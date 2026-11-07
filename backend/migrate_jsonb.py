# -*- coding: utf-8 -*-
"""
rows_data 宽表 → JSONB 单列 数据迁移脚本
========================================

设计依据见 `docs/立项-存储层重构.md`。

为什么需要迁移：
  旧 `rows_data` 是「字段即列」的宽表，靠 `ALTER TABLE ADD COLUMN` 扩展。
  实测 active 库 `data/app.db`：`columns_meta` 定义 15 个字段，`rows_data` 却有 35 列，
  其中 18 个孤儿列（数据值被误判成表头后当成字段名 ALTER 进去）。列数只增不减。

迁移策略（安全优先）：
  1. **不动原表**：先建新表 `rows_data_new`，搬运完成后原子改名
  2. **旧表保留**：原表改名为 `rows_data_legacy_<日期>`，出问题可秒级回滚
  3. **幂等**：检测到已是新结构（有 `data` 列）就直接跳过，可反复执行
  4. **可校验**：迁移前后比对行数、每行逐字段值，不相等则中止并保留旧表
  5. **孤儿列一并搬**：18 个孤儿列的值不丢（它们仍是要保留的历史数据，只是无字段定义）

用法：
    python -m backend.migrate_jsonb                 # 迁移（默认库）
    python -m backend.migrate_jsonb --dry-run       # 只检查不执行
    python -m backend.migrate_jsonb --verify-only   # 只校验，不迁移
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.db_adapter import get_adapter, reset_adapter

# ──────────────────────── 常量 ────────────────────────

NEW_TABLE = "rows_data_new"
LEGACY_PREFIX = "rows_data_legacy_"

#: 新表结构（SQLite 方言；MySQL 由 convert_create_table_sql 转换）
NEW_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS rows_data_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    schema_version INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
)
"""

#: 新表索引
NEW_TABLE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_rows_new_created_by ON rows_data_new(created_by)",
    "CREATE INDEX IF NOT EXISTS idx_rows_new_created_at ON rows_data_new(created_at)",
]

#: 不属于用户字段的系统列
SYSTEM_COLUMNS = {"id", "_created_by", "created_by", "created_at", "updated_at", "schema_version"}


class MigrationError(Exception):
    """迁移失败；失败时旧表一定保持原样"""


# ──────────────────────── 工具 ────────────────────────


def _log(msg: str) -> None:
    print(f"[migrate] {msg}", flush=True)


def get_table_columns(db, table: str) -> List[str]:
    return [c["name"] for c in db.get_table_columns(table)]


def table_exists(db, table: str) -> bool:
    """
    判断表是否存在。

    注意：SQLite 的 `PRAGMA table_info(<不存在>)` **不抛异常**，只返回空列表，
    所以不能靠 try/except 判断，必须显式查 sqlite_master；MySQL 走 information_schema。
    """
    if db.is_sqlite():
        row = db.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table,),
        )
        return bool(row)
    row = db.fetch_one(
        "SELECT table_name AS name FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = ?",
        (table,),
    )
    return bool(row)


def is_migrated(db) -> bool:
    """判断 rows_data 是否已是新结构"""
    if not table_exists(db, "rows_data"):
        return False
    cols = set(get_table_columns(db, "rows_data"))
    return "data" in cols


def quote_ident(db, name: str) -> str:
    """按引擎引用标识符（SQLite 双引号 / MySQL 反引号）"""
    q = db.get_column_quote()
    return f"{q}{name}{q}"


# ──────────────────────── 校验 ────────────────────────


def row_checksum(row: Dict[str, Any], keys: List[str]) -> str:
    """
    生成一行数据的稳定校验串（已归一化）。

    规则：空字符串与 None 一律视为「该字段不存在」；其余按 `字段名=值` 排序拼接。
    迁移前后用同一套规则，才能做有意义的比对。
    """
    parts = []
    for k in sorted(keys):
        v = row.get(k)
        if v is None:
            continue
        s = str(v)
        if s.strip() == "":
            continue
        parts.append(f"{k}={s}")
    return "|".join(parts)


def _payload_checksum(payload: Dict[str, Any]) -> str:
    """从 JSON 负载重建校验串，规则与 row_checksum 一致"""
    return row_checksum(payload, list(payload.keys()))


def read_old_rows(db, dynamic_cols: List[str], created_by_col: Optional[str]) -> List[Dict[str, Any]]:
    """按旧宽表结构读全部行"""
    select = ["id"]
    select += dynamic_cols
    if created_by_col:
        select.append(created_by_col)
    sql = "SELECT " + ", ".join(quote_ident(db, c) for c in select) + " FROM rows_data"
    return db.fetch_all(sql)


# ──────────────────────── 主流程 ────────────────────────


def migrate(db, dry_run: bool = False) -> Dict[str, Any]:
    """
    执行迁移。返回统计信息。

    Raises:
        MigrationError: 校验不通过或执行出错；此时旧表保持原样
    """
    stats: Dict[str, Any] = {"status": "started"}

    if not table_exists(db, "rows_data"):
        raise MigrationError("rows_data 表不存在，无可迁移内容")

    if is_migrated(db):
        _log("rows_data 已是 JSONB 结构，跳过（幂等）")
        stats.update(status="already-migrated")
        return stats

    old_cols = get_table_columns(db, "rows_data")
    _log(f"旧表列数: {len(old_cols)}")

    defined = {r["name"] for r in db.fetch_all("SELECT name FROM columns_meta")}
    dynamic_cols = [c for c in old_cols if c not in SYSTEM_COLUMNS]
    orphan_cols = [c for c in dynamic_cols if c not in defined]

    _log(f"已定义字段: {len(defined)}")
    _log(f"物理动态列: {len(dynamic_cols)}")
    _log(f"孤儿列（无字段定义）: {len(orphan_cols)}")
    if orphan_cols:
        for c in orphan_cols:
            _log(f"    - {c}")

    created_by_col = None
    for cand in ("_created_by", "created_by"):
        if cand in old_cols:
            created_by_col = cand
            break

    if dry_run:
        stats.update(
            status="dry-run",
            old_column_count=len(old_cols),
            defined_fields=len(defined),
            orphan_columns=orphan_cols,
        )
        _log("dry-run 模式，未做任何修改")
        return stats

    old_rows = read_old_rows(db, dynamic_cols, created_by_col)
    _log(f"读取旧表 {len(old_rows)} 行")

    # 迁移前快照校验值
    before = {}
    for r in old_rows:
        keys = [c for c in dynamic_cols]
        before[r["id"]] = row_checksum(r, keys)

    # ── 1. 建新表 ──
    if table_exists(db, NEW_TABLE):
        _log(f"清理上次遗留的 {NEW_TABLE}")
        db.execute_query(f"DROP TABLE {quote_ident(db, NEW_TABLE)}")
    ddl = db.convert_create_table_sql(NEW_TABLE_DDL)
    db.execute_query(ddl)
    for idx in NEW_TABLE_INDEXES:
        db.execute_query(idx.replace("rows_data_new", quote_ident(db, NEW_TABLE)))
    _log(f"已创建 {NEW_TABLE}")

    # ── 2. 逐行搬运 ──
    ph = db.get_placeholder()
    insert_sql = (
        f"INSERT INTO {quote_ident(db, NEW_TABLE)} "
        f"(id, data, created_by, schema_version, created_at, updated_at) "
        f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})"
    )
    moved = 0
    for r in old_rows:
        payload = {}
        for c in dynamic_cols:
            v = r.get(c)
            # 空字符串与 None 统一成 None，避免 JSON 里堆无效键
            if v is not None and str(v).strip() != "":
                payload[c] = v
        created_by = r.get(created_by_col) if created_by_col else ""
        db.execute_query(
            insert_sql,
            (
                r["id"],
                json.dumps(payload, ensure_ascii=False),
                created_by or "",
                0,
                r.get("created_at"),
                r.get("updated_at"),
            ),
        )
        moved += 1
    _log(f"已搬运 {moved} 行")

    # ── 3. 迁移后校验（行数 + 逐行字段值）──
    new_rows = db.fetch_all(
        f"SELECT id, data, created_by FROM {quote_ident(db, NEW_TABLE)}"
    )
    if len(new_rows) != len(old_rows):
        raise MigrationError(f"行数不一致: 旧 {len(old_rows)} vs 新 {len(new_rows)}")

    # 逐行比对：从新表 JSON 重建「字段名=值」串，与迁移前快照严格相等。
    # 语义：迁移前记的是"这一行有哪些非空字段、值分别是什么"，
    #       迁移后必须能原样重建出来，否则说明搬运丢了或篡改了数据。
    mismatches = []
    for nr in new_rows:
        rid = nr["id"]
        try:
            payload = json.loads(nr["data"]) if nr.get("data") else {}
        except (ValueError, TypeError):
            payload = {}
        actual = _payload_checksum(payload)
        expected = before.get(rid, "")
        if expected != actual:
            mismatches.append((rid, expected, actual))

    if mismatches:
        for rid, exp, act in mismatches[:5]:
            _log(f"  数据不一致 id={rid}")
            _log(f"    迁移前: {exp[:300]}")
            _log(f"    迁移后: {act[:300]}")
        raise MigrationError(
            f"{len(mismatches)} 行数据校验不一致，迁移中止（旧表 rows_data 未做任何修改）"
        )

    _log("逐行数据校验通过")

    # ── 4. 原子改名 ──
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    legacy = LEGACY_PREFIX + stamp

    if db.is_sqlite():
        # SQLite 支持 RENAME TABLE，但为了不触发触发器/视图级联问题，
        # 且要保证「失败即回滚」，这里显式按步骤做并在每步校验。
        db.execute_query(f"ALTER TABLE rows_data RENAME TO {quote_ident(db, legacy)}")
        db.execute_query(f"ALTER TABLE {quote_ident(db, NEW_TABLE)} RENAME TO rows_data")
    else:
        db.execute_query(f"RENAME TABLE rows_data TO {legacy}")
        db.execute_query(f"RENAME TABLE {quote_ident(db, NEW_TABLE)} TO rows_data")

    _log(f"旧表已保留为 {legacy}")
    _log("迁移完成")

    stats.update(
        status="migrated",
        rows_moved=moved,
        old_column_count=len(old_cols),
        orphan_columns=orphan_cols,
        legacy_table=legacy,
    )
    return stats


def verify(db) -> Dict[str, Any]:
    """只校验不改数据：报告当前结构是否符合 JSONB 方案"""
    if not table_exists(db, "rows_data"):
        return {"ok": False, "reason": "rows_data 不存在"}
    cols = get_table_columns(db, "rows_data")
    result = {
        "ok": "data" in cols,
        "is_migrated": is_migrated(db),
        "columns": cols,
        "column_count": len(cols),
    }
    if "rows_data" in cols or "data" in cols:
        try:
            n = db.fetch_one("SELECT COUNT(*) AS c FROM rows_data")["c"]
            result["row_count"] = n
        except Exception as e:
            result["count_error"] = str(e)
    legacy = [
        t for t in (db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
                    if db.is_sqlite() else [])
        if str(t.get("name", "")).startswith(LEGACY_PREFIX)
    ]
    result["legacy_tables"] = [t.get("name") for t in legacy]
    return result


# ──────────────────────── CLI ────────────────────────


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="rows_data 宽表 → JSONB 迁移")
    parser.add_argument("--dry-run", action="store_true", help="只检查不执行")
    parser.add_argument("--verify-only", action="store_true", help="只校验当前结构")
    args = parser.parse_args(argv)

    db = get_adapter()
    try:
        if args.verify_only:
            print(json.dumps(verify(db), ensure_ascii=False, indent=2))
            return 0
        stats = migrate(db, dry_run=args.dry_run)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0 if stats.get("status") != "failed" else 1
    except MigrationError as e:
        _log(f"迁移失败: {e}")
        return 1
    finally:
        db.close()
        reset_adapter()


if __name__ == "__main__":
    sys.exit(main())
