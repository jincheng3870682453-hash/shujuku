# -*- coding: utf-8 -*-
"""
drsync 单元测试（Phase 4）
==========================

覆盖（语义见 docs/drsync.md）：
  ① 两库字段级合并：A 改 姓名、B 改 部门，合并后两者都在且各自保留
     （另测并发新增不同字段的 union 各自保留）
  ② 同字段冲突新者胜（rows_data 与普通表各一）
  ③ 加密包口令错抛 SyncError；伪包 / 截断包 / 坏版本 / 空口令也抛
  ④ 整包 roundtrip：A 库 → export → 打包 → B 空库导入 → 逐行相等
  ⑤ import 幂等：重复导入行数不翻倍
  ⑥ 水位增量：第二次 export 只带新增行
  + P2P 网络层 smoke：beacon 编解码、邻居超时剔除、Flask 收包逻辑
    （test_client 进程内验证，不开任何端口）、bind 失败优雅降级

运行方式（必须从项目根目录，临时目录指到 .dsh-tmp）：
    # TMPDIR/TEMP/TMP 均设为 G:/dynamic_registry/.dsh-tmp
    python -m pytest backend/test_drsync.py -q

约定：全部使用 tempfile 临时目录，绝不读写 data/app.db 真库；
     单测不真正起 UDP/HTTP 服务；不 import app（DDL 拷贝自 app.init_db）。
"""

import json
import os
import socket
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.db_adapter import SQLiteAdapter
from backend.drsync import (
    SyncError,
    compute_watermark,
    export_events,
    import_events,
    pack_bytes,
    read_drsync,
    unpack_bytes,
    write_drsync,
)
from backend.drsync.node import (
    NodeHandle,
    _make_app,
    build_beacon,
    parse_beacon,
    scan_peers,
)

# ────────────────────── 测试库脚手架 ──────────────────────
# 与 app.init_db（Phase 2b TEXT PK / UUIDv7 版本）一致的 8 张表 DDL，
# 拷贝自 app.py init_db（铁律：测试不 import app、不碰真库）。

_TS_SQL = "datetime('now','localtime')"

DDL_TABLES = (
    f"CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'employee', permissions TEXT DEFAULT '[]', global_audit INTEGER DEFAULT 0, theme TEXT DEFAULT NULL, created_at DATETIME DEFAULT ({_TS_SQL}))",
    "CREATE TABLE IF NOT EXISTS columns_meta (id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, label TEXT NOT NULL, field_type TEXT NOT NULL DEFAULT 'text', options TEXT, position INTEGER DEFAULT 0)",
    f"CREATE TABLE IF NOT EXISTS rows_data (id TEXT PRIMARY KEY, data TEXT NOT NULL DEFAULT '{{}}', created_by TEXT NOT NULL DEFAULT '', schema_version INTEGER NOT NULL DEFAULT 0, created_at DATETIME DEFAULT ({_TS_SQL}), updated_at DATETIME DEFAULT ({_TS_SQL}))",
    f"CREATE TABLE IF NOT EXISTS audit_log (id TEXT PRIMARY KEY, user_id TEXT, username TEXT, action TEXT, target_table TEXT, target_id TEXT, old_value TEXT, new_value TEXT, created_at DATETIME DEFAULT ({_TS_SQL}))",
    f"CREATE TABLE IF NOT EXISTS pending_changes (id TEXT PRIMARY KEY, row_id TEXT, column_name TEXT, old_value TEXT, new_value TEXT, change_type TEXT NOT NULL, requested_by TEXT, status TEXT DEFAULT '待审核', reviewed_by TEXT, review_comment TEXT, reviewed_at DATETIME, created_at DATETIME DEFAULT ({_TS_SQL}))",
    f"CREATE TABLE IF NOT EXISTS operations_log (id TEXT PRIMARY KEY, user_id TEXT, username TEXT, role TEXT, action TEXT, target_type TEXT, target_id TEXT, detail TEXT, created_at DATETIME DEFAULT ({_TS_SQL}))",
    f"CREATE TABLE IF NOT EXISTS backups (id TEXT PRIMARY KEY, filename TEXT UNIQUE, size_bytes INTEGER, created_at DATETIME DEFAULT ({_TS_SQL}))",
    f"CREATE TABLE IF NOT EXISTS ai_analysis_history (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, report TEXT, chat_history TEXT, created_at DATETIME DEFAULT ({_TS_SQL}), updated_at DATETIME DEFAULT ({_TS_SQL}))",
)

T0 = "2026-11-07 10:00:00"
T1 = "2026-11-07 10:01:00"
T2 = "2026-11-07 10:02:00"
T3 = "2026-11-07 10:03:00"
T4 = "2026-11-07 10:04:00"
T5 = "2026-11-07 10:05:00"
T9 = "2026-11-07 10:09:00"

ROW_A = "aaaaaaaa-0000-7000-8000-00000000000a"
ROW_B = "bbbbbbbb-0000-7000-8000-00000000000b"
ROW_C = "cccccccc-0000-7000-8000-00000000000c"
USER_1 = "11111111-0000-7000-8000-000000000001"
USER_2 = "11111111-0000-7000-8000-000000000002"
USER_3 = "11111111-0000-7000-8000-000000000003"
PC_1 = "22222222-0000-7000-8000-000000000002"


def make_db(tmpdir, name="a.db"):
    """临时库：8 张 TEXT PK 表（DDL 与 app.init_db 一致）。"""
    adapter = SQLiteAdapter(os.path.join(str(tmpdir), name))
    adapter.connect()
    for stmt in DDL_TABLES:
        adapter.execute_query(stmt)
    return adapter


class DrsyncTestCase(unittest.TestCase):
    """公共脚手架：临时目录 + SQLite 适配器登记。

    Windows 下 sqlite 连接不关会导致 TemporaryDirectory 清理报
    WinError 32，所以这里统一 addCleanup(adapter.close)。
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.td = self._td.name
        self._dbs = []

    def make(self, name="a.db"):
        """在临时目录建一个 8 表库，退出时自动关闭。"""
        adapter = make_db(self.td, name)
        self._dbs.append(adapter)
        self.addCleanup(adapter.close)
        return adapter


def row(rid, data, ts=T0, created=T0, created_by="op", schema_version=1):
    return {
        "id": rid,
        "data": json.dumps(data, ensure_ascii=False),
        "created_by": created_by,
        "schema_version": schema_version,
        "created_at": created,
        "updated_at": ts,
    }


def user(uid, role="employee", ts=T0, username="alice"):
    return {"id": uid, "username": username, "password_hash": "h", "role": role,
            "permissions": "[]", "global_audit": 0, "theme": None, "created_at": ts}


def edit_row(adapter, rid, data, ts):
    adapter.execute_query(
        "UPDATE rows_data SET data = ?, updated_at = ? WHERE id = ?",
        (json.dumps(data, ensure_ascii=False), ts, rid),
    )


def read_row(adapter, rid):
    r = adapter.fetch_one("SELECT data, updated_at FROM rows_data WHERE id = ?", (rid,))
    assert r is not None, f"row {rid} missing"
    return json.loads(r["data"]), r["updated_at"]


# ────────────────────── ③ 加密包 ──────────────────────


class TestCrypto(DrsyncTestCase):
    def test_pack_unpack_roundtrip(self):
        data = "行数据♪→JSON".encode("utf-8")
        self.assertEqual(unpack_bytes(pack_bytes(data, "口令pw"), "口令pw"), data)

    def test_wrong_password_raises(self):
        blob = pack_bytes(b"secret", "right-password")
        with self.assertRaises(SyncError):
            unpack_bytes(blob, "wrong-password")

    def test_file_roundtrip_and_ciphertext_on_disk(self):
        """落盘前必须已是密文：文件里既无明文也无口令，且带头部 magic。"""
        data = b"TOP-SECRET-ROWS-2026"
        path = os.path.join(self.td, "pkg.drsync")
        write_drsync(path, data, "pw123")
        blob = open(path, "rb").read()
        self.assertTrue(blob.startswith(b"DRSYNC1"))
        self.assertNotIn(data, blob)
        self.assertNotIn(b"pw123", blob)
        self.assertEqual(read_drsync(path, "pw123"), data)

    def test_bad_magic_truncated_bad_version(self):
        with self.assertRaises(SyncError):
            unpack_bytes(b"XXXXXXXX" + b"\x00" * 60, "pw")  # magic 不对
        with self.assertRaises(SyncError):
            unpack_bytes(pack_bytes(b"x", "pw")[:-5], "pw")  # 截断
        good = pack_bytes(b"x", "pw")
        bad_version = good[:7] + bytes([99]) + good[8:]
        with self.assertRaises(SyncError):
            unpack_bytes(bad_version, "pw")

    def test_salt_unique_per_pack(self):
        b1 = pack_bytes(b"same", "pw")
        b2 = pack_bytes(b"same", "pw")
        self.assertNotEqual(b1, b2)  # salt/IV 随机，同明文同口令两包也不同

    def test_empty_password_raises(self):
        with self.assertRaises(SyncError):
            pack_bytes(b"x", "")


# ────────────────────── ①② 合并语义 ──────────────────────


class TestMerge(DrsyncTestCase):
    def test_two_editors_different_columns_both_survive(self):
        """① A 改姓名、B 改部门：双向同步后两人的修改都在。"""
        a = self.make("a.db")
        b = self.make("b.db")
        base = row(ROW_A, {"姓名": "张三", "部门": "研发"}, ts=T0)
        a.insert("rows_data", dict(base))
        b.insert("rows_data", dict(base))

        # B 改部门（T2）→ 全量导出 → A 导入
        edit_row(b, ROW_A, {"姓名": "张三", "部门": "销售"}, T2)
        import_events(a, export_events(b), source_node="B")
        data, ts = read_row(a, ROW_A)
        self.assertEqual(data, {"姓名": "张三", "部门": "销售"})  # B 的修改进入 A
        self.assertEqual(ts, T2)

        # A 改姓名（T3）→ 水位增量导出 → B 导入
        edit_row(a, ROW_A, {"姓名": "王五", "部门": "销售"}, T3)
        import_events(b, export_events(a, since=T2), source_node="A")
        for db in (a, b):
            data, ts = read_row(db, ROW_A)
            self.assertEqual(data["姓名"], "王五")  # A 的修改保留
            self.assertEqual(data["部门"], "销售")  # B 的修改保留
            self.assertEqual(ts, T3)

    def test_union_disjoint_fields_concurrent(self):
        """①' 并发各自新增不同字段：union 后两个新字段都在。"""
        a = self.make("a.db")
        b = self.make("b.db")
        a.insert("rows_data", row(ROW_A, {"姓名": "张三", "备注": "A的备注"}, ts=T5))
        b.insert("rows_data", row(ROW_A, {"姓名": "张三", "电话": "123"}, ts=T3))
        import_events(a, export_events(b), source_node="B")
        data, _ = read_row(a, ROW_A)
        self.assertEqual(data, {"姓名": "张三", "备注": "A的备注", "电话": "123"})

    def test_same_field_conflict_newer_wins(self):
        """② 同字段冲突：updated_at 新者胜；旧包反向导入被跳过。"""
        a = self.make("a.db")
        b = self.make("b.db")
        a.insert("rows_data", row(ROW_A, {"姓名": "李四"}, ts=T5))
        b.insert("rows_data", row(ROW_A, {"姓名": "王五"}, ts=T4))

        stats = import_events(b, export_events(a, since=T4), source_node="A")
        self.assertEqual(stats["merged"], 1)
        data, ts = read_row(b, ROW_A)
        self.assertEqual(data["姓名"], "李四")  # 新者胜
        self.assertEqual(ts, T5)  # 行时间戳也取新者

        # 旧的 B 行再导回 A：本地较新 → skipped，不回退
        old_event = [{"table": "rows_data", "id": ROW_A, "created_at": T0,
                      "updated_at": T4, "row": row(ROW_A, {"姓名": "王五"}, ts=T4)}]
        stats2 = import_events(a, old_event, source_node="B")
        self.assertEqual(stats2["skipped"], 1)
        self.assertEqual(read_row(a, ROW_A)[0]["姓名"], "李四")

    def test_plain_table_newer_row_wins(self):
        """②' 普通表（users，无 updated_at）按 created_at 新者胜。"""
        a = self.make("a.db")
        b = self.make("b.db")
        a.insert("users", user(USER_1, role="admin", ts=T5))
        b.insert("users", user(USER_1, role="employee", ts=T3))
        import_events(b, export_events(a, since=T3), source_node="A")
        self.assertEqual(b.fetch_one("SELECT role FROM users WHERE id=?", (USER_1,))["role"], "admin")
        old = [{"table": "users", "id": USER_1, "created_at": T3, "updated_at": None,
                "row": user(USER_1, role="employee", ts=T3)}]
        stats = import_events(a, old, source_node="B")
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(a.fetch_one("SELECT role FROM users WHERE id=?", (USER_1,))["role"], "admin")

    def test_pending_changes_status_preserved(self):
        """pending_changes 导入保持源库原 status；本地更新的审核不被旧包覆盖。"""
        b = self.make("b.db")
        incoming = {"id": PC_1, "row_id": ROW_A, "column_name": "部门", "old_value": "研发",
                    "new_value": "销售", "change_type": "修改", "requested_by": "u1",
                    "status": "已通过", "reviewed_by": "boss", "review_comment": "ok",
                    "reviewed_at": T5, "created_at": T3}
        stale = dict(incoming, status="待审核", reviewed_by=None, review_comment=None,
                     reviewed_at=None, created_at=T2)
        b.insert("pending_changes", stale)
        stats = import_events(b, [{"table": "pending_changes", "id": PC_1,
                                   "created_at": T3, "updated_at": None, "row": incoming}])
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(b.fetch_one("SELECT status FROM pending_changes WHERE id=?", (PC_1,))["status"],
                         "已通过")  # imported 保持原 status

        # 本地是更新的审核结论（T9 已驳回）→ 旧包（T3 待审核）不得覆盖
        b.execute_query("UPDATE pending_changes SET status='已驳回', created_at=? WHERE id=?", (T9, PC_1))
        stats2 = import_events(b, [{"table": "pending_changes", "id": PC_1,
                                    "created_at": T3, "updated_at": None, "row": incoming}])
        self.assertEqual(stats2["skipped"], 1)
        self.assertEqual(b.fetch_one("SELECT status FROM pending_changes WHERE id=?", (PC_1,))["status"],
                         "已驳回")


# ────────────────────── ④⑤ 整包与幂等 ──────────────────────


class TestRoundtripAndIdempotency(DrsyncTestCase):
    def setUp(self):
        super().setUp()
        self.a = self.make("a.db")
        self.a.insert("rows_data", row(ROW_A, {"姓名": "张三", "部门": "研发"}, ts=T0))
        self.a.insert("rows_data", row(ROW_B, {"姓名": "李四", "部门": "市场"}, ts=T1))
        self.a.insert("rows_data", row(ROW_C, {"姓名": "王五", "部门": "财务", "备注": "♪unicode"}, ts=T2))
        self.a.insert("users", user(USER_1, role="admin", ts=T0))

    def test_full_package_roundtrip(self):
        """④ A 库 → export → 加密包 → B 空库导入 → 逐行相等。"""
        events = export_events(self.a)
        plaintext = json.dumps(events, ensure_ascii=False).encode("utf-8")
        path = write_drsync(os.path.join(self.td, "pkg.drsync"), plaintext, "口令123")

        plain2 = read_drsync(path, "口令123")
        self.assertEqual(json.loads(plain2.decode("utf-8")), events)  # 包内事件无损

        b = self.make("b.db")
        stats = import_events(b, json.loads(plain2.decode("utf-8")), source_node="pkg")
        self.assertEqual(stats["inserted"], 4)
        # 逐行相等（rows_data 与 users 全列比较）
        self.assertEqual(b.fetch_all("SELECT * FROM rows_data ORDER BY id"),
                         self.a.fetch_all("SELECT * FROM rows_data ORDER BY id"))
        self.assertEqual(b.fetch_all("SELECT * FROM users ORDER BY id"),
                         self.a.fetch_all("SELECT * FROM users ORDER BY id"))

    def test_import_idempotent(self):
        """⑤ 重复导入行数不翻倍，且不再产生新插入。"""
        events = export_events(self.a)
        b = self.make("b.db")
        import_events(b, events)
        import_events(b, events)
        import_events(b, events)
        self.assertEqual(len(b.fetch_all("SELECT * FROM rows_data")), 3)
        self.assertEqual(len(b.fetch_all("SELECT * FROM users")), 1)
        stats = import_events(b, events)
        self.assertEqual(stats["inserted"], 0)
        self.assertEqual(len(b.fetch_all("SELECT * FROM rows_data")), 3)


# ────────────────────── ⑥ 水位增量 ──────────────────────


class TestWatermark(DrsyncTestCase):
    def test_second_export_only_new_rows(self):
        """⑥ 第一次全量 → 记水位 → 只插新行 → 第二次 export 只带新增行。

        columns_meta 没有时间戳列：首次全量带出，之后按 id（UUIDv7）
        水位增量——没有新字段定义就不重复出现。
        """
        a = self.make("a.db")
        a.insert("rows_data", row(ROW_A, {"姓名": "张三"}, ts=T0))
        a.insert("rows_data", row(ROW_B, {"姓名": "李四"}, ts=T1))
        a.insert("users", user(USER_1, ts=T0))
        a.insert("columns_meta", {"id": "col-1", "name": "姓名", "label": "姓名",
                                  "field_type": "text", "options": None, "position": 0})

        first = export_events(a)
        self.assertEqual(len(first), 4)  # 2 rows_data + 1 users + 1 columns_meta
        json.dumps(first, ensure_ascii=False)  # 事件流必须 JSON 可序列化
        mark = compute_watermark(first)
        self.assertEqual(mark["columns_meta"], "col-1")  # 无时间戳表按 max(id)

        # 水位之后只新增：1 行 rows_data + 1 个用户
        a.insert("rows_data", row(ROW_C, {"姓名": "王五"}, ts=T9))
        a.insert("users", user(USER_2, ts=T9, username="bob"))

        second = export_events(a, since=mark)
        self.assertEqual({(e["table"], e["id"]) for e in second},
                         {("rows_data", ROW_C), ("users", USER_2)})
        self.assertNotIn(ROW_A, {e["id"] for e in second})
        self.assertNotIn(ROW_B, {e["id"] for e in second})

        # 增量导进已有旧数据的 B 库，正好补齐
        b = self.make("b.db")
        import_events(b, first)
        stats = import_events(b, second)
        self.assertEqual(stats["inserted"], 2)
        self.assertEqual(len(b.fetch_all("SELECT * FROM rows_data")), 3)


# ────────────────────── 导入防御 ──────────────────────


class TestImportSafety(DrsyncTestCase):
    def test_unknown_table_and_missing_id_skipped(self):
        db = self.make("a.db")
        stats = import_events(db, [
            {"table": "not_a_table", "id": "x", "row": {}},       # 未知表
            {"table": "rows_data", "row": {"data": "{}"}},        # 缺 id
        ])
        self.assertEqual(stats["unknown_table"], 1)
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(stats["inserted"], 0)
        self.assertEqual(len(db.fetch_all("SELECT * FROM rows_data")), 0)

    def test_import_accepts_adapter_instance(self):
        """db 参数既可以是路径，也可以是已连接的适配器。"""
        src = self.make("src.db")
        dst = self.make("dst.db")
        src.insert("rows_data", row(ROW_A, {"a": 1}, ts=T1))
        stats = import_events(dst, export_events(src), source_node="x")
        self.assertEqual(stats["inserted"], 1)
        self.assertEqual(dst.fetch_one("SELECT id FROM rows_data")["id"], ROW_A)

    def test_import_is_atomic_on_error(self):
        """整体事务：中途炸了全部回滚，不留半包。

        用 users.username 的 UNIQUE 约束制造必然失败
        （SQLite 列是动态类型，塞错型不会报错，约束才会）。
        """
        db = self.make("a.db")
        db.insert("users", user(USER_3, username="alice"))  # 已占用 username
        good = {"table": "rows_data", "id": ROW_A, "created_at": T0,
                "updated_at": T0, "row": row(ROW_A, {"a": 1})}
        broken = {"table": "users", "id": USER_2, "created_at": T0, "updated_at": None,
                  "row": user(USER_2, username="alice")}  # UNIQUE 冲突 → 必炸
        with self.assertRaises(Exception):
            import_events(db, [good, broken])
        self.assertEqual(len(db.fetch_all("SELECT * FROM rows_data")), 0)  # good 也被回滚
        self.assertEqual(len(db.fetch_all("SELECT * FROM users")), 1)  # 只剩预置那行


# ────────────────────── P2P 网络层 smoke（不开真实端口） ──────────────────────


class TestNodeLogic(DrsyncTestCase):
    def test_beacon_roundtrip(self):
        payload = build_beacon("node-1", "HOST-1", 41889, ts=123.0)
        info = parse_beacon(payload)
        self.assertEqual(info["magic"], "DRBEACON1")
        self.assertEqual(info["node_id"], "node-1")
        self.assertEqual(info["hostname"], "HOST-1")
        self.assertEqual(info["http_port"], 41889)
        self.assertEqual(info["ts"], 123.0)

    def test_beacon_garbage_returns_none(self):
        for bad in (b"", b"\xff\xfe\x00", b"not json", b"{}", b'{"magic":"WRONG"}',
                    b'{"magic":"DRBEACON1"}'):  # 缺 node_id 也算坏包
            self.assertIsNone(parse_beacon(bad), bad)

    def test_peer_timeout_pruning(self):
        handle = NodeHandle(db_path="unused.db", password="p", beacon_enabled=False)
        self.addCleanup(handle.stop)
        handle._record_peer("n1", "192.168.1.5", 41889, "pc-1")
        self.assertIn("n1", handle.peers())
        with handle._peers_lock:
            handle._peers["n1"]["last_seen"] = time.time() - (10 + 1)
        self.assertNotIn("n1", handle.peers())  # 超 10s 剔除

    def _make_node_client(self):
        # 收包目标库先建好 8 张表（真实场景里节点库本来就是应用建好的库）
        db = self.make("node.db")
        handle = NodeHandle(db_path=db._db_path,
                            password="pw-node", beacon_enabled=False)
        handle.app = _make_app(handle)
        return handle, handle.app.test_client()

    def test_flask_push_wrong_password_rejected(self):
        """收包必须先过加密校验：口令错 → 400 且绝不入库。"""
        src = self.make("src.db")
        src.insert("rows_data", row(ROW_A, {"姓名": "张三"}, ts=T1))
        events = export_events(src)
        blob = pack_bytes(json.dumps(events, ensure_ascii=False).encode("utf-8"), "other-pw")

        handle, client = self._make_node_client()
        resp = client.post("/drsync/push", data=blob, content_type="application/octet-stream")
        self.assertEqual(resp.status_code, 400)
        db = SQLiteAdapter(handle.db_path)
        db.connect()
        self.addCleanup(db.close)
        self.assertEqual(len(db.fetch_all("SELECT * FROM rows_data")), 0)

    def test_flask_push_ok_and_peers_endpoint(self):
        src = self.make("src.db")
        src.insert("rows_data", row(ROW_A, {"姓名": "张三", "部门": "研发"}, ts=T1))
        events = export_events(src)
        blob = pack_bytes(json.dumps(events, ensure_ascii=False).encode("utf-8"), "pw-node")

        handle, client = self._make_node_client()
        resp = client.post("/drsync/push", data=blob, content_type="application/octet-stream")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])
        self.assertEqual(resp.get_json()["stats"]["inserted"], 1)

        db = SQLiteAdapter(handle.db_path)
        db.connect()
        self.addCleanup(db.close)
        self.assertEqual(json.loads(db.fetch_one(
            "SELECT data FROM rows_data WHERE id=?", (ROW_A,))["data"])["姓名"], "张三")

        info = client.get("/drsync/peers")
        self.assertEqual(info.status_code, 200)
        self.assertEqual(info.get_json()["node_id"], handle.node_id)

    def test_scan_peers_bind_failure_degrades(self):
        """bind 失败必须优雅降级：返回 ({}, False)，绝不抛异常。

        Windows 允许 0.0.0.0:p 与 127.0.0.1:p 共存（特定地址绑定优先），
        所以占用方必须也绑 0.0.0.0 才能制造确定性的端口冲突。
        """
        occupier = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        occupier.bind(("0.0.0.0", 0))
        port = occupier.getsockname()[1]
        try:
            peers, listening = scan_peers(timeout=0.2, listen_port=port)
            self.assertFalse(listening)
            self.assertEqual(peers, {})
        finally:
            occupier.close()


if __name__ == "__main__":
    unittest.main()
