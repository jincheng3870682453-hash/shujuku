# -*- coding: utf-8 -*-
"""
drsync 去中心化 P2P 节点（**可选增强，默认关闭**）。

设计（用户裁定，见 docs/立项-存储层重构.md §0.1 / docs/drsync.md）：
  * 不需要中心服务器：同一局域网内每台机器都是对等节点，可互相同步、自动发现。
  * 发现：UDP 广播 0.0.0.0:41888，包体 JSON
        {magic:'DRBEACON1', node_id, hostname, http_port, ts}
    周期 3s；同时监听收集邻居 {node_id: (ip, port, last_seen)}，
    超时 10s 剔除。全部线程 daemon，程序退出即无残留。
  * 传输：每节点可选起一个 Flask 小应用，仅绑定 127.0.0.1（或指定所在网卡），
    端口 41889：
        POST /drsync/push   body = 整个 .drsync 文件字节（口令不传输，双方共同口令约定）
        GET  /drsync/peers  列邻居
  * 安全断言：不做 NAT 穿透、不连公网；收到的包必须先过 crypto.unpack_bytes
    校验才入库；口令只在本机内存里用于解密。
  * 优雅降级：UDP/HTTP bind 失败不抛致命错误，节点退化为「纯手工包模式」
    （手工 export/import 永远可用）。

本模块在 backend.drsync.__init__ 里是懒加载的：只有显式调用 start_node()
才会开端口；不调用则整个进程不开任何监听端口。
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from typing import Any, Dict, Optional, Tuple

from ..uuid7 import uuid7
from . import crypto as _crypto
from . import events as _events
from .crypto import SyncError

#: UDP 广播包魔数
BEACON_MAGIC = "DRBEACON1"
#: UDP 广播发现端口
BEACON_PORT = 41888
#: HTTP 收包默认端口
DEFAULT_HTTP_PORT = 41889
#: 广播周期（秒）
BEACON_INTERVAL = 3.0
#: 邻居超时剔除（秒）
PEER_TIMEOUT = 10.0

__all__ = ["NodeHandle", "start_node", "stop_node", "scan_peers",
           "build_beacon", "parse_beacon",
           "BEACON_MAGIC", "BEACON_PORT", "DEFAULT_HTTP_PORT",
           "BEACON_INTERVAL", "PEER_TIMEOUT"]


# ────────────────────── beacon 编解码（纯逻辑，可单测） ──────────────────────


def build_beacon(node_id: str, hostname: str, http_port: int,
                 ts: Optional[float] = None) -> bytes:
    """构造 UDP 广播包体（JSON，UTF-8）。"""
    return json.dumps({
        "magic": BEACON_MAGIC,
        "node_id": node_id,
        "hostname": hostname,
        "http_port": http_port,
        "ts": time.time() if ts is None else ts,
    }, ensure_ascii=False).encode("utf-8")


def parse_beacon(data: bytes) -> Optional[Dict[str, Any]]:
    """解析并校验 beacon 包体；任何非法包返回 None，绝不抛异常。"""
    try:
        obj = json.loads(bytes(data).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, TypeError):
        return None
    if not isinstance(obj, dict) or obj.get("magic") != BEACON_MAGIC:
        return None
    node_id = obj.get("node_id")
    if not isinstance(node_id, str) or not node_id:
        return None
    return obj


# ────────────────────── 节点句柄 ──────────────────────


class NodeHandle:
    """start_node() 返回的节点句柄；也可直接构造纯逻辑实例（不起任何服务）。"""

    def __init__(self, db_path: str, password: str,
                 http_port: int = DEFAULT_HTTP_PORT,
                 beacon_enabled: bool = True,
                 node_id: Optional[str] = None,
                 hostname: Optional[str] = None):
        self.node_id = node_id or uuid7()
        self.db_path = os.path.abspath(db_path)
        self.password = password  # 只存内存，绝不落盘 / 上网络
        self.http_port = http_port
        self.beacon_enabled = beacon_enabled
        self.hostname = hostname or socket.gethostname()
        self.http_active = False   # HTTP 收包是否可用
        self.listen_active = False  # UDP 监听是否可用
        self.app = None
        self._http_server = None
        self._stop = threading.Event()
        self._peers: Dict[str, Dict[str, Any]] = {}
        self._peers_lock = threading.Lock()

    # ── 邻居表 ──

    def _record_peer(self, node_id: str, ip: str, http_port: Any,
                     hostname: str = "") -> None:
        with self._peers_lock:
            self._peers[node_id] = {
                "ip": ip,
                "http_port": http_port,
                "hostname": hostname,
                "last_seen": time.time(),
            }

    def _prune(self) -> None:
        cutoff = time.time() - PEER_TIMEOUT
        with self._peers_lock:
            for nid in [n for n, info in self._peers.items() if info["last_seen"] < cutoff]:
                del self._peers[nid]

    def peers(self) -> Dict[str, Dict[str, Any]]:
        """当前邻居快照（超时 10s 的已剔除）。"""
        self._prune()
        with self._peers_lock:
            return {nid: dict(info) for nid, info in self._peers.items()}

    # ── 生命周期 ──

    def stop(self) -> None:
        """停广播、停监听、关 HTTP；可安全重复调用。"""
        self._stop.set()
        server, self._http_server = self._http_server, None
        if server is not None:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
        self.http_active = False


# ────────────────────── Flask 收包应用 ──────────────────────


def _make_app(handle: NodeHandle):
    """
    构造收包 Flask 应用。真实端口由 start_node() 里的 make_server 打开；
    单测用 app.test_client() 在进程内验证逻辑，不开任何端口。
    """
    from flask import Flask, jsonify, request

    app = Flask("drsync-node")
    app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 单包上限 512MB

    @app.post("/drsync/push")
    def push():
        body = request.get_data(cache=False)
        # 安全断言：先过加密校验才碰数据库；口令错 / 伪包一律 400，绝不入库
        try:
            plaintext = _crypto.unpack_bytes(body, handle.password)
        except SyncError as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        try:
            events = json.loads(plaintext.decode("utf-8"))
            if not isinstance(events, list):
                raise ValueError("事件流必须是 list")
            stats = _events.import_events(handle.db_path, events,
                                          source_node=request.remote_addr or "")
        except Exception as e:
            return jsonify({"ok": False, "error": f"导入失败: {e}"}), 400
        return jsonify({"ok": True, "stats": stats})

    @app.get("/drsync/peers")
    def peers():
        return jsonify({
            "ok": True,
            "node_id": handle.node_id,
            "hostname": handle.hostname,
            "peers": handle.peers(),
        })

    return app


# ────────────────────── 发现线程 ──────────────────────


def _beacon_sender(handle: NodeHandle) -> None:
    """周期 3s 广播本节点 beacon（发送端不需要绑定固定端口）。"""
    payload = build_beacon(handle.node_id, handle.hostname, handle.http_port)
    send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while not handle._stop.is_set():
            try:
                send.sendto(payload, ("<broadcast>", BEACON_PORT))
            except OSError:
                pass  # 网络暂不可用：静默重试，广播失败不影响手工包通道
            handle._stop.wait(BEACON_INTERVAL)
    finally:
        send.close()


def _beacon_listener(handle: NodeHandle) -> None:
    """监听 41888 收集邻居；bind 失败 → listen_active=False（优雅降级）。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不设 SO_REUSEADDR：UDP 发现端口同机只该有一个监听者，
        # 重复 bind 直接失败 → 走优雅降级（纯手工包模式），且行为跨平台确定
        sock.bind(("0.0.0.0", BEACON_PORT))
    except OSError:
        handle.listen_active = False
        sock.close()
        return
    handle.listen_active = True
    sock.settimeout(0.5)
    try:
        while not handle._stop.is_set():
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            info = parse_beacon(data)
            if not info or info.get("node_id") == handle.node_id:
                continue  # 坏包 / 自己的回环广播
            handle._record_peer(info["node_id"], addr[0], info.get("http_port"),
                                hostname=info.get("hostname") or "")
    finally:
        sock.close()


# ────────────────────── 启停与一次性扫描 ──────────────────────

_current: Optional[NodeHandle] = None
_current_lock = threading.Lock()


def start_node(db_path: str, password: str,
               http_port: int = DEFAULT_HTTP_PORT,
               beacon: bool = True,
               bind_http: str = "127.0.0.1") -> NodeHandle:
    """
    启动一个对等节点（HTTP 收包 + UDP 广播发现，均为 daemon 线程）。

    任何 bind 失败都优雅降级：
      * HTTP 起不来 → http_active=False（退化为纯手工包模式）；
      * UDP 监听起不来 → listen_active=False（只广播不收集）。
    默认绑定 127.0.0.1；局域网其他机器要推包给你时传 bind_http="0.0.0.0"
    （仍只在局域网使用，不做任何公网暴露 / NAT 穿透）。
    """
    global _current
    handle = NodeHandle(db_path=db_path, password=password,
                        http_port=http_port, beacon_enabled=bool(beacon))
    try:
        from werkzeug.serving import make_server

        handle.app = _make_app(handle)
        handle._http_server = make_server(bind_http, http_port, handle.app, threaded=True)
        handle.http_port = handle._http_server.socket.getsockname()[1]
        handle.http_active = True
        threading.Thread(target=handle._http_server.serve_forever,
                         name="drsync-http", daemon=True).start()
    except Exception:
        handle.http_active = False
        handle._http_server = None

    if beacon:
        threading.Thread(target=_beacon_sender, args=(handle,),
                         name="drsync-beacon-send", daemon=True).start()
        threading.Thread(target=_beacon_listener, args=(handle,),
                         name="drsync-beacon-recv", daemon=True).start()

    with _current_lock:
        _current = handle
    return handle


def stop_node(handle: Optional[NodeHandle] = None) -> None:
    """停止节点（缺省停最近一次 start_node 的节点）；可安全重复调用。"""
    global _current
    with _current_lock:
        target = handle or _current
        if target is not None and target is _current:
            _current = None
    if target is not None:
        target.stop()


def scan_peers(timeout: float = 9.0, listen_port: int = BEACON_PORT
               ) -> Tuple[Dict[str, Dict[str, Any]], bool]:
    """
    一次性监听邻居广播（供 CLI `peers` 用；不起 HTTP、不发广播）。

    Returns:
        (peers, listening)。listening=False 表示 UDP 端口绑定失败
        （优雅降级，调用方提示改用手工包通道）。
    """
    peers: Dict[str, Dict[str, Any]] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 同上：不设 SO_REUSEADDR，端口冲突立即失败 → listening=False
        sock.bind(("0.0.0.0", listen_port))
    except OSError:
        sock.close()
        return peers, False
    sock.settimeout(0.5)
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            info = parse_beacon(data)
            if not info:
                continue
            peers[info["node_id"]] = {
                "ip": addr[0],
                "http_port": info.get("http_port"),
                "hostname": info.get("hostname") or "",
                "last_seen": time.time(),
            }
    finally:
        sock.close()
    return peers, True
