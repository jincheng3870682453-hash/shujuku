# -*- coding: utf-8 -*-
"""
Phase 1b 端到端验证：在**真实数据副本**上执行完整迁移并全量比对。

不会触碰 live 库（只读打开并复制到临时目录）。

比对内容（比 migrate() 内部自校验更严）：
  1. 行数相等
  2. 每行的每个字段值相等（含孤儿列，空串/None 视为相等）
  3. id 集合完全一致
  4. created_by 相等
  5. 迁移后物理列数恒为 6
  6. RowStore 能读回全部行
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from backend.db_adapter import SQLiteAdapter
from backend import migrate_jsonb as M
from backend.row_store import RowStore

LIVE = os.path.join(_ROOT, "data", "app.db")


def snap(path):
    """用原生 sqlite3 读全表，返回 {id: {字段: 值}} 与列名列表"""
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    cols = [r[1] for r in c.execute("PRAGMA table_info(rows_data)")]
    rows = {}
    for r in c.execute("SELECT * FROM rows_data"):
        d = dict(r)
        rows[d["id"]] = {k: v for k, v in d.items() if k != "id"}
    c.close()
    return cols, rows


def norm_map(d, drop_id=True):
    """
    归一化一个 {字段: 值} 字典：
      * None / 空串 / 纯空白 → 该键**删除**（迁移时空值键不写入 JSON，这是有意设计）
      * 其余转成字符串，保证 '3' 与 3 不会因类型差异误报
    """
    out = {}
    for k, v in d.items():
        if drop_id and k in ("_created_by", "created_by"):
            continue
        if v is None:
            continue
        s = str(v)
        if s.strip() == "":
            continue
        out[k] = s
    return out


def main():
    tmp = tempfile.mkdtemp(prefix="e2e_migrate_")
    copy = os.path.join(tmp, "app_copy.db")
    shutil.copy2(LIVE, copy)
    print(f"副本: {copy}")

    # ── 迁移前快照 ──
    before_cols, before_rows = snap(copy)
    print(f"\n[迁移前] 物理列数 = {len(before_cols)}")
    print(f"[迁移前] 行数     = {len(before_rows)}")
    before_dynamic = [c for c in before_cols if c not in (
        "id", "_created_by", "created_by", "created_at", "updated_at", "schema_version", "data")]
    before_orphans = [c for c in before_dynamic if c not in
                      ("工号", "姓名", "性别", "年龄", "部门", "岗位", "学历", "籍贯_城市",
                       "联系电话", "电子邮箱", "入职日期", "月薪_元", "婚姻状况", "血型", "员工状态")]
    print(f"[迁移前] 动态列   = {len(before_dynamic)}（其中孤儿列 {len(before_orphans)}）")

    # ── 执行迁移 ──
    db = SQLiteAdapter(copy)
    db.connect()
    stats = M.migrate(db)
    print(f"\n[迁移] status = {stats['status']}, rows_moved = {stats.get('rows_moved')}")
    print(f"[迁移] legacy_table = {stats.get('legacy_table')}")

    ok = True

    # ── 1. 迁移后结构 ──
    after_cols = [c["name"] for c in db.get_table_columns("rows_data")]
    print(f"\n[迁移后] 物理列数 = {len(after_cols)} : {after_cols}")
    if len(after_cols) != 6:
        print("  ✗ 物理列数应为 6")
        ok = False
    else:
        print("  ✓ 物理列数恒为 6（与字段数量解耦）")

    # ── 2. 行数 / id / 逐字段比对 ──
    after_raw = db.fetch_all("SELECT id, data, created_by FROM rows_data ORDER BY id")
    if len(after_raw) != len(before_rows):
        print(f"  ✗ 行数不等: {len(after_raw)} vs {len(before_rows)}")
        ok = False
    else:
        print(f"  ✓ 行数相等 ({len(after_raw)})")

    ids_match = set(r["id"] for r in after_raw) == set(before_rows.keys())
    print(("  ✓ id 集合一致" if ids_match else "  ✗ id 集合不一致"))
    ok &= ids_match

    field_mismatch = 0
    cb_mismatch = 0
    for r in after_raw:
        rid = r["id"]
        try:
            payload = json.loads(r["data"]) if r["data"] else {}
        except (ValueError, TypeError):
            payload = {}
        old = before_rows.get(rid, {})

        # 字段比对：两侧都按「空值键删除」归一化后，键集合与值必须完全相同
        old_keys = norm_map(old)
        new_keys = norm_map(payload, drop_id=False)
        if old_keys != new_keys:
            field_mismatch += 1
            if field_mismatch <= 3:
                only_old = sorted(set(old_keys) - set(new_keys))
                only_new = sorted(set(new_keys) - set(old_keys))
                diff_val = [k for k in set(old_keys) & set(new_keys)
                            if old_keys[k] != new_keys[k]]
                print(f"    id={rid} 仅旧有={only_old[:5]} 仅新有={only_new[:5]} "
                      f"值不同={diff_val[:5]}")

        old_cb = norm_map(old, drop_id=False).get("_created_by") or \
            norm_map(old, drop_id=False).get("created_by")
        if old_cb != (r["created_by"] if r["created_by"] else None):
            cb_mismatch += 1

    if field_mismatch == 0:
        print(f"  ✓ 全部 {len(after_raw)} 行的字段值逐一相等（含 {len(before_orphans)} 个孤儿列）")
    else:
        print(f"  ✗ {field_mismatch} 行字段值不一致")
        ok = False

    if cb_mismatch == 0:
        print("  ✓ created_by 全部一致")
    else:
        print(f"  ✗ {cb_mismatch} 行 created_by 不一致")
        ok = False

    # ── 3. RowStore 可读回 ──
    store = RowStore(db)
    cols = store.load_columns()
    rows = store.fetch_rows(cols)
    print(f"\n[RowStore] 读回 {len(rows)} 行，字段 {len(cols)} 个")
    if len(rows) != len(before_rows):
        print("  ✗ RowStore 读回行数不符")
        ok = False
    else:
        print("  ✓ RowStore 读回行数一致")

    # 抽查第一行的字段值
    if rows and cols:
        sample_id = rows[0]["id"]
        old_sample = norm_map(before_rows[sample_id])
        new_sample = norm_map({k: v for k, v in rows[0].items() if k != "id"}, drop_id=False)
        same = old_sample == new_sample
        print(("  ✓ 抽查行字段值一致" if same else "  ✗ 抽查行字段值不一致"))
        if not same:
            print(f"    仅旧有: {sorted(set(old_sample)-set(new_sample))[:6]}")
            print(f"    仅新有: {sorted(set(new_sample)-set(old_sample))[:6]}")
        ok &= same

    # ── 4. 旧表保留 ──
    legacy = stats.get("legacy_table")
    legacy_cols = [c["name"] for c in db.get_table_columns(legacy)]
    legacy_n = db.fetch_one(f"SELECT COUNT(*) AS c FROM {legacy}")["c"]
    print(f"\n[回滚保障] {legacy}: {len(legacy_cols)} 列, {legacy_n} 行")
    ok &= (len(legacy_cols) == len(before_cols) and legacy_n == len(before_rows))

    db.close()

    print("\n" + "=" * 60)
    print("E2E RESULT: " + ("PASS ✅" if ok else "FAIL ❌"))
    print("=" * 60)
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
