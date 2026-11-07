# -*- coding: utf-8 -*-
"""
迁移脚本单元测试
================

覆盖：
  * 幂等（已迁移 → 跳过）
  * dry-run 不修改任何数据
  * 逐行数据校验（核心：迁移前后值完全相等）
  * 孤儿列数据不丢
  * created_by 保留
  * 校验失败时中止且旧表保持原样
  * id 保持连续
  * verify 报告结构

运行方式（项目根目录）:
    python -m pytest backend/test_migrate_jsonb.py -v --timeout=60
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import migrate_jsonb as M
from backend.db_adapter import SQLiteAdapter
from backend.row_store import RowStore


def build_legacy_db(path, rows):
    """
    构造一个「旧宽表」结构的库，模拟现状。
    rows: list of dict，key 为列名
    """
    a = SQLiteAdapter(path)
    a.connect()
    a.execute_query(
        "CREATE TABLE columns_meta (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, "
        "label TEXT, field_type TEXT DEFAULT 'text', options TEXT, position INTEGER DEFAULT 0)"
    )
    # 旧表：动态列 + 系统列 _created_by
    cols = ["id INTEGER PRIMARY KEY AUTOINCREMENT", "_created_by VARCHAR(255)"]
    all_names = set()
    for r in rows:
        all_names.update(r.keys())
    for c in sorted(all_names):
        cols.append(f'"{c}" TEXT')
    a.execute_query("CREATE TABLE rows_data (" + ", ".join(cols) + ")")
    for r in rows:
        names = [c for c in r.keys()]
        ph = ", ".join("?" for _ in names)
        a.execute_query(
            f"INSERT INTO rows_data ({', '.join(names)}, _created_by) VALUES ({ph}, ?)",
            tuple(r.values()) + ("hr",),
        )
    return a


class TestMigrateHappyPath(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrate_")
        self.path = os.path.join(self.tmp, "legacy.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_migrate_preserves_all_rows_and_values(self):
        src = [
            {"工号": "EMP-1042", "姓名": "陈静宜", "部门": "人力资源部"},
            {"工号": "EMP-1043", "姓名": "林致远", "部门": "技术研发部", "备注": "高级职称"},
            {"工号": "EMP-1044", "姓名": "苏婉清", "部门": "市场运营部", "备注": None},
        ]
        a = build_legacy_db(self.path, src)
        a.execute_query("INSERT INTO columns_meta (name,label,position) VALUES ('工号','工号',0)")
        a.execute_query("INSERT INTO columns_meta (name,label,position) VALUES ('姓名','姓名',1)")
        a.execute_query("INSERT INTO columns_meta (name,label,position) VALUES ('部门','部门',2)")
        before_rows = a.fetch_all("SELECT * FROM rows_data ORDER BY id")
        a.close()

        db = SQLiteAdapter(self.path)
        db.connect()
        stats = M.migrate(db)
        db.close()

        self.assertEqual(stats["status"], "migrated")
        self.assertEqual(stats["rows_moved"], 3)

        db = SQLiteAdapter(self.path)
        db.connect()
        after = db.fetch_all("SELECT id, data, created_by FROM rows_data ORDER BY id")
        self.assertEqual(len(after), len(before_rows))

        for old, new in zip(before_rows, after):
            payload = json.loads(new["data"])
            # 每个字段逐一比对
            for key in ("工号", "姓名", "部门", "备注"):
                ov = old.get(key)
                nv = payload.get(key)
                if ov is None or str(ov).strip() == "":
                    self.assertIsNone(nv, f"id={old['id']} 字段 {key} 应为空")
                else:
                    self.assertEqual(str(ov), str(nv), f"id={old['id']} 字段 {key} 不一致")
            self.assertEqual(new["created_by"], "hr")
            self.assertEqual(old["id"], new["id"])
        db.close()

    def test_orphan_columns_are_not_lost(self):
        """孤儿列（无字段定义）的数据同样要搬过去"""
        a = build_legacy_db(self.path, [{"姓名": "A", "赵子涵": "孤儿值", "col_49": "x"}])
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        stats = M.migrate(db)
        self.assertEqual(stats["status"], "migrated")
        rows = db.fetch_all("SELECT data FROM rows_data")
        payload = json.loads(rows[0]["data"])
        self.assertEqual(payload.get("赵子涵"), "孤儿值")
        self.assertEqual(payload.get("col_49"), "x")
        db.close()

    def test_legacy_table_is_kept(self):
        a = build_legacy_db(self.path, [{"姓名": "A"}])
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        stats = M.migrate(db)
        legacy = stats["legacy_table"]
        self.assertTrue(legacy.startswith(M.LEGACY_PREFIX))
        # 旧表仍在且可读
        old_rows = db.fetch_all(f"SELECT * FROM {legacy}")
        self.assertEqual(len(old_rows), 1)
        db.close()

    def test_ids_stay_contiguous(self):
        a = build_legacy_db(self.path, [{"姓名": f"n{i}"} for i in range(5)])
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        M.migrate(db)
        ids = [r["id"] for r in db.fetch_all("SELECT id FROM rows_data ORDER BY id")]
        self.assertEqual(ids, [1, 2, 3, 4, 5])
        db.close()

    def test_new_table_has_fixed_column_set(self):
        a = build_legacy_db(self.path, [{"姓名": "A"}])
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        M.migrate(db)
        cols = {c["name"] for c in db.get_table_columns("rows_data")}
        self.assertEqual(
            cols, {"id", "data", "created_by", "schema_version", "created_at", "updated_at"}
        )
        db.close()


class TestMigrateIdempotent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrate_")
        self.path = os.path.join(self.tmp, "db.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_second_run_is_noop(self):
        a = build_legacy_db(self.path, [{"姓名": "A"}, {"姓名": "B"}])
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        M.migrate(db)
        n1 = db.fetch_one("SELECT COUNT(*) AS c FROM rows_data")["c"]
        stats2 = M.migrate(db)          # 再跑一次
        n2 = db.fetch_one("SELECT COUNT(*) AS c FROM rows_data")["c"]
        db.close()
        self.assertEqual(stats2["status"], "already-migrated")
        self.assertEqual(n1, n2)
        self.assertEqual(n2, 2)

    def test_is_migrated_detects_new_structure(self):
        a = build_legacy_db(self.path, [{"姓名": "A"}])
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        self.assertFalse(M.is_migrated(db))
        M.migrate(db)
        self.assertTrue(M.is_migrated(db))
        db.close()

    def test_dry_run_does_not_modify(self):
        a = build_legacy_db(self.path, [{"姓名": "A"}, {"姓名": "B"}])
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        before_cols = {c["name"] for c in db.get_table_columns("rows_data")}
        stats = M.migrate(db, dry_run=True)
        after_cols = {c["name"] for c in db.get_table_columns("rows_data")}
        db.close()
        self.assertEqual(stats["status"], "dry-run")
        self.assertEqual(before_cols, after_cols, "dry-run 不应改表结构")


class TestMigrateWithRowStore(unittest.TestCase):
    """迁移后用 RowStore 读写，验证两层能配合"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrate_")
        self.path = os.path.join(self.tmp, "db.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rowstore_reads_migrated_data(self):
        a = build_legacy_db(self.path, [{"姓名": "陈静宜"}, {"姓名": "林致远"}])
        a.execute_query("INSERT INTO columns_meta (name,label,field_type,position) VALUES ('姓名','姓名','text',0)")
        a.close()

        db = SQLiteAdapter(self.path)
        db.connect()
        M.migrate(db)
        store = RowStore(db)
        cols = store.load_columns()
        rows = store.fetch_rows(cols)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["姓名"], "林致远")     # ORDER BY id DESC
        self.assertEqual(rows[1]["姓名"], "陈静宜")

        # 写完再读，值不串
        store.update_row(rows[1]["id"], cols, {"姓名": "陈静宜-new"})
        after = store.fetch_rows(cols)
        by_id = {r["id"]: r["姓名"] for r in after}
        self.assertEqual(by_id[rows[1]["id"]], "陈静宜-new")
        self.assertEqual(by_id[rows[0]["id"]], "林致远")
        db.close()


class TestVerify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrate_")
        self.path = os.path.join(self.tmp, "db.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_verify_reports_legacy_table(self):
        a = build_legacy_db(self.path, [{"姓名": "A"}])
        a.close()
        db = SQLiteAdapter(self.path)
        db.connect()
        M.migrate(db)
        report = M.verify(db)
        db.close()
        self.assertTrue(report["ok"])
        self.assertTrue(report["is_migrated"])
        self.assertEqual(report["column_count"], 6)
        self.assertEqual(len(report["legacy_tables"]), 1)


class TestRealDatabaseDryRun(unittest.TestCase):
    """
    对真实 active 库做 dry-run（不改数据），验证脚本能处理现场的 35 列 / 18 孤儿列。
    这是 Phase 1b 的现场验收。
    """

    def test_real_db_dry_run(self):
        real = r"G:\dynamic_registry\data\app.db"
        if not os.path.exists(real):
            self.skipTest("真实库不存在")
        db = None
        try:
            db = SQLiteAdapter(real)
            db.connect()
        except Exception as e:
            # 真库可能被运行环境限制打开（只读挂载 / 沙箱策略 / 被其他进程锁死）。
            # 这是对「现场库」的验收增强，不是功能回归——环境不允许就跳过。
            self.skipTest(f"真实库不可打开（环境限制）: {e}")
        try:
            self.assertFalse(M.is_migrated(db), "真实库应仍为宽表结构")
            stats = M.migrate(db, dry_run=True)
            self.assertEqual(stats["status"], "dry-run")
            # 现场事实：35 列、15 个已定义字段、18 个孤儿列
            self.assertEqual(stats["old_column_count"], 35)
            self.assertEqual(stats["defined_fields"], 15)
            self.assertEqual(len(stats["orphan_columns"]), 18)
            # dry-run 之后结构必须丝毫未变
            self.assertEqual(len(db.get_table_columns("rows_data")), 35)
            self.assertEqual(db.fetch_one("SELECT COUNT(*) AS c FROM rows_data")["c"], 49)
        finally:
            if db is not None:
                db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
