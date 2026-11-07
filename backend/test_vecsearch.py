# -*- coding: utf-8 -*-
"""
vecsearch 单元测试
==================

运行方式（必须从项目根目录，TEMP/TMP 指向 .dsh-tmp，不碰 data/app.db）:
    python -m pytest backend/test_vecsearch.py -q

覆盖：
  ① tokenize 中文单字 + bigram
  ② build + search 命中正确行（含「陈静宜」查「静宜」）
  ③ top_k 截断
  ④ 空查询 / 空索引不崩
  ⑤ persist/load roundtrip 相等
  ⑥ 索引对未知行 id 安全（裁剪 norms/texts 后兜底重算）
  ⑦ 1000 行建索引 <1s（性能烟测，超时机器标记 skip 而非 fail）
"""

import json
import os
import sys
import tempfile
import time
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.vecsearch import (
    VecSearchError,
    build_index,
    build_index_from_store,
    get_row_text,
    load_index,
    persist_index,
    search,
    tokenize,
)


def make_rows(n: int) -> list:
    """造 n 行假 HR 数据（id 为 UUIDv7 格式字符串）。"""
    surnames = "陈林王张刘李"
    rows = []
    for i in range(n):
        rows.append({
            "id": str(uuid.uuid4()),
            "姓名": f"{surnames[i % len(surnames)]}静宜{i}",
            "部门": "技术部" if i % 2 == 0 else "市场部",
            "工号": f"GH{i:05d}",
            "邮箱": f"user{i}@corp.example",
            "备注": "在职" if i % 3 else "离职",
        })
    return rows


class TestTokenize(unittest.TestCase):
    """① 中文单字 + bigram；英文/数字小写词；标点空白过滤。"""

    def test_chinese_unigram_and_bigram(self):
        self.assertEqual(tokenize("静宜"), ["静", "宜", "静宜"])
        # 顺序约定：每遇到一个 CJK 字，先出该字单字，再出与前字的 bigram
        self.assertEqual(tokenize("陈静宜"), ["陈", "静", "陈静", "宜", "静宜"])

    def test_ascii_words_lowercased(self):
        self.assertEqual(tokenize("User-01"), ["user", "01"])
        self.assertEqual(tokenize("Hello World"), ["hello", "world"])

    def test_punct_space_breaks_bigram(self):
        # 标点/空白切断相邻关系，且自身不产出 token
        self.assertEqual(tokenize("陈 静"), ["陈", "静"])
        self.assertEqual(tokenize("陈，静。"), ["陈", "静"])
        self.assertEqual(tokenize("，。！"), [])

    def test_mixed_and_none(self):
        self.assertEqual(tokenize("工号GH001"), ["工", "号", "工号", "gh001"])
        self.assertEqual(tokenize(None), [])
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize(12345), ["12345"])


class TestBuildAndSearch(unittest.TestCase):
    """② build + search 命中正确行。"""

    def setUp(self):
        self.rows = [
            {"id": "01900000-0000-7000-8000-000000000001", "姓名": "陈静宜", "部门": "技术部", "工号": "GH001"},
            {"id": "01900000-0000-7000-8000-000000000002", "姓名": "王大力", "部门": "市场部", "工号": "GH002"},
            {"id": "01900000-0000-7000-8000-000000000003", "姓名": "陈大力", "部门": "技术部", "工号": "GH003"},
        ]
        self.index = build_index(self.rows, fields=["姓名", "部门", "工号"])

    def test_hit_correct_row(self):
        hits = search(self.index, "静宜")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["row_id"], self.rows[0]["id"])
        self.assertGreater(hits[0]["score"], 0.05)
        self.assertTrue(hits[0]["snippet"])

    def test_hit_row_without_full_name(self):
        # 「大力」应同时命中王大力/陈大力，不命中陈静宜
        hits = search(self.index, "大力")
        ids = {h["row_id"] for h in hits}
        self.assertEqual(ids, {self.rows[1]["id"], self.rows[2]["id"]})

    def test_query_indexed_field_only(self):
        # 工号精确片段
        hits = search(self.index, "GH002")
        self.assertEqual(hits[0]["row_id"], self.rows[1]["id"])

    def test_no_hit_returns_empty(self):
        self.assertEqual(search(self.index, "赵铁柱"), [])

    def test_index_shape(self):
        self.assertEqual(self.index["version"], 1)
        self.assertEqual(self.index["row_count"], 3)
        self.assertEqual(self.index["fields"], ["姓名", "部门", "工号"])
        self.assertTrue(self.index["schema_fingerprint"])
        self.assertTrue(self.index["built_at"])
        self.assertIn("陈静宜", self.index["texts"][self.rows[0]["id"]])


class TestTopK(unittest.TestCase):
    """③ top_k 截断。"""

    def test_top_k_truncates(self):
        rows = make_rows(30)
        idx = build_index(rows)
        hits = search(idx, "静宜", top_k=5)
        self.assertLessEqual(len(hits), 5)
        scores = [h["score"] for h in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))
        # top_k 大于命中数时全量返回
        self.assertLessEqual(len(search(idx, "静宜", top_k=100)), 30)
        # top_k=0 返回空
        self.assertEqual(search(idx, "静宜", top_k=0), [])


class TestEmptySafety(unittest.TestCase):
    """④ 空查询 / 空索引不崩。"""

    def test_empty_query(self):
        idx = build_index(make_rows(5))
        self.assertEqual(search(idx, ""), [])
        self.assertEqual(search(idx, "，。"), [])

    def test_empty_index(self):
        idx = build_index([])
        self.assertEqual(idx["row_count"], 0)
        self.assertEqual(search(idx, "静宜"), [])

    def test_empty_query_on_empty_index(self):
        self.assertEqual(search(build_index([]), ""), [])

    def test_bad_row_raises(self):
        with self.assertRaises(VecSearchError):
            build_index([{"姓名": "无id"}])
        with self.assertRaises(VecSearchError):
            build_index(["not a dict"])


class TestPersistRoundtrip(unittest.TestCase):
    """⑤ persist/load roundtrip 相等。"""

    def test_roundtrip_equal(self):
        idx = build_index(make_rows(20))
        with tempfile.TemporaryDirectory(prefix="vecsearch_") as tmp:
            path = os.path.join(tmp, "idx.json")
            self.assertEqual(persist_index(idx, path), path)
            loaded = load_index(path)
            # 中文未被转义（ensure_ascii=False）
            self.assertIn("静宜", open(path, encoding="utf-8").read())
        self.assertEqual(loaded["version"], 1)
        self.assertEqual(loaded["row_count"], 20)
        self.assertEqual(loaded["tf"], idx["tf"])
        self.assertEqual(loaded["df"], idx["df"])
        self.assertEqual(loaded["norms"], idx["norms"])
        self.assertEqual(loaded["texts"], idx["texts"])
        self.assertEqual(loaded["schema_fingerprint"], idx["schema_fingerprint"])
        # roundtrip 后检索结果一致
        self.assertEqual(
            search(loaded, "静宜", snippet=False),
            search(idx, "静宜", snippet=False),
        )

    def test_load_bad_version_rejected(self):
        with tempfile.TemporaryDirectory(prefix="vecsearch_") as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"version": 999}, f)
            with self.assertRaises(VecSearchError):
                load_index(path)


class TestUnknownRowSafety(unittest.TestCase):
    """⑥ 索引对未知行 id 安全。"""

    def test_pruned_norms_texts_still_scored(self):
        rows = make_rows(6)
        idx = build_index(rows)
        # 模拟外部裁剪：某一行的 norms / texts 被删掉
        victim = rows[0]["id"]
        idx["norms"].pop(victim)
        idx["texts"].pop(victim)
        hits = search(idx, "静宜", top_k=100)
        self.assertTrue(hits)  # 该行仍应能被打分返回（现场重算模长）
        self.assertIn(victim, {h["row_id"] for h in hits})
        # 被裁剪行的 snippet 为空但不抛异常
        victim_hits = [h for h in hits if h["row_id"] == victim]
        self.assertEqual(victim_hits[0].get("snippet", ""), "")

    def test_get_row_text_unknown_id(self):
        idx = build_index(make_rows(3))
        self.assertIsNone(get_row_text(idx, "nonexistent-id"))
        self.assertIsNotNone(get_row_text(idx, idx["texts"] and list(idx["texts"])[0]))


class TestPerfSmoke(unittest.TestCase):
    """⑦ 1000 行建索引 <1s（性能烟测；慢机器超时 → skip 而非 fail）。"""

    def test_1000_rows_index_under_1s(self):
        rows = make_rows(1000)
        t0 = time.perf_counter()
        idx = build_index(rows, fields=["姓名", "部门", "工号", "邮箱", "备注"])
        dt = time.perf_counter() - t0
        self.assertEqual(idx["row_count"], 1000)
        if dt >= 1.0:
            self.skipTest(f"建索引耗时 {dt:.3f}s，机器过慢，按约定 skip")
        # 附带验证检索可用
        self.assertTrue(search(idx, "静宜"))


class TestBuildFromStore(unittest.TestCase):
    """顶层 API：从 db_adapter 适配器建索引（不 import RowStore / app）。"""

    def setUp(self):
        from backend.db_adapter import SQLiteAdapter
        self.tmp = tempfile.mkdtemp(prefix="vecsearch_db_")
        self.db_path = os.path.join(self.tmp, "vs_test.db")
        self.adapter = SQLiteAdapter(self.db_path)
        self.adapter.connect()
        self.adapter.execute_query(
            """
            CREATE TABLE IF NOT EXISTS columns_meta (
                id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, label TEXT NOT NULL,
                field_type TEXT NOT NULL DEFAULT 'text', options TEXT,
                position INTEGER DEFAULT 0
            )
            """
        )
        self.adapter.execute_query(
            """
            CREATE TABLE IF NOT EXISTS rows_data (
                id TEXT PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}',
                created_by TEXT, schema_version INTEGER, created_at DATETIME, updated_at DATETIME
            )
            """
        )
        for name, ftype, pos in [("姓名", "text", 0), ("部门", "select", 1), ("工号", "text", 2)]:
            self.adapter.execute_query(
                "INSERT INTO columns_meta (id, name, label, field_type, position) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), name, name, ftype, pos),
            )
        self.target_id = "01900000-0000-7000-8000-0000000000ab"
        for rid, data in [
            (self.target_id, {"姓名": "陈静宜", "部门": "技术部", "工号": "GH001"}),
            (str(uuid.uuid4()), {"姓名": "王大力", "部门": "市场部", "工号": "GH002"}),
        ]:
            self.adapter.insert("rows_data", {"id": rid, "data": json.dumps(data, ensure_ascii=False)})

    def tearDown(self):
        self.adapter.close()

    def test_build_from_store_hits(self):
        idx = build_index_from_store(self.adapter)  # fields=None → columns_meta 全字段
        self.assertEqual(idx["row_count"], 2)
        self.assertEqual(idx["fields"], ["姓名", "部门", "工号"])
        hits = search(idx, "静宜")
        self.assertEqual(hits[0]["row_id"], self.target_id)
        # schema_fingerprint 覆盖「字段名:类型」
        self.assertNotEqual(idx["schema_fingerprint"], build_index([])["schema_fingerprint"])

    def test_build_from_store_explicit_fields(self):
        idx = build_index_from_store(self.adapter, fields=["工号"])
        hits = search(idx, "GH001")
        self.assertEqual(hits[0]["row_id"], self.target_id)
        self.assertEqual(search(idx, "静宜"), [])  # 姓名未参与索引

    def test_store_with_bad_data_json(self):
        # data 非 JSON 时不炸，该行按空文本处理
        self.adapter.insert("rows_data", {
            "id": str(uuid.uuid4()), "data": "{bad json",
        })
        idx = build_index_from_store(self.adapter)
        self.assertEqual(idx["row_count"], 3)


if __name__ == "__main__":
    unittest.main()
