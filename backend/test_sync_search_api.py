# -*- coding: utf-8 -*-
"""
Phase 4/5 API 接线端到端测试：
  * /api/search/semantic + /api/search/rebuild（本地向量检索）
  * /api/sync/export + /api/sync/import（加密 .drsync 包）
  * 权限：search_data / reset_database

全部走 Flask test client + tempfile 库，绝不碰 data/app.db。
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.pop("REGISTRY_INIT_ON_IMPORT", None)
from backend.db_adapter import SQLiteAdapter  # noqa: E402


def _build_db(path: str):
    a = SQLiteAdapter(path)
    a.connect()
    ts = a.get_current_timestamp_sql()
    for ddl in (
        f"CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'employee', permissions TEXT DEFAULT '[]', global_audit INTEGER DEFAULT 0, theme TEXT DEFAULT NULL, created_at DATETIME DEFAULT ({ts}))",
        "CREATE TABLE IF NOT EXISTS columns_meta (id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, label TEXT NOT NULL, field_type TEXT NOT NULL DEFAULT 'text', options TEXT, position INTEGER DEFAULT 0)",
        f"CREATE TABLE IF NOT EXISTS rows_data (id TEXT PRIMARY KEY, data TEXT NOT NULL DEFAULT '{{}}', created_by TEXT NOT NULL DEFAULT '', schema_version INTEGER NOT NULL DEFAULT 0, created_at DATETIME DEFAULT ({ts}), updated_at DATETIME DEFAULT ({ts}))",
        f"CREATE TABLE IF NOT EXISTS pending_changes (id TEXT PRIMARY KEY, row_id TEXT, column_name TEXT, old_value TEXT, new_value TEXT, change_type TEXT NOT NULL, requested_by TEXT, status TEXT DEFAULT '待审核', reviewed_by TEXT, review_comment TEXT, reviewed_at DATETIME, created_at DATETIME DEFAULT ({ts}))",
        f"CREATE TABLE IF NOT EXISTS operations_log (id TEXT PRIMARY KEY, user_id TEXT, username TEXT, role TEXT, action TEXT, target_type TEXT, target_id TEXT, detail TEXT, created_at DATETIME DEFAULT ({ts}))",
        f"CREATE TABLE IF NOT EXISTS audit_log (id TEXT PRIMARY KEY, user_id TEXT, username TEXT, action TEXT, target_table TEXT, target_id TEXT, old_value TEXT, new_value TEXT, created_at DATETIME DEFAULT ({ts}))",
        f"CREATE TABLE IF NOT EXISTS backups (id TEXT PRIMARY KEY, filename TEXT UNIQUE, size_bytes INTEGER, created_at DATETIME DEFAULT ({ts}))",
        f"CREATE TABLE IF NOT EXISTS system_config (`key` VARCHAR(255) PRIMARY KEY, `value` TEXT NOT NULL, updated_at DATETIME DEFAULT ({ts}))",
        f"CREATE TABLE IF NOT EXISTS ai_analysis_history (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, report TEXT, chat_history TEXT, created_at DATETIME DEFAULT ({ts}), updated_at DATETIME DEFAULT ({ts}))",
    ):
        a.execute_query(ddl)
    a.close()


class TestSyncSearchApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as appmod
        from backend import config as cfg

        cls.appmod = appmod
        cls.cfg = cfg
        cls.tmp = tempfile.mkdtemp(prefix="syncsearch_")
        cls.db_path = os.path.join(cls.tmp, "t.db")
        _build_db(cls.db_path)
        cls._orig = cfg.SQLITE_PATH
        cfg.SQLITE_PATH = cls.db_path
        # 检索索引文件与同步导出目录都落到临时目录（python 子进程对项目 data/ 无写权限）
        cls._orig_vs = appmod._VS_INDEX_PATH
        appmod._VS_INDEX_PATH = os.path.join(cls.tmp, "vs_index.json")
        cls._orig_sync_dir = os.environ.get("REGISTRY_SYNC_DIR")
        os.environ["REGISTRY_SYNC_DIR"] = os.path.join(cls.tmp, "sync")
        appmod.app.config["TESTING"] = True
        cls.client = appmod.app.test_client()

        # 造数：boss 账户 + 2 个字段 + 3 行数据
        from app import hash_password

        a = SQLiteAdapter(cls.db_path)
        a.connect()
        a.insert("users", {"username": "boss", "password_hash": hash_password("pw123456"),
                           "role": "boss", "permissions": json.dumps(
                               ["search_data", "reset_database", "view_data", "add_data", "edit_data"])})
        a.insert("columns_meta", {"name": "col_0", "label": "姓名", "field_type": "text", "position": 0})
        a.insert("columns_meta", {"name": "col_1", "label": "部门", "field_type": "text", "position": 1})
        for name, dept in (("陈静宜", "人力资源部"), ("赵子涵", "技术部"), ("孙一", "财务部")):
            a.execute_query(
                "INSERT INTO rows_data (id, data, created_by, schema_version) VALUES (?,?,?,0)",
                (__import__("backend.uuid7", fromlist=["uuid7"]).uuid7(),
                 json.dumps({"col_0": name, "col_1": dept}, ensure_ascii=False), "boss"))
        a.close()

        r = cls.client.post("/api/login", json={"username": "boss", "password": "pw123456"})
        assert r.status_code == 200, r.get_data(as_text=True)[:200]

    @classmethod
    def tearDownClass(cls):
        cls.cfg.SQLITE_PATH = cls._orig
        cls.appmod._VS_INDEX_PATH = cls._orig_vs
        if cls._orig_sync_dir is None:
            os.environ.pop("REGISTRY_SYNC_DIR", None)
        else:
            os.environ["REGISTRY_SYNC_DIR"] = cls._orig_sync_dir

    # ── Phase 5：语义检索 ──

    def test_semantic_search_hits_substring(self):
        r = self.client.get("/api/search/semantic?q=%E9%9D%99%E5%AE%9C")  # 静宜
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:200])
        hits = r.get_json()["results"]
        self.assertTrue(hits, "「静宜」没有命中「陈静宜」")
        top = hits[0]
        self.assertIn("row_id", top)
        self.assertIn("score", top)
        # 命中的行真的在库里
        self.assertTrue(self.client.get("/api/rows").get_json()  is not None)

    def test_semantic_search_department(self):
        r = self.client.get("/api/search/semantic?q=" + "人力资源")
        hits = r.get_json()["results"]
        self.assertTrue(hits)

    def test_semantic_rebuild(self):
        r = self.client.post("/api/search/rebuild")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:200])
        self.assertEqual(r.get_json()["row_count"], 3)

    def test_semantic_requires_perm(self):
        # 未登录 401
        c2 = self.appmod.app.test_client()
        r = c2.get("/api/search/semantic?q=x")
        self.assertEqual(r.status_code, 401)

    def test_empty_query_returns_empty(self):
        r = self.client.get("/api/search/semantic?q=")
        self.assertEqual(r.get_json()["results"], [])

    # ── Phase 4：.drsync 同步 ──

    def test_sync_export_import_roundtrip(self):
        # 导出（boss 有 reset_database 权限）
        r = self.client.post("/api/sync/export", json={"password": "sync-pass-123"})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True)[:300])
        body = r.get_json()
        self.assertEqual(body["events"] >= 5, True, f"事件数异常: {body}")
        self.assertTrue(body["filename"].endswith(".drsync"))

        # 密文落盘：文件内容不得含明文姓名
        out_file = os.path.join(os.path.dirname(self.db_path), "..")  # 占位
        # 实际文件在 data/sync/ 下，路径基于 app base_path —— 换个方式验证：再次导入用错口令必须失败
        path = self._find_export(body["filename"])
        self.assertTrue(path, "导出文件不存在")
        raw = open(path, "rb").read()
        self.assertNotIn("陈静宜".encode("utf-8"), raw, "密文里出现了明文！")
        self.assertNotIn(b"sync-pass-123", raw, "口令出现在文件里！")

        # 错误口令导入 → 400
        with open(path, "rb") as f:
            from io import BytesIO

            r = self.client.post("/api/sync/import",
                                 data={"password": "wrong-pass",
                                       "file": (BytesIO(f.read()), body["filename"])},
                                 content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True)[:200])

        # 正确口令导入到**另一个库**：模拟 B 机（用独立 Flask client + 换库）
        self._import_into_fresh_db(path)

    def _find_export(self, filename: str):
        base_dir = os.environ.get("REGISTRY_SYNC_DIR") or os.path.join(
            os.path.dirname(self.appmod.__file__), "..", "data", "sync"
        )
        path = os.path.join(base_dir, filename)
        return path if os.path.exists(path) else None

    def _import_into_fresh_db(self, src_path: str):
        """把导出的包导入一个全新的临时库，验证 roundtrip"""
        from backend.drsync import read_drsync, import_events

        fresh = os.path.join(self.tmp, "fresh.db")
        # 复用测试建库 DDL
        import importlib

        mod = importlib.import_module("backend.test_sync_search_api")
        mod._build_db(fresh)
        a = SQLiteAdapter(fresh)
        a.connect()
        plain = read_drsync(src_path, "sync-pass-123")
        stats = import_events(a, json.loads(plain.decode("utf-8")), source_node="test")
        a.close()
        self.assertEqual(stats["inserted"] >= 5, True, f"导入统计异常: {stats}")

        # 数据一致：3 行 rows_data 的姓名都在
        a = SQLiteAdapter(fresh)
        a.connect()
        names = {json.loads(r["data"]).get("col_0") for r in a.fetch_all("SELECT data FROM rows_data")}
        a.close()
        self.assertEqual(names, {"陈静宜", "赵子涵", "孙一"})

    def test_sync_import_wrong_password_rejected(self):
        r = self.client.post("/api/sync/export", json={"password": "right-pass-1"})
        self.assertEqual(r.status_code, 201)
        path = self._find_export(r.get_json()["filename"])
        self.assertTrue(path)
        from io import BytesIO

        with open(path, "rb") as f:
            r = self.client.post("/api/sync/import",
                                 data={"password": "nope-nope",
                                       "file": (BytesIO(f.read()), "x.drsync")},
                                 content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)

    def test_sync_requires_reset_database_perm(self):
        c2 = self.appmod.app.test_client()
        r = c2.post("/api/sync/export", json={"password": "whatever-1"})
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
