# -*- coding: utf-8 -*-
"""
Phase 2c 乐观锁 API 层端到端测试。

链路：GET /api/rows 下发 updated_at → 两个会话先后改同一行 →
后提交者带过期版本必须收到 409，先提交者的改动必须完好。

G6 验收（立项书 §4.7）：「提交后目标被改 → 返回冲突而非静默执行」。
"""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.pop("REGISTRY_INIT_ON_IMPORT", None)
from backend.db_adapter import SQLiteAdapter  # noqa: E402


def _build_db(path: str):
    """按 init_db 的 TEXT PK DDL 建临时库（不 import app，避免连生产库）"""
    a = SQLiteAdapter(path)
    a.connect()
    ts = a.get_current_timestamp_sql()
    for ddl in (
        f"CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'employee', permissions TEXT DEFAULT '[]', global_audit INTEGER DEFAULT 0, theme TEXT DEFAULT NULL, created_at DATETIME DEFAULT ({ts}))",
        "CREATE TABLE IF NOT EXISTS columns_meta (id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, label TEXT NOT NULL, field_type TEXT NOT NULL DEFAULT 'text', options TEXT, position INTEGER DEFAULT 0)",
        f"CREATE TABLE IF NOT EXISTS rows_data (id TEXT PRIMARY KEY, data TEXT NOT NULL DEFAULT '{{}}', created_by TEXT NOT NULL DEFAULT '', schema_version INTEGER NOT NULL DEFAULT 0, created_at DATETIME DEFAULT ({ts}), updated_at DATETIME DEFAULT ({ts}))",
        f"CREATE TABLE IF NOT EXISTS pending_changes (id TEXT PRIMARY KEY, row_id TEXT, column_name TEXT, old_value TEXT, new_value TEXT, change_type TEXT NOT NULL, requested_by TEXT, status TEXT DEFAULT '待审核', reviewed_by TEXT, review_comment TEXT, reviewed_at DATETIME, created_at DATETIME DEFAULT ({ts}))",
        f"CREATE TABLE IF NOT EXISTS operations_log (id TEXT PRIMARY KEY, user_id TEXT, username TEXT, role TEXT, action TEXT, target_type TEXT, target_id TEXT, detail TEXT, created_at DATETIME DEFAULT ({ts}))",
    ):
        a.execute_query(ddl)
    a.insert("users", {"username": "boss", "password_hash": "x", "role": "boss",
                       "permissions": json.dumps(["view_data", "add_data", "edit_data"], ensure_ascii=False)})
    a.insert("columns_meta", {"name": "col_0", "label": "姓名", "field_type": "text", "position": 0})
    a.close()


class TestOptimisticLockApi(unittest.TestCase):
    """409 冲突端到端（Flask test client + 真实 SQLite 临时库）"""

    @classmethod
    def setUpClass(cls):
        import app as appmod  # 项目根目录运行；不会触发 init_db

        cls.appmod = appmod
        cls.tmp = tempfile.mkdtemp(prefix="optlock_")
        cls.db_path = os.path.join(cls.tmp, "t.db")
        _build_db(cls.db_path)
        from backend import config as cfg

        cls._orig_sqlite_path = cfg.SQLITE_PATH
        cfg.SQLITE_PATH = cls.db_path
        appmod.app.config["TESTING"] = True
        cls.client = appmod.app.test_client()

    @classmethod
    def tearDownClass(cls):
        from backend import config as cfg

        cfg.SQLITE_PATH = cls._orig_sqlite_path

    def _login(self):
        # 密码哈希直接写库绕过 hash_password 依赖：这里用已知口令重置
        r = self.client.post("/api/login", json={"username": "boss", "password": "wrong"})
        if r.status_code != 200:
            # 直接把密码哈希写成可校验的形式
            from backend.db_adapter import SQLiteAdapter

            a = SQLiteAdapter(self.db_path)
            a.connect()
            from app import hash_password

            a.execute_query("UPDATE users SET password_hash = ? WHERE username = ?",
                            (hash_password("pw123456"), "boss"))
            a.close()
        r = self.client.post("/api/login", json={"username": "boss", "password": "pw123456"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:200])

    def test_conflict_returns_409_and_keeps_first_write(self):
        self._login()
        # 1. 造一行
        r = self.client.post("/api/rows", json={"col_0": "原始值"})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True)[:200])
        rid = r.get_json()["id"]

        # 2. 读列表拿到 updated_at（版本号随行下发）
        r = self.client.get("/api/rows?page=1&pageSize=10")
        row = next(x for x in r.get_json()["data"] if x["id"] == rid)
        self.assertIn("updated_at", row, "列表未下发乐观锁版本号")
        base = row["updated_at"]

        # 3. A（先提交）成功
        r = self.client.put(f"/api/rows/{rid}", json={"col_0": "A先改", "base_updated_at": base})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:200])

        # 4. B 带着同一旧版本提交 → 必须 409，且 A 的值不被覆盖
        r = self.client.put(f"/api/rows/{rid}", json={"col_0": "B后改", "base_updated_at": base})
        self.assertEqual(r.status_code, 409, f"过期版本未返回 409: {r.status_code} {r.get_data(as_text=True)[:200]}")
        body = r.get_json()
        self.assertTrue(body.get("conflict"))

        # 5. A 的改动完好
        r = self.client.get("/api/rows?page=1&pageSize=10")
        row = next(x for x in r.get_json()["data"] if x["id"] == rid)
        self.assertEqual(row["col_0"], "A先改")

    def test_fresh_version_succeeds(self):
        self._login()
        r = self.client.post("/api/rows", json={"col_0": "第一版"})
        rid = r.get_json()["id"]
        base = next(x for x in self.client.get("/api/rows").get_json()["data"] if x["id"] == rid)["updated_at"]
        time.sleep(0.005)
        r = self.client.put(f"/api/rows/{rid}", json={"col_0": "第二版", "base_updated_at": base})
        self.assertEqual(r.status_code, 200)
        r = self.client.put(f"/api/rows/{rid}", json={"col_0": "第三版",
                                                      "base_updated_at": next(
                                                          x for x in self.client.get("/api/rows").get_json()["data"]
                                                          if x["id"] == rid)["updated_at"]})
        self.assertEqual(r.status_code, 200, "连续两次带新鲜版本提交应都成功")

    def test_legacy_client_without_version_still_works(self):
        """不带 base_updated_at 的旧客户端按原行为处理（不阻断）"""
        self._login()
        r = self.client.post("/api/rows", json={"col_0": "旧客户端"})
        rid = r.get_json()["id"]
        r = self.client.put(f"/api/rows/{rid}", json={"col_0": "旧客户端改"})
        self.assertEqual(r.status_code, 200)

    def test_date_validation_rejects_garbage(self):
        """Phase 3：date 字段垃圾字符串 → 400，不静默入库"""
        self._login()
        from backend.db_adapter import SQLiteAdapter

        a = SQLiteAdapter(self.db_path)
        a.connect()
        a.insert("columns_meta", {"name": "col_1", "label": "入职日期", "field_type": "date", "position": 1})
        a.close()

        r = self.client.post("/api/rows", json={"col_0": "甲", "col_1": "这不是日期"})
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True)[:200])

        # 合法日期各种写法归一化为 YYYY-MM-DD
        for good in ("2024-03-18", "2024/3/18", "2024.3.18"):
            r = self.client.post("/api/rows", json={"col_0": "乙", "col_1": good})
            self.assertEqual(r.status_code, 201, f"{good}: {r.get_data(as_text=True)[:200]}")
        r = self.client.get("/api/rows?page=1&pageSize=50")
        got = {x["col_0"]: x["col_1"] for x in r.get_json()["data"]}
        self.assertEqual(got.get("乙"), "2024-03-18")


if __name__ == "__main__":
    unittest.main()
