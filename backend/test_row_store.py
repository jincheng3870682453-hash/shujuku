# -*- coding: utf-8 -*-
"""
RowStore 单元测试
=================

覆盖 JSONB 存储层的关键行为：
  * 字段定义读取与 options 反序列化
  * 读写往返（insert → fetch）的类型保真
  * 部分更新 merge 语义
  * schema_version 随字段结构变化
  * count / delete / batch_delete
  * json_path 的注入防御
  * 空字段表不炸

运行方式（必须从项目根目录，见 docs/立项-存储层重构.md §0.5）:
    python -m pytest backend/test_row_store.py -v --timeout=60
"""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.db_adapter import SQLiteAdapter
from backend.row_store import RowStore, RowStoreError, json_path, SYSTEM_COLUMNS


def make_store(tmpdir):
    """建一个带新表结构的临时 SQLite 库，返回 (adapter, store)"""
    adapter = SQLiteAdapter(os.path.join(tmpdir, "rowstore_test.db"))
    adapter.connect()
    adapter.execute_query(
        """
        CREATE TABLE IF NOT EXISTS columns_meta (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            field_type TEXT NOT NULL DEFAULT 'text',
            options TEXT,
            position INTEGER DEFAULT 0,
            is_indexed INTEGER DEFAULT 0
        )
        """
    )
    adapter.execute_query(
        """
        CREATE TABLE IF NOT EXISTS rows_data (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL DEFAULT '{}',
            created_by TEXT NOT NULL DEFAULT '',
            schema_version INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT (datetime('now')),
            updated_at DATETIME DEFAULT (datetime('now'))
        )
        """
    )
    return adapter, RowStore(adapter)


def add_column(adapter, name, label, field_type, position, options=None):
    adapter.execute_query(
        "INSERT INTO columns_meta (name, label, field_type, options, position) VALUES (?,?,?,?,?)",
        (name, label, field_type, json.dumps(options, ensure_ascii=False) if options is not None else None, position),
    )


class TestJsonPath(unittest.TestCase):
    """json_path 必须挡住注入"""

    def test_normal_name(self):
        self.assertEqual(json_path("col_0"), "$.col_0")
        self.assertEqual(json_path("姓名"), "$.姓名")
        self.assertEqual(json_path("入职日期"), "$.入职日期")

    def test_rejects_injection_chars(self):
        for bad in ["a'b", "a\"b", "a$b", "a.b", "a[b]", "a\\b", "a\nb", "a\tb"]:
            with self.assertRaises(ValueError, msg=bad):
                json_path(bad)

    def test_rejects_empty_and_too_long(self):
        with self.assertRaises(ValueError):
            json_path("")
        with self.assertRaises(ValueError):
            json_path("x" * 300)


class TestLoadColumns(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rowstore_")
        self.adapter, self.store = make_store(self.tmp)

    def tearDown(self):
        self.adapter.close()

    def test_empty_table_returns_empty(self):
        self.assertEqual(self.store.load_columns(), [])

    def test_orders_by_position_and_parses_options(self):
        add_column(self.adapter, "状态", "状态", "select", 5, options=["在职", "离职"])
        add_column(self.adapter, "工号", "工号", "text", 0)
        cols = self.store.load_columns()
        self.assertEqual([c["name"] for c in cols], ["工号", "状态"])
        self.assertEqual(cols[1]["options"], ["在职", "离职"])
        self.assertIsNone(cols[0]["options"])

    def test_bad_options_json_does_not_crash(self):
        self.adapter.execute_query(
            "INSERT INTO columns_meta (name,label,field_type,options,position) VALUES (?,?,?,?,?)",
            ("x", "X", "text", "{not json", 0),
        )
        cols = self.store.load_columns()
        self.assertIsNone(cols[0]["options"])

    def test_field_type_defaults_when_empty(self):
        # 真实库里 field_type 可能是空串（历史数据 / 迁移残留）
        self.adapter.execute_query(
            "INSERT INTO columns_meta (name,label,field_type,options,position) VALUES (?,?,?,?,?)",
            ("x", "X", "", None, 0),
        )
        cols = self.store.load_columns()
        self.assertEqual(cols[0]["field_type"], "text")

    def test_field_type_defaults_when_null_in_table_without_notnull(self):
        # 用一个没有 NOT NULL 约束的表，验证 NULL 也能兜底成 'text'
        self.adapter.execute_query(
            "CREATE TABLE columns_meta_loose (id INTEGER PRIMARY KEY, name TEXT, label TEXT, "
            "field_type TEXT, options TEXT, position INTEGER)"
        )
        self.adapter.execute_query(
            "INSERT INTO columns_meta_loose (name,label,field_type,options,position) "
            "VALUES (?,?,?,?,?)",
            ("y", "Y", None, None, 0),
        )
        # 直接走底层查询验证 RowStore 的兜底逻辑
        rows = self.adapter.fetch_all(
            "SELECT id, name, label, field_type, options, position "
            "FROM columns_meta_loose ORDER BY position ASC"
        )
        normalized = self.store._normalize_options(rows)
        self.assertEqual(normalized[0]["field_type"], "text")


class TestSchemaVersion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rowstore_")
        self.adapter, self.store = make_store(self.tmp)

    def tearDown(self):
        self.adapter.close()

    def test_changes_when_field_added(self):
        v0 = self.store.schema_version()
        add_column(self.adapter, "a", "A", "text", 0)
        v1 = self.store.schema_version()
        add_column(self.adapter, "b", "B", "text", 1)
        v2 = self.store.schema_version()
        self.assertNotEqual(v0, v1)
        self.assertNotEqual(v1, v2)

    def test_changes_when_type_changed(self):
        add_column(self.adapter, "a", "A", "text", 0)
        v1 = self.store.schema_version()
        self.adapter.execute_query("UPDATE columns_meta SET field_type='number' WHERE name='a'")
        v2 = self.store.schema_version()
        self.assertNotEqual(v1, v2)

    def test_stable_when_nothing_changed(self):
        add_column(self.adapter, "a", "A", "text", 0)
        self.assertEqual(self.store.schema_version(), self.store.schema_version())


class TestReadWriteRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rowstore_")
        self.adapter, self.store = make_store(self.tmp)
        add_column(self.adapter, "姓名", "姓名", "text", 0)
        add_column(self.adapter, "年龄", "年龄", "number", 1)
        add_column(self.adapter, "在职", "在职", "boolean", 2)
        add_column(self.adapter, "入职日期", "入职日期", "date", 3)
        add_column(self.adapter, "部门", "部门", "select", 4)
        self.cols = self.store.load_columns()

    def tearDown(self):
        self.adapter.close()

    def test_insert_and_fetch_roundtrip(self):
        rid = self.store.insert_row(
            self.cols,
            {"姓名": "陈静宜", "年龄": 31.0, "在职": 1, "入职日期": "2024-03-18", "部门": "人力资源部"},
            created_by="hr",
        )
        from backend.uuid7 import is_valid_uuid7

        self.assertIsInstance(rid, str)
        self.assertTrue(is_valid_uuid7(rid), rid)

        row = self.store.fetch_row_by_id(rid, self.cols)
        self.assertEqual(row["id"], rid)
        self.assertEqual(row["姓名"], "陈静宜")
        self.assertEqual(row["年龄"], 31.0)
        self.assertEqual(row["在职"], 1)
        self.assertEqual(row["入职日期"], "2024-03-18")
        self.assertEqual(row["部门"], "人力资源部")

    def test_undefined_keys_are_ignored(self):
        rid = self.store.insert_row(
            self.cols, {"姓名": "A", "不存在的字段": "junk"}, created_by="hr"
        )
        row = self.store.fetch_row_by_id(rid, self.cols)
        self.assertNotIn("不存在的字段", row)
        self.assertEqual(row["姓名"], "A")

    def test_null_values_stay_none(self):
        rid = self.store.insert_row(self.cols, {"姓名": "A", "年龄": None}, created_by="hr")
        row = self.store.fetch_row_by_id(rid, self.cols)
        self.assertIsNone(row["年龄"])

    def test_boolean_hydration_from_json(self):
        # JSON 里存 1/0，读出来按 boolean 字段还原
        rid = self.store.insert_row(self.cols, {"姓名": "A", "在职": 0}, created_by="hr")
        row = self.store.fetch_row_by_id(rid, self.cols)
        self.assertEqual(row["在职"], 0)

    def test_order_desc_matches_list_page(self):
        # UUIDv7 前 48 位是毫秒时间戳 → 字符串序 = 时间序，DESC 即最新在前
        rids = [self.store.insert_row(self.cols, {"姓名": f"n{i}"}, created_by="hr") for i in range(3)]
        rows = self.store.fetch_rows(self.cols, order_desc=True)
        self.assertEqual([r["id"] for r in rows], list(reversed(rids)))

    def test_created_by_is_recorded(self):
        rid = self.store.insert_row(self.cols, {"姓名": "A"}, created_by="林致远")
        got = self.adapter.fetch_one("SELECT created_by FROM rows_data WHERE id = ?", (rid,))
        self.assertEqual(got["created_by"], "林致远")

    def test_schema_version_recorded_on_insert(self):
        rid = self.store.insert_row(self.cols, {"姓名": "A"}, created_by="hr")
        got = self.adapter.fetch_one("SELECT schema_version FROM rows_data WHERE id = ?", (rid,))
        self.assertEqual(got["schema_version"], self.store.schema_version())

    def test_count(self):
        for i in range(4):
            self.store.insert_row(self.cols, {"姓名": f"n{i}"}, created_by="hr")
        self.assertEqual(self.store.count_rows(), 4)

    def test_count_with_where(self):
        for i in range(3):
            self.store.insert_row(self.cols, {"姓名": "same"}, created_by="hr")
        self.store.insert_row(self.cols, {"姓名": "other"}, created_by="hr")
        self.assertEqual(self.store.count_rows("created_by = ?", ("hr",)), 4)
        self.assertEqual(
            self.store.count_rows("created_by = ?", ("nobody",)), 0
        )

    def test_fetch_rows_with_limit_offset(self):
        rids = [self.store.insert_row(self.cols, {"姓名": f"n{i}"}, created_by="hr") for i in range(5)]
        page = self.store.fetch_rows(self.cols, limit=2, offset=0)
        self.assertEqual(len(page), 2)
        self.assertEqual([r["id"] for r in page], [rids[4], rids[3]])


class TestUpdate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rowstore_")
        self.adapter, self.store = make_store(self.tmp)
        add_column(self.adapter, "姓名", "姓名", "text", 0)
        add_column(self.adapter, "部门", "部门", "select", 1)
        self.cols = self.store.load_columns()

    def tearDown(self):
        self.adapter.close()

    def test_partial_update_preserves_other_fields(self):
        rid = self.store.insert_row(
            self.cols, {"姓名": "苏婉清", "部门": "市场运营部"}, created_by="hr"
        )
        self.store.update_row(rid, self.cols, {"部门": "财务审计部"})
        row = self.store.fetch_row_by_id(rid, self.cols)
        self.assertEqual(row["姓名"], "苏婉清")          # 未被触碰
        self.assertEqual(row["部门"], "财务审计部")        # 已更新

    def test_update_ignores_undefined_fields(self):
        rid = self.store.insert_row(self.cols, {"姓名": "A"}, created_by="hr")
        self.store.update_row(rid, self.cols, {"幽灵字段": "x"})
        row = self.store.fetch_row_by_id(rid, self.cols)
        self.assertEqual(row["姓名"], "A")
        self.assertNotIn("幽灵字段", row)

    def test_update_nonexistent_row_affects_zero(self):
        n = self.store.update_row(99999, self.cols, {"姓名": "x"})
        self.assertEqual(n, 0)

    def test_replace_mode_drops_unmentioned_fields(self):
        rid = self.store.insert_row(
            self.cols, {"姓名": "A", "部门": "B"}, created_by="hr"
        )
        self.store.update_row(rid, self.cols, {"姓名": "C"}, merge=False)
        row = self.store.fetch_row_by_id(rid, self.cols)
        self.assertEqual(row["姓名"], "C")
        self.assertIsNone(row["部门"])

    def test_concurrent_updates_to_different_fields_both_survive(self):
        """
        原子性验收：两人同时改同一行的【不同字段】，两次改动都必须保留。

        「读出来→合并→写回」的非原子实现会让后写者覆盖先写者的字段。
        服务端 json_set 合并则不会。
        """
        rid = self.store.insert_row(
            self.cols, {"姓名": "原始", "部门": "原始部门"}, created_by="hr"
        )
        # 模拟两个并发请求：各自只改自己的字段
        self.store.update_row(rid, self.cols, {"姓名": "新姓名"})
        self.store.update_row(rid, self.cols, {"部门": "新部门"})
        row = self.store.fetch_row_by_id(rid, self.cols)
        self.assertEqual(row["姓名"], "新姓名", "姓名的修改被并发的部门修改覆盖了")
        self.assertEqual(row["部门"], "新部门")

    def test_update_with_no_valid_field_is_noop(self):
        rid = self.store.insert_row(self.cols, {"姓名": "A"}, created_by="hr")
        n = self.store.update_row(rid, self.cols, {"完全不相干的键": "x"})
        self.assertEqual(n, 0)
        self.assertEqual(self.store.fetch_row_by_id(rid, self.cols)["姓名"], "A")

    # ──────────── Phase 2c 乐观锁 ────────────

    def test_optimistic_lock_same_version_succeeds(self):
        """版本一致（读到的 updated_at 未变）→ 更新成功"""
        rid = self.store.insert_row(self.cols, {"姓名": "A"}, created_by="hr")
        base = self.store.get_updated_at(rid)
        self.assertIsNotNone(base)
        n = self.store.update_row(
            rid, self.cols, {"姓名": "B"}, base_updated_at=base
        )
        self.assertEqual(n, 1)
        self.assertEqual(self.store.fetch_row_by_id(rid, self.cols)["姓名"], "B")

    def test_optimistic_lock_stale_version_conflicts(self):
        """
        版本过期 → 0 行受影响（调用方转 409）。

        场景：A 打开编辑框拿到 base_updated_at；B 先改了一笔（updated_at 变了）；
        A 才提交。带旧版本的 UPDATE 必须不命中，绝不能静默覆盖 B 的改动。
        """
        rid = self.store.insert_row(self.cols, {"姓名": "A"}, created_by="hr")
        base = self.store.get_updated_at(rid)
        # B 抢先修改 → updated_at 前进（毫秒精度也要跨毫秒，睡 5ms 保证）
        time.sleep(0.005)
        self.store.update_row(rid, self.cols, {"姓名": "B先改的"})
        time.sleep(0.005)
        # A 带着旧版本提交
        n = self.store.update_row(
            rid, self.cols, {"姓名": "A后提交的"}, base_updated_at=base
        )
        self.assertEqual(n, 0, "过期版本居然更新成功——乐观锁失效")
        self.assertEqual(
            self.store.fetch_row_by_id(rid, self.cols)["姓名"], "B先改的",
            "B 的改动被 A 的过期提交覆盖了",
        )

    def test_optimistic_lock_merge_mode_preserves_other_fields(self):
        """乐观锁 + 原子合并同时生效：命中时别的字段不被清掉"""
        rid = self.store.insert_row(
            self.cols, {"姓名": "A", "部门": "技术部"}, created_by="hr"
        )
        base = self.store.get_updated_at(rid)
        self.store.update_row(rid, self.cols, {"姓名": "B"}, base_updated_at=base)
        row = self.store.fetch_row_by_id(rid, self.cols)
        self.assertEqual(row["姓名"], "B")
        self.assertEqual(row["部门"], "技术部")

    def test_get_updated_at_missing_row_returns_none(self):
        self.assertIsNone(self.store.get_updated_at("not-a-real-uuid"))

    def test_update_dict_value_field_is_stored_as_json_string(self):
        # file 字段的值是 dict，旧实现 json.dumps 成字符串，新实现保持一致
        add_column(self.adapter, "附件", "附件", "file", 2)
        cols = self.store.load_columns()
        rid = self.store.insert_row(
            cols, {"姓名": "A", "附件": {"name": "a.pdf", "content": "xx"}}, created_by="hr"
        )
        self.store.update_row(rid, cols, {"附件": {"name": "b.pdf", "content": "yy"}})
        row = self.store.fetch_row_by_id(rid, cols)
        self.assertEqual(json.loads(row["附件"])["name"], "b.pdf")

    def test_injected_field_name_is_filtered_by_whitelist(self):
        """
        恶意字段名有两道防线：
          1. `update_row` 先用字段白名单过滤，未定义键直接丢弃
          2. 即便绕过白名单，`json_path()` 也会拒绝含 $ . [ ] ' " 的键
        这里验证第 1 道：注入键既不改数据也不报错。
        """
        rid = self.store.insert_row(self.cols, {"姓名": "A"}, created_by="hr")
        n = self.store.update_row(
            rid, self.cols, {"$.evil' OR 1=1--": "x", "姓名": "B"}
        )
        self.assertGreaterEqual(n, 1)
        row = self.store.fetch_row_by_id(rid, self.cols)
        self.assertEqual(row["姓名"], "B")            # 合法字段照常生效
        self.assertNotIn("$.evil' OR 1=1--", row)      # 注入键未落库

    def test_json_path_is_the_second_line_of_defense(self):
        """第二道防线：直接调用 json_path 必须拒绝危险字符"""
        from backend.row_store import json_path
        for bad in ["$.x", "x'", 'x"', "x.y", "x[0]", "x\\", "x\ny"]:
            with self.assertRaises(ValueError, msg=bad):
                json_path(bad)


class TestDelete(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rowstore_")
        self.adapter, self.store = make_store(self.tmp)
        add_column(self.adapter, "姓名", "姓名", "text", 0)
        self.cols = self.store.load_columns()

    def tearDown(self):
        self.adapter.close()

    def test_delete_single(self):
        rid = self.store.insert_row(self.cols, {"姓名": "A"}, created_by="hr")
        self.assertEqual(self.store.delete_row(rid), 1)
        self.assertIsNone(self.store.fetch_row_by_id(rid, self.cols))

    def test_delete_all(self):
        for i in range(3):
            self.store.insert_row(self.cols, {"姓名": f"n{i}"}, created_by="hr")
        self.store.delete_all_rows()
        self.assertEqual(self.store.count_rows(), 0)

    def test_batch_delete(self):
        ids = [self.store.insert_row(self.cols, {"姓名": f"n{i}"}, created_by="hr") for i in range(4)]
        self.store.batch_delete_rows(ids[:2])
        self.assertEqual(self.store.count_rows(), 2)

    def test_batch_delete_empty_list_is_noop(self):
        self.store.insert_row(self.cols, {"姓名": "A"}, created_by="hr")
        self.assertEqual(self.store.batch_delete_rows([]), 0)
        self.assertEqual(self.store.count_rows(), 1)


class TestFetchColumnValues(unittest.TestCase):
    """统计接口的单列取值"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rowstore_")
        self.adapter, self.store = make_store(self.tmp)
        add_column(self.adapter, "部门", "部门", "select", 0)
        self.cols = self.store.load_columns()

    def tearDown(self):
        self.adapter.close()

    def test_skips_nulls_and_empty_strings(self):
        self.store.insert_row(self.cols, {"部门": "技术研发部"}, created_by="hr")
        self.store.insert_row(self.cols, {"部门": None}, created_by="hr")
        self.store.insert_row(self.cols, {"部门": ""}, created_by="hr")
        self.store.insert_row(self.cols, {"部门": "技术研发部"}, created_by="hr")
        self.store.insert_row(self.cols, {"部门": "  "}, created_by="hr")
        vals = self.store.fetch_column_values(self.cols[0])
        self.assertEqual(vals, ["技术研发部", "技术研发部"])

    def test_with_where_filter(self):
        self.store.insert_row(self.cols, {"部门": "A"}, created_by="hr")
        self.store.insert_row(self.cols, {"部门": "B"}, created_by="other")
        only_hr = self.store.fetch_column_values(
            self.cols[0], "created_by = ?", ("hr",)
        )
        self.assertEqual(only_hr, ["A"])

    def test_number_column_returns_numbers(self):
        add_column(self.adapter, "年龄", "年龄", "number", 1)
        cols = self.store.load_columns()
        num_col = [c for c in cols if c["name"] == "年龄"][0]
        self.store.insert_row(cols, {"年龄": 30.0}, created_by="hr")
        self.store.insert_row(cols, {"年龄": 41.0}, created_by="hr")
        vals = self.store.fetch_column_values(num_col)
        self.assertEqual(sorted(vals), [30.0, 41.0])


class TestNoColumns(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rowstore_")
        self.adapter, self.store = make_store(self.tmp)

    def tearDown(self):
        self.adapter.close()

    def test_fetch_rows_with_no_field_defs_returns_empty(self):
        self.assertEqual(self.store.fetch_rows([], ), [])
        self.assertEqual(self.store.count_rows(), 0)


class TestPhysicalColumnCountStability(unittest.TestCase):
    """
    核心验收：字段数量增长不应改变 rows_data 的物理列数。
    这是 ALTER TABLE 方案的硬伤（PG 1600 列上限、SQLite 删列残留）。
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rowstore_")
        self.adapter, self.store = make_store(self.tmp)

    def tearDown(self):
        self.adapter.close()

    def test_adding_fields_does_not_add_physical_columns(self):
        base = len(self.adapter.get_table_columns("rows_data"))
        self.store.insert_row(self.store.load_columns(), {}, created_by="hr") if self.store.load_columns() else None
        # 逐次加字段并写数据，物理列数必须恒定
        for i in range(60):
            add_column(self.adapter, f"f_{i}", f"字段{i}", "text", i)
            cols = self.store.load_columns()
            self.store.insert_row(cols, {f"f_{i}": f"v{i}"}, created_by="hr")
            n = len(self.adapter.get_table_columns("rows_data"))
            self.assertEqual(
                n, base, f"第 {i} 个字段后物理列数变成 {n}（基线 {base}）——D 方案已回归"
            )
        # 数据全部可读回
        self.assertEqual(self.store.count_rows(), 60)

    def test_deleting_field_does_not_leave_physical_column(self):
        add_column(self.adapter, "临时", "临时", "text", 0)
        self.store.insert_row(self.store.load_columns(), {"临时": "x"}, created_by="hr")
        base = len(self.adapter.get_table_columns("rows_data"))
        # 删字段定义（模拟现状：只删元数据）
        self.adapter.execute_query("DELETE FROM columns_meta WHERE name = '临时'")
        after = len(self.adapter.get_table_columns("rows_data"))
        self.assertEqual(after, base, "删除字段定义不应留下额外物理列")


if __name__ == "__main__":
    unittest.main(verbosity=2)
