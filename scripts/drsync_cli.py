#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
drsync 命令行（Phase 4）—— 离线多机同步手工通道 + 可选 LAN P2P。

用法（从项目根目录运行）：
    python scripts/drsync_cli.py export --db data/app.db --out out.drsync --password 口令 [--since "2026-11-07 10:00:00"]
    python scripts/drsync_cli.py import --db data/app.db --file out.drsync --password 口令
    python scripts/drsync_cli.py serve  --db data/app.db --password 口令 [--port 41889] [--no-beacon]
    python scripts/drsync_cli.py peers  [--timeout 9]

export / import / peers 不开任何监听端口；只有 serve 显式启动局域网节点
（默认关，安全模型见 docs/drsync.md）。口令只在内存参与密钥派生。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading

# 独立运行时把项目根目录放进 sys.path（scripts/ 的上一级）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.drsync import SyncError, export_events, import_events, read_drsync, write_drsync


def cmd_export(args) -> None:
    events = export_events(args.db, args.since)
    payload = json.dumps(events, ensure_ascii=False).encode("utf-8")
    write_drsync(args.out, payload, args.password)
    print(f"[drsync] 导出 {len(events)} 条事件 -> {args.out}（落盘即密文）")


def cmd_import(args) -> None:
    plaintext = read_drsync(args.file, args.password)
    events = json.loads(plaintext.decode("utf-8"))
    stats = import_events(args.db, events, source_node="cli")
    print("[drsync] 导入完成 " + json.dumps(stats, ensure_ascii=False))


def cmd_serve(args) -> None:
    from backend.drsync.node import start_node, stop_node

    handle = start_node(args.db, args.password, http_port=args.port, beacon=not args.no_beacon)
    print(f"[drsync] 节点 {handle.node_id} 已启动："
          f"http={'开' if handle.http_active else '降级(手工包模式)'} "
          f"udp监听={'开' if handle.listen_active else '降级(只广播)'} "
          f"端口 {handle.http_port}（Ctrl+C 退出）")
    try:
        threading.Event().wait()  # 常驻直到 Ctrl+C
    except KeyboardInterrupt:
        print()
    finally:
        stop_node(handle)
        print("[drsync] 节点已停止，端口已释放")


def cmd_peers(args) -> None:
    from backend.drsync.node import scan_peers

    peers, listening = scan_peers(timeout=args.timeout)
    if not listening:
        print("[drsync] UDP 41888 绑定失败（端口被占用或无网络），退化为纯手工包模式："
              "用 export / import 交换 .drsync 文件即可。")
        return
    if not peers:
        print(f"[drsync] {args.timeout:.0f}s 内未发现邻居（对方机器需先执行 serve）")
        return
    print(f"[drsync] 发现 {len(peers)} 个邻居：")
    for nid, info in sorted(peers.items()):
        print(f"  {nid}  {info.get('hostname') or '?'}  {info['ip']}:{info['http_port']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drsync_cli",
        description="dynamic_registry 离线多机同步（.drsync 加密包 / LAN P2P 可选增强）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("export", help="导出增量事件流并加密为 .drsync 包")
    p.add_argument("--db", required=True, help="SQLite 库文件路径")
    p.add_argument("--out", required=True, help="输出 .drsync 文件路径")
    p.add_argument("--since", default=None, help="水位时间戳 'YYYY-MM-DD HH:MM:SS'（缺省全量对账）")
    p.add_argument("--password", required=True, help="加密口令（不落盘、不上网络）")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("import", help="解密 .drsync 包并按主键 upsert 导入")
    p.add_argument("--db", required=True, help="SQLite 库文件路径")
    p.add_argument("--file", required=True, help="输入 .drsync 文件路径")
    p.add_argument("--password", required=True, help="解密口令")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("serve", help="（可选增强）启动 LAN P2P 节点：UDP 发现 + HTTP 收加密包")
    p.add_argument("--db", required=True, help="SQLite 库文件路径")
    p.add_argument("--password", required=True, help="收包解密口令（双方共同约定）")
    p.add_argument("--port", type=int, default=41889, help="HTTP 收包端口（默认 41889）")
    p.add_argument("--no-beacon", action="store_true", help="不发 UDP 广播（只收包不宣告）")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("peers", help="监听一轮 UDP 广播，列出局域网邻居节点")
    p.add_argument("--timeout", type=float, default=9.0, help="监听时长秒数（默认 9）")
    p.set_defaults(func=cmd_peers)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except SyncError as exc:  # 口令错 / 包损坏：友好退出码
        print(f"[drsync] 失败：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
