# -*- coding: utf-8 -*-
"""
UUIDv7 迁移测试（Phase 2b）
==========================

覆盖（对应 backend/migrate_uuid7.py 的锁定语义）：
  * dry-run 不修改任何数据
  * 幂等：第二次执行直接跳过（already-migrated）
  * 8 张表行数 + 非 id 列值完全保留
  * 8 张表 id 全变为合法 uuid7，且旧 int→新 uuid 一一映射、无碰撞
  * FK 改写：pending_changes.requested_by/reviewed_by、
    operations_log.user_id、audit_log.user_id、ai_analysis_history.user_id
  * pending_changes.row_id 多态：insert/update/delete→rows_data，
    add_user/update_user/delete_user→users，其余类型保持 NULL
  * 未知 change_type 的 row_id 原样保留（不置 NULL，靠悬空检查暴露）
  * operations_log/audit_log.target_id 多态：
    rows_data/users/pending_changes 按映射改写；
    columns_meta（列名字符串键 col_x）与其它字符串键原样保留
  * JSON 内嵌 id：new_value/old_value 里 {"id": int} 按 change_type 改写
  * 悬空 FK 会中止迁移且旧表保持原样
  * 显式索引在改名后重建（SQLite RENAME 会把索引带到 legacy 表）
  * legacy 旧表保留且可读
  * verify 报告结构

运行方式（项目根目录）:
    python -m pytest backend/test_uuid7.py -v --timeout=60
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import migrate_uuid7 as M
from backend.db_adapter import SQLiteAdapter
from backend.uuid7 import is_valid_uuid7


def build_int_pk_db(path):
    """构造 8 张整数 PK 表 + 有代表性的外键/多态/JSON 数据"""
    a = SQLiteAdapter(path)
    a.connect()
    a.execute_query(
        "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, "
        "role TEXT NOT NULL DEFAULT 'employee', global_audit INTEGER DEFAULT 0)"
    )
    a.execute_query(
        "CREATE TABLE columns_meta (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT UNIQUE NOT NULL, label TEXT NOT NULL, "
        "field_type TEXT NOT NULL DEFAULT 'text', position INTEGER DEFAULT 0)"
    )
    a.execute_query(
        "CREATE TABLE rows_data (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "data TEXT NOT NULL DEFAULT '{}', created_by TEXT NOT NULL DEFAULT '', "
        "schema_version INTEGER NOT NULL DEFAULT 0)"
    )
    a.execute_query(
        "CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER, username TEXT, action TEXT, "
        "target_table TEXT, target_id TEXT, old_value TEXT, new_value TEXT)"
    )
    a.execute_query(
        "CREATE TABLE pending_changes (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "row_id INTEGER, column_name TEXT, old_value TEXT, new_value TEXT, "
        "change_type TEXT NOT NULL, requested_by INTEGER, "
        "status TEXT DEFAULT '待审核', reviewed_by INTEGER)"
    )
    a.execute_query(
        "CREATE TABLE operations_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER, username TEXT, role TEXT, action TEXT, "
        "target_type TEXT, target_id TEXT, detail TEXT)"
    )
    a.execute_query(
        "CREATE TABLE backups (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "filename TEXT UNIQUE, size_bytes INTEGER)"
    )
    a.execute_query(
        "CREATE TABLE ai_analysis_history (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER NOT NULL, report TEXT)"
    )
    # 显式索引：迁移后必须重建到新表上（改名会把它们带到 legacy 表）
    a.execute_query("CREATE INDEX idx_rows_data_created_by ON rows_data(created_by)")
    a.execute_query("CREATE INDEX idx_ops_target ON operations_log(target_type)")

    # ── 数据 ──
    a.execute_query("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                    ("boss", "h1", "boss"))          # id=1
    a.execute_query("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                    ("alice", "h2", "employee"))     # id=2
    a.execute_query("INSERT INTO columns_meta (name,label,position) VALUES (?,?,?)",
                    ("col_0", "姓名", 0))            # id=1
    a.execute_query("INSERT INTO rows_data (data, created_by) VALUES (?,?)",
                    ('{"姓名": "A"}', "boss"))       # id=1
    a.execute_query("INSERT INTO rows_data (data, created_by) VALUES (?,?)",
                    ('{"姓名": "B"}', "alice"))      # id=2
    # pending: insert 行（row_id→rows_data#2，JSON 内嵌 rows_data id）
    a.execute_query(
        "INSERT INTO pending_changes (row_id, new_value, change_type, requested_by, status) "
        "VALUES (?,?,?,?,?)",
        (2, json.dumps({"id": 2, "姓名": "B2"}, ensure_ascii=False),
         "insert", 1, "待审核"),
    )  # id=1
    # pending: update_user 行（row_id→users#2，JSON 内嵌 users id）
    a.execute_query(
        "INSERT INTO pending_changes (row_id, new_value, change_type, requested_by, "
        "reviewed_by, status) VALUES (?,?,?,?,?,?)",
        (2, json.dumps({"id": 2, "role": "boss"}, ensure_ascii=False),
         "update_user", 1, 1, "待审核"),
    )  # id=2
    # pending: add_column 行（row_id NULL）
    a.execute_query(
        "INSERT INTO pending_changes (row_id, column_name, new_value, change_type, "
        "requested_by, status) VALUES (?,?,?,?,?,?)",
        (None, "__new_column__", json.dumps({"label": "电话"}, ensure_ascii=False),
         "add_column", 2, "待审核"),
    )  # id=3
    # operations_log：整数 target_id + 列名字符串键 + 纯字符串键
    a.execute_query(
        "INSERT INTO operations_log (user_id, username, action, target_type, target_id) "
        "VALUES (?,?,?,?,?)",
        (1, "boss", "新增行", "rows_data", "2"),
    )
    a.execute_query(
        "INSERT INTO operations_log (user_id, username, action, target_type, target_id) "
        "VALUES (?,?,?,?,?)",
        (2, "alice", "添加字段", "columns_meta", "col_0"),
    )
    a.execute_query(
        "INSERT INTO operations_log (user_id, username, action, target_type, target_id) "
        "VALUES (?,?,?,?,?)",
        (1, "boss", "备份", "backup", "full_2024.db"),
    )
    # audit_log：整数 target_id
    a.execute_query(
        "INSERT INTO audit_log (user_id, username, action, target_table, target_id) "
        "VALUES (?,?,?,?,?)",
        (2, "alice", "改用户", "users", "2"),
    )
    a.execute_query("INSERT INTO backups (filename, size_bytes) VALUES (?,?)",
                    ("full_2024.db", 100))
    a.execute_query("INSERT INTO ai_analysis_history (user_id, report) VALUES (?,?)",
                    (1, "r1"))
    return a


class TestUuid7MigrateHappyPath(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="uuid7_")
        self.path = os.path.join(self.tmp, "t.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_full_remap(self):
        a = build_int_pk_db(self.path)
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        self.assertFalse(M.is_migrated(db))
        stats = M.migrate(db)
        self.assertEqual(stats["status"], "migrated")
        self.assertTrue(M.is_migrated(db))

        # ── id 全是合法 uuid7，且表内无碰撞 ──
        for t in M.PK_TABLES:
            ids = [r["id"] for r in db.fetch_all(f"SELECT id FROM {t}")]
            self.assertTrue(ids, f"{t} 不应为空")
            for v in ids:
                self.assertTrue(is_valid_uuid7(str(v)), f"{t}.id={v} 非法 uuid7")
            self.assertEqual(len(set(str(v) for v in ids)), len(ids), f"{t} id 碰撞")

        # ── 行数保留 ──
        self.assertEqual(db.fetch_one("SELECT COUNT(*) AS c FROM users")["c"], 2)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) AS c FROM rows_data")["c"], 2)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) AS c FROM pending_changes")["c"], 3)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) AS c FROM operations_log")["c"], 3)

        # ── 取映射：旧 1/2 → 新 uuid ──
        users = {r["username"]: r["id"] for r in db.fetch_all("SELECT id, username FROM users")}
        rows = db.fetch_all("SELECT id, data FROM rows_data ORDER BY data")
        # rows_data 按 data 排序：A 在前（旧 id=1），B 在后（旧 id=2）
        row_uuid_1, row_uuid_2 = rows[0]["id"], rows[1]["id"]

        # ── FK 改写 ──
        pc = db.fetch_all("SELECT * FROM pending_changes ORDER BY id")
        # 注意：pending_changes 自身 id 已变，改按 change_type 区分
        by_ct = {r["change_type"]: r for r in pc}
        self.assertEqual(str(by_ct["insert"]["requested_by"]), str(users["boss"]))
        self.assertEqual(str(by_ct["insert"]["row_id"]), str(row_uuid_2))
        self.assertEqual(str(by_ct["update_user"]["row_id"]), str(users["alice"]))
        self.assertEqual(str(by_ct["update_user"]["reviewed_by"]), str(users["boss"]))
        self.assertIsNone(by_ct["add_column"]["row_id"])

        # ── JSON 内嵌 id 改写 ──
        ins_json = json.loads(by_ct["insert"]["new_value"])
        self.assertEqual(str(ins_json["id"]), str(row_uuid_2))
        upd_json = json.loads(by_ct["update_user"]["new_value"])
        self.assertEqual(str(upd_json["id"]), str(users["alice"]))

        # ── target_id 多态 ──
        # 注意：迁移后 id 是 uuid 字符串，ORDER BY id 不再是插入顺序，
        # 改按 target_type 区分三行。
        ops = {r["target_type"]: r
               for r in db.fetch_all("SELECT * FROM operations_log")}
        self.assertEqual(str(ops["rows_data"]["target_id"]), str(row_uuid_2))  # 改写
        self.assertEqual(str(ops["rows_data"]["user_id"]), str(users["boss"]))
        self.assertEqual(ops["columns_meta"]["target_id"], "col_0")  # 列名字符串键保留
        self.assertEqual(ops["backup"]["target_id"], "full_2024.db")  # 纯字符串键保留
        au = db.fetch_all("SELECT * FROM audit_log")
        self.assertEqual(str(au[0]["target_id"]), str(users["alice"]))
        self.assertEqual(str(au[0]["user_id"]), str(users["alice"]))
        ai = db.fetch_all("SELECT * FROM ai_analysis_history")
        self.assertEqual(str(ai[0]["user_id"]), str(users["boss"]))

        # ── 非 id 列值保留 ──
        self.assertEqual(json.loads(rows[0]["data"])["姓名"], "A")
        self.assertEqual(
            db.fetch_one("SELECT label FROM columns_meta")["label"], "姓名")

        # ── 索引重建到新表 ──
        idx_rows = db.fetch_all(
            "SELECT name, tbl_name FROM sqlite_master "
            "WHERE type='index' AND name IN ('idx_rows_data_created_by','idx_ops_target')"
        )
        tbl_of = {r["name"]: r["tbl_name"] for r in idx_rows}
        self.assertEqual(tbl_of.get("idx_rows_data_created_by"), "rows_data")
        self.assertEqual(tbl_of.get("idx_ops_target"), "operations_log")

        # ── legacy 旧表保留 ──
        for t, leg in stats["legacy_tables"].items():
            cnt = db.fetch_one(f"SELECT COUNT(*) AS c FROM {leg}")["c"]
            self.assertGreaterEqual(cnt, 1, f"{leg} 应保留旧数据")
        db.close()

    def test_unknown_change_type_row_id_passthrough(self):
        """未知 change_type 的 row_id 原样保留（不置 NULL）"""
        a = build_int_pk_db(self.path)
        a.execute_query(
            "INSERT INTO pending_changes (row_id, change_type, requested_by, status) "
            "VALUES (?,?,?,?)",
            (999, "mystery_type", 1, "待审核"),
        )
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        stats = M.migrate(db)
        self.assertEqual(stats["status"], "migrated")
        row = db.fetch_one(
            "SELECT row_id FROM pending_changes WHERE change_type='mystery_type'")
        self.assertEqual(str(row["row_id"]), "999")
        db.close()

    def test_legacy_rollback_readable(self):
        a = build_int_pk_db(self.path)
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        stats = M.migrate(db)
        leg = stats["legacy_tables"]["users"]
        old = db.fetch_all(f"SELECT id, username FROM {leg} ORDER BY id")
        self.assertEqual([r["username"] for r in old], ["boss", "alice"])
        self.assertEqual([r["id"] for r in old], [1, 2])
        db.close()


class TestUuid7Guards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="uuid7_")
        self.path = os.path.join(self.tmp, "t.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dry_run_changes_nothing(self):
        a = build_int_pk_db(self.path)
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        stats = M.migrate(db, dry_run=True)
        self.assertEqual(stats["status"], "dry-run")
        self.assertFalse(M.is_migrated(db))
        # 数据原样：整数 id 还在
        row = db.fetch_one("SELECT id FROM users ORDER BY id LIMIT 1")
        self.assertEqual(row["id"], 1)
        self.assertFalse(M.table_exists(db, "users_new"))
        db.close()

    def test_second_run_is_noop(self):
        a = build_int_pk_db(self.path)
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        M.migrate(db)
        n1 = db.fetch_one("SELECT COUNT(*) AS c FROM rows_data")["c"]
        stats2 = M.migrate(db)
        self.assertEqual(stats2["status"], "already-migrated")
        n2 = db.fetch_one("SELECT COUNT(*) AS c FROM rows_data")["c"]
        self.assertEqual(n1, n2)
        db.close()

    def test_dangling_fk_is_repaired_to_null(self):
        """
        悬空 FK（指向不存在的旧 id）应被置 NULL 并记录，而不是卡住整库迁移。

        线上实测：`operations_log.user_id=99999` 对应用户早已删除。这类行本身是
        有效留痕，属于历史脏值；整库迁移不该被一行失效引用阻断。
        """
        a = build_int_pk_db(self.path)
        # operations_log.user_id=999 不存在 → 改写后仍是 999 → 悬空
        a.execute_query(
            "INSERT INTO operations_log (user_id, username, action) VALUES (?,?,?)",
            (999, "ghost", "x"),
        )
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        stats = M.migrate(db)
        self.assertEqual(stats["status"], "migrated")
        self.assertTrue(stats.get("repaired_fks"), "应记录修复明细")
        self.assertTrue(M.is_migrated(db))

        # 悬空引用已断，行本身仍在（数据不丢）
        ghosts = db.fetch_all(
            "SELECT user_id, username FROM operations_log WHERE username = ?", ("ghost",)
        )
        self.assertEqual(len(ghosts), 1)
        self.assertIsNone(ghosts[0]["user_id"])

        # 修复后校验应无悬空
        v = M.verify(db)
        self.assertEqual(v.get("dangling"), [])
        db.close()

    def test_verify_report(self):
        a = build_int_pk_db(self.path)
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        v0 = M.verify(db)
        self.assertFalse(v0["is_migrated"])
        self.assertFalse(v0["ok"])
        M.migrate(db)
        v1 = M.verify(db)
        self.assertTrue(v1["is_migrated"])
        self.assertTrue(v1["ok"])
        self.assertEqual(v1["tables"]["users"]["row_count"], 2)
        db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
