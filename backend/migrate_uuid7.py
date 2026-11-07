# -*- coding: utf-8 -*-
"""
INTEGER PK → UUIDv7 TEXT PK 数据迁移脚本（Phase 2b）
==================================================

背景见 `docs/立项-存储层重构.md` §0.1 + Phase 2b：
离线同步的硬阻塞是多台机器各自 AUTOINCREMENT 会撞 id，
主键必须全局唯一且可离线生成 → 8 张整数主键表统一切到 TEXT PK + 应用层 uuid7。

改写面（Lead 2026-10-18 彻底盘点锁定）：
  PK 表（8 张）: users / columns_meta / rows_data / pending_changes /
                 operations_log / audit_log / backups / ai_analysis_history
    `id INTEGER PRIMARY KEY AUTOINCREMENT` → `id TEXT PRIMARY KEY`
  FK 列（整数 → TEXT，值按 old_int→uuid7 映射改写）:
    pending_changes.row_id       —— 多态！insert/update/delete/clear 指 rows_data.id；
                                   add_user/update_user/delete_user 指 users.id；
                                   其余类型（add_column/delete_column/…）为 NULL
    pending_changes.requested_by → users.id
    pending_changes.reviewed_by  → users.id
    operations_log.user_id       → users.id
    audit_log.user_id            → users.id
  多态 TEXT 列（字符串比对改写）:
    operations_log.target_id —— target_type=rows_data/users/pending_changes 时按对应映射改写
    audit_log.target_id      —— target_table 同上
  JSON 内嵌 id（new_value / old_value 里 `{"id": <int>}`）:
    add_user/update_user/delete_user → users 映射
    insert/update/delete            → rows_data 映射

迁移策略（安全优先，与 migrate_jsonb.py 同构）：
  1. **不动原表**：每张表建 `<表>_new`（TEXT PK），搬运完成后逐表原子改名
  2. **旧表保留**：原表改名为 `<表>_legacy_<日期>`，出问题可秒级回滚
  3. **幂等**：检测到 8 张表 id 列已全是 TEXT 类型就直接跳过，可反复执行
  4. **可校验**：迁移前后比对行数 + FK 悬空检查，不相等则中止并保留旧表
  5. **映射先行**：第一遍先为 8 张表所有旧 id 生成 uuid7 映射，第二遍才搬运改写

用法：
    python -m backend.migrate_uuid7                 # 迁移（默认库）
    python -m backend.migrate_uuid7 --dry-run       # 只检查不执行
    python -m backend.migrate_uuid7 --verify-only   # 只校验当前结构
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.db_adapter import get_adapter, reset_adapter
from backend.uuid7 import is_valid_uuid7, uuid7

# ──────────────────────── 常量 ────────────────────────

#: 旧表改名后缀。刻意与 migrate_jsonb 的 `rows_data_legacy_<日期>` 区分开：
#: 两个迁移可能在同一秒内先后执行（先 jsonb 再 uuid7），共用前缀会撞表名。
LEGACY_PREFIX = "_uuid_legacy_"

#: 8 张整数主键表
PK_TABLES = [
    "users",
    "columns_meta",
    "rows_data",
    "pending_changes",
    "operations_log",
    "audit_log",
    "backups",
    "ai_analysis_history",
]

#: FK 列 → 引用的 PK 表（值按对应表的 old_int→uuid7 映射改写）
#: pending_changes.row_id 是多态列，单独处理，不在这里
FK_MAP = {
    ("pending_changes", "requested_by"): "users",
    ("pending_changes", "reviewed_by"): "users",
    ("operations_log", "user_id"): "users",
    ("audit_log", "user_id"): "users",
    ("ai_analysis_history", "user_id"): "users",
}

#: pending_changes.row_id 多态：change_type → 引用的 PK 表（None = 不引用，保持 NULL）
ROW_ID_REF = {
    "insert": "rows_data",
    "update": "rows_data",
    "delete": "rows_data",
    "clear": None,
    "add_user": "users",
    "update_user": "users",
    "delete_user": "users",
    "add_column": None,
    "delete_column": None,
    "update_column": None,
    "update_column_config": None,
    "rename_column": None,
    "clear_columns": None,
    "clear_rows": None,
    "clear_logs": None,
}

#: 多态 target_id 列：(表, 类型列) → 类型值 → 引用的 PK 表
#: 注意：columns_meta 的日志 target_id 存的是列名（col_3 这类字符串键），
#: 不是 columns_meta.id 整数主键 —— 无需改写也不做悬空检查，故不列入。
#: 同理 backup 文件名 / system_config 等字符串键天然跳过（类型值不在 map 里）。
TARGET_ID_REF = {
    ("operations_log", "target_type"): {
        "rows_data": "rows_data",
        "users": "users",
        "pending_changes": "pending_changes",
    },
    ("audit_log", "target_table"): {
        "rows_data": "rows_data",
        "users": "users",
        "pending_changes": "pending_changes",
    },
}

#: JSON 内嵌 id：change_type → 引用的 PK 表（pending_changes.new_value/old_value 里 {"id": int}）
JSON_ID_REF = {
    "add_user": "users",
    "update_user": "users",
    "delete_user": "users",
    "insert": "rows_data",
    "update": "rows_data",
    "delete": "rows_data",
}


class MigrationError(Exception):
    """迁移失败；失败时旧表一定保持原样"""


# ──────────────────────── 工具 ────────────────────────


def _log(msg: str) -> None:
    print(f"[migrate-uuid7] {msg}", flush=True)


def get_table_columns(db, table: str) -> List[str]:
    return [c["name"] for c in db.get_table_columns(table)]


def table_exists(db, table: str) -> bool:
    """
    判断表是否存在。

    注意：SQLite 的 `PRAGMA table_info(<不存在>)` **不抛异常**，只返回空列表，
    所以不能靠 try/except 判断，必须显式查 sqlite_master；MySQL 走 information_schema。
    （与 migrate_jsonb.py 同一坑。）
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


def _column_type(db, table: str, column: str) -> str:
    """返回某列的声明类型（大写），找不到返回 ''"""
    try:
        for c in db.get_table_columns(table):
            if c.get("name") == column:
                return (c.get("type") or "").upper()
    except Exception:
        pass
    return ""


def is_migrated(db) -> bool:
    """
    判断是否已是 UUID TEXT PK 结构：8 张表全部存在且 id 列声明为 TEXT/CHAR/VARCHAR。

    幂等入口：已迁移则直接跳过，可反复执行。
    """
    for t in PK_TABLES:
        if not table_exists(db, t):
            return False
        if "INT" in _column_type(db, t, "id"):
            return False
    return True


def quote_ident(db, name: str) -> str:
    """按引擎引用标识符（SQLite 双引号 / MySQL 反引号）"""
    q = db.get_column_quote()
    return f"{q}{name}{q}"


def _remap_fk(value: Any, mapping: Dict[int, str]) -> Any:
    """整数 FK → uuid7；NULL/空/已是 uuid 字符串则原样保留；未知旧 id 原样保留并告警上游处理"""
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return value
    if is_valid_uuid7(s):
        return s
    try:
        old = int(s)
    except (ValueError, TypeError):
        return value
    return mapping.get(old, value)


def _remap_json_ids(obj: Any, mapping: Dict[int, str]) -> Any:
    """
    递归改写 JSON 里内嵌的 `{"id": <int>}`（只改恰好叫 id 且值为整数的键）。

    只处理 dict 的 "id" 键 + list 递归；其它键原样保留，避免误伤业务字段。
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "id" and isinstance(v, int) and not isinstance(v, bool):
                out[k] = mapping.get(v, v)
            else:
                out[k] = _remap_json_ids(v, mapping)
        return out
    if isinstance(obj, list):
        return [_remap_json_ids(v, mapping) for v in obj]
    return obj


def _unique_legacy_name(db, base: str) -> str:
    """legacy 表名去重：同名对象已存在时追加 _2/_3…，绝不覆盖已有备份表。"""
    if not table_exists(db, base):
        return base
    i = 1
    while True:
        i += 1
        cand = f"{base}_{i}"
        if not table_exists(db, cand):
            return cand


def _repair_dangling_fks(db, suffix: str = "") -> List[str]:
    """
    把指向不存在主键的 FK 置 NULL，返回修复明细。

    为什么需要：线上真实库里有历史脏值——例如 `operations_log.user_id = 99999`，
    对应用户早已被删除。这些行本身仍然有效（是日志/审核留痕），
    不该因为一个失效引用就卡住整库迁移。置 NULL 保住行、断掉悬空引用，
    并把修复条数写进迁移统计，让运维知道发生了数据清洗。

    置 NULL 之后若仍有悬空（说明不是「旧 id 缺失」而是映射逻辑 bug），
    由随后的 `_check_dangling_fks` 中止迁移。
    """
    fixed: List[str] = []

    def _q(name: str) -> str:
        return quote_ident(db, name)

    def _table(name: str) -> str:
        return _q(f"{name}{suffix}")

    def _fix(table: str, col: str, ref: str, where: str = "", params=()) -> None:
        cond = f" AND {where}" if where else ""
        sql = (
            f"UPDATE {_table(table)} SET {_q(col)} = NULL "
            f"WHERE {_q(col)} IS NOT NULL{cond} "
            f"AND {_q(col)} NOT IN (SELECT {_q('id')} FROM {_table(ref)} WHERE {_q('id')} IS NOT NULL)"
        )
        n = db.execute_query(sql, params)
        if n:
            fixed.append(f"{table}.{col}: {n} 行置 NULL（引用 {ref} 不存在）")

    for (table, col), ref in FK_MAP.items():
        _fix(table, col, ref)

    for change_type, ref in ROW_ID_REF.items():
        if ref is None:
            continue
        _fix("pending_changes", "row_id", ref, "change_type = ?", (change_type,))

    for (table, type_col), refs in TARGET_ID_REF.items():
        for type_value, ref in refs.items():
            _fix(table, "target_id", ref, f"{_q(type_col)} = ?", (type_value,))

    return fixed


# ──────────────────────── 主流程 ────────────────────────


def migrate(db, dry_run: bool = False) -> Dict[str, Any]:
    """
    执行迁移。返回统计信息。

    Raises:
        MigrationError: 校验不通过或执行出错；此时旧表保持原样
    """
    stats: Dict[str, Any] = {"status": "started"}

    for t in PK_TABLES:
        if not table_exists(db, t):
            raise MigrationError(f"{t} 表不存在，无可迁移内容")

    if is_migrated(db):
        _log("8 张表已是 TEXT PK 结构，跳过（幂等）")
        stats.update(status="already-migrated")
        return stats

    # ── 0. 盘点：每表行数 + 旧 id 列表 ──
    old_ids: Dict[str, List[int]] = {}
    row_counts: Dict[str, int] = {}
    for t in PK_TABLES:
        rows = db.fetch_all(f"SELECT id FROM {quote_ident(db, t)}")
        ids: List[int] = []
        for r in rows:
            v = r.get("id")
            if v is None:
                continue
            if isinstance(v, int) and not isinstance(v, bool):
                ids.append(v)
            else:
                try:
                    ids.append(int(str(v)))
                except (ValueError, TypeError):
                    pass
        old_ids[t] = ids
        row_counts[t] = len(rows)
        _log(f"{t}: {len(rows)} 行（整数 id {len(ids)} 个）")

    if dry_run:
        stats.update(status="dry-run", row_counts=row_counts)
        _log("dry-run 模式，未做任何修改")
        return stats

    # ── 1. 生成 old_int→uuid7 映射（8 张表各自独立命名空间）──
    id_map: Dict[str, Dict[int, str]] = {}
    for t in PK_TABLES:
        m: Dict[int, str] = {}
        for old in old_ids[t]:
            if old not in m:
                m[old] = uuid7()
        id_map[t] = m
        _log(f"{t}: 生成 {len(m)} 个 uuid7 映射")

    # ── 2. 逐表建 _new 表（TEXT PK）+ 搬运改写 ──
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ph = db.get_placeholder()
    moved: Dict[str, int] = {}

    for t in PK_TABLES:
        cols = get_table_columns(db, t)
        if "id" not in cols:
            raise MigrationError(f"{t} 表没有 id 列，无法迁移")

        # 取原表建表语句做模板：id 列改 TEXT PRIMARY KEY，其余列定义原样保留。
        # SQLite 下从 sqlite_master 取 sql；MySQL 下从 SHOW CREATE TABLE 取。
        new_table = f"{t}_new"
        if table_exists(db, new_table):
            _log(f"清理上次遗留的 {new_table}")
            db.execute_query(f"DROP TABLE {quote_ident(db, new_table)}")
        _create_new_table_like(db, t, new_table)
        _log(f"已创建 {new_table}")

        # 逐行搬运：id 按映射改写，FK/多态/JSON 按规则改写
        rows = db.fetch_all(f"SELECT * FROM {quote_ident(db, t)}")
        insert_sql = (
            f"INSERT INTO {quote_ident(db, new_table)} "
            f"({', '.join(quote_ident(db, c) for c in cols)}) "
            f"VALUES ({', '.join(ph for _ in cols)})"
        )
        n = 0
        for r in rows:
            new_row = _remap_row(db, t, dict(r), cols, id_map)
            db.execute_query(insert_sql, tuple(new_row[c] for c in cols))
            n += 1
        moved[t] = n
        _log(f"{t}: 已搬运 {n} 行 → {new_table}")

    # ── 3. 迁移后校验（行数 + FK 悬空检查）──
    for t in PK_TABLES:
        new_table = f"{t}_new"
        cnt = db.fetch_one(f"SELECT COUNT(*) AS c FROM {quote_ident(db, new_table)}") or {}
        if (cnt.get("c") or 0) != row_counts[t]:
            raise MigrationError(
                f"{t} 行数不一致: 旧 {row_counts[t]} vs 新 {cnt.get('c')}，"
                f"迁移中止（旧表未做任何修改）"
            )
    _log("行数校验通过")

    repaired = _repair_dangling_fks(db, "_new")
    if repaired:
        for msg in repaired:
            _log(f"  已修复悬空 FK（置 NULL）: {msg}")

    dangling = _check_dangling_fks(db, "_new", id_map)
    if dangling:
        for msg in dangling[:10]:
            _log(f"  悬空 FK: {msg}")
        raise MigrationError(
            f"{len(dangling)} 个悬空 FK，迁移中止（旧表未做任何修改）"
        )
    _log("FK 悬空检查通过")

    # ── 4. 逐表原子改名（旧表保留为 legacy）──
    # SQLite 注意：RENAME 会把原表索引一起带到 legacy 名下，
    # 且索引名全局唯一，所以改名前先记下原表索引 DDL，
    # 改名后先 DROP 同名旧索引再重建到新表上。
    legacy_tables: Dict[str, str] = {}
    saved_indexes: Dict[str, List[str]] = {}
    for t in PK_TABLES:
        saved_indexes[t] = _get_index_ddls(db, t)
    for t in PK_TABLES:
        new_table = f"{t}_new"
        legacy = _unique_legacy_name(db, f"{t}{LEGACY_PREFIX}{stamp}")
        if db.is_sqlite():
            db.execute_query(f"ALTER TABLE {quote_ident(db, t)} RENAME TO {quote_ident(db, legacy)}")
            db.execute_query(f"ALTER TABLE {quote_ident(db, new_table)} RENAME TO {quote_ident(db, t)}")
        else:
            db.execute_query(f"RENAME TABLE {quote_ident(db, t)} TO {quote_ident(db, legacy)}")
            db.execute_query(f"RENAME TABLE {quote_ident(db, new_table)} TO {quote_ident(db, t)}")
        legacy_tables[t] = legacy
        _log(f"{t}: 旧表已保留为 {legacy}")
        _recreate_indexes(db, t, saved_indexes.get(t, []))

    _log("迁移完成")
    stats.update(status="migrated", rows_moved=moved, legacy_tables=legacy_tables,
                 repaired_fks=repaired)
    return stats


def _create_new_table_like(db, table: str, new_table: str) -> None:
    """
    建 `<表>_new`：复用原表建表模板，唯独 id 列改 TEXT PK。

    SQLite：从 sqlite_master 取原 DDL，把 `id INTEGER PRIMARY KEY AUTOINCREMENT`
    替换成 `id TEXT PRIMARY KEY`，其余列定义（NOT NULL/DEFAULT/UNIQUE…）原样保留。
    MySQL：从 SHOW CREATE TABLE 取 DDL，同理把 id 改成 VARCHAR(36) PK。
    索引不在 DDL 里重建——SQLite 的 RENAME TABLE 会把原表索引自动带到新表名下，
    _new 表的索引在改名后由 SQLite 自动处理；为保险起见改名后调用方无需额外建索引。
    """
    if db.is_sqlite():
        row = db.fetch_one(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?", (table,)
        )
        if not row or not row.get("sql"):
            raise MigrationError(f"取不到 {table} 的建表语句")
        ddl = row["sql"]
        import re
        # 把新表名换上去（只换 CREATE TABLE 后面的第一个标识符）
        ddl = re.sub(
            r'CREATE\s+TABLE\s+("?' + re.escape(table) + r'"?)',
            f"CREATE TABLE {quote_ident(db, new_table)}",
            ddl, count=1, flags=re.IGNORECASE,
        )
        # id 列：INTEGER PRIMARY KEY AUTOINCREMENT → TEXT PRIMARY KEY
        pat = re.compile(r'"?id"?\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', re.IGNORECASE)
        if not pat.search(ddl):
            # 兼容无 AUTOINCREMENT 的 INTEGER PK（如测试夹具）
            pat = re.compile(r'"?id"?\s+INTEGER\s+PRIMARY\s+KEY', re.IGNORECASE)
        if not pat.search(ddl):
            raise MigrationError(f"{table} 的 DDL 里找不到整数 id 主键定义")
        ddl = pat.sub(f"{quote_ident(db, 'id')} TEXT PRIMARY KEY", ddl, count=1)
        db.execute_query(ddl)
    else:
        row = db.fetch_one(f"SHOW CREATE TABLE {quote_ident(db, table)}")
        if not row:
            raise MigrationError(f"取不到 {table} 的建表语句")
        ddl = row.get("Create Table") or next(iter(row.values()))
        import re
        ddl = re.sub(
            r'CREATE\s+TABLE\s+(`?' + re.escape(table) + r'`?)',
            f"CREATE TABLE {quote_ident(db, new_table)}",
            ddl, count=1, flags=re.IGNORECASE,
        )
        pat = re.compile(r'`?id`?\s+int[^,]*?primary\s+key', re.IGNORECASE)
        if pat.search(ddl):
            ddl = pat.sub(f"{quote_ident(db, 'id')} VARCHAR(36) PRIMARY KEY", ddl, count=1)
        else:
            raise MigrationError(f"{table} 的 DDL 里找不到整数 id 主键定义")
        db.execute_query(ddl)


def _get_index_ddls(db, table: str) -> List[str]:
    """取某表在 sqlite_master 里的显式索引 DDL（排除 sqlite_autoindex_）"""
    if not db.is_sqlite():
        return []
    try:
        rows = db.fetch_all(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='index' AND tbl_name = ? AND sql IS NOT NULL",
            (table,),
        )
    except Exception:
        return []
    out = []
    for r in rows or []:
        name = str(r.get("name") or "")
        sql = r.get("sql")
        if not sql or name.startswith("sqlite_autoindex_"):
            continue
        out.append(sql)
    return out


def _recreate_indexes(db, table: str, index_ddls: List[str]) -> None:
    """在新表（已改名为正式名）上重建索引。

    背景：SQLite 的 `ALTER TABLE RENAME` 会把原表索引一起带到 legacy 表名下，
    且索引名全局唯一——直接 CREATE 会因重名跳过（IF NOT EXISTS）或报错。
    所以先 DROP（删掉 legacy 表上的同名索引，数据不受影响），再按原 DDL 重建。
    回滚时 legacy 表数据完整，仅缺索引（不影响正确性，下次 init_db 可补）。
    """
    if not db.is_sqlite():
        return
    import re
    for ddl in index_ddls:
        m = re.search(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?("?\w+"?)',
                      ddl, flags=re.IGNORECASE)
        if m:
            idx_name = m.group(1).strip('"')
            try:
                db.execute_query(f"DROP INDEX IF EXISTS {quote_ident(db, idx_name)}")
            except Exception as e:
                _log(f"删旧索引 {idx_name} 失败（忽略）: {e}")
        try:
            # 去掉 IF NOT EXISTS 保险？保留原样即可，重名已删
            db.execute_query(ddl)
            _log(f"已重建索引: {ddl[:80]}...")
        except Exception as e:
            _log(f"重建索引失败（不阻断）: {e}")


def _remap_row(db, table: str, row: Dict[str, Any], cols: List[str],
               id_map: Dict[str, Dict[int, str]]) -> Dict[str, Any]:
    """对单行做 id/FK/多态/JSON 改写，返回新行 dict"""
    out = dict(row)

    # ① 主键 id
    v = out.get("id")
    if isinstance(v, int) and not isinstance(v, bool):
        out["id"] = id_map[table].get(v, uuid7())
    elif v is not None and not (isinstance(v, str) and is_valid_uuid7(v)):
        try:
            out["id"] = id_map[table].get(int(str(v)), uuid7())
        except (ValueError, TypeError):
            out["id"] = uuid7()

    # ② 普通 FK 列
    for (t, col), ref in FK_MAP.items():
        if t == table and col in out:
            out[col] = _remap_fk(out[col], id_map.get(ref, {}))

    # ③ pending_changes.row_id 多态（未知 change_type 原样保留，不置 NULL）
    if table == "pending_changes" and "row_id" in out:
        ct = str(out.get("change_type") or "")
        if ct in ROW_ID_REF:
            ref = ROW_ID_REF[ct]
            if ref is None:
                out["row_id"] = None
            else:
                out["row_id"] = _remap_fk(out.get("row_id"), id_map.get(ref, {}))
        # 未知类型：原样保留，靠悬空检查暴露

    # ④ 多态 target_id（字符串比对）
    for (t, type_col), type_map in TARGET_ID_REF.items():
        if t == table and "target_id" in out:
            ref = type_map.get(str(out.get(type_col) or ""))
            if ref is not None:
                out["target_id"] = _remap_fk(out.get("target_id"), id_map.get(ref, {}))

    # ⑤ JSON 内嵌 id（new_value / old_value）
    if table == "pending_changes":
        ct = str(out.get("change_type") or "")
        ref = JSON_ID_REF.get(ct)
        if ref is not None:
            for jk in ("new_value", "old_value"):
                raw = out.get(jk)
                if not raw:
                    continue
                try:
                    obj = json.loads(raw) if isinstance(raw, str) else raw
                except (ValueError, TypeError):
                    continue
                out[jk] = json.dumps(_remap_json_ids(obj, id_map.get(ref, {})), ensure_ascii=False)

    return out


def _check_dangling_fks(db, suffix: str, id_map: Dict[str, Dict[int, str]]) -> List[str]:
    """
    检查 _new 表里的 FK 是否悬空：改写后的 uuid 必须在对应 _new 表的 id 集合里。

    suffix="_new" 时查 `<表>_new`；verify 模式下 suffix="" 查正式表。
    """
    errors: List[str] = []
    # 收集新 id 集合
    new_ids: Dict[str, set] = {}
    for t in PK_TABLES:
        name = f"{t}{suffix}" if suffix else t
        try:
            rows = db.fetch_all(f"SELECT id FROM {quote_ident(db, name)}")
            new_ids[t] = {str(r.get("id")) for r in rows}
        except Exception:
            new_ids[t] = set()

    def _check(table: str, col: str, ref: str, extra_where: str = "",
               params: tuple = ()) -> None:
        name = f"{table}{suffix}" if suffix else table
        try:
            rows = db.fetch_all(
                f"SELECT id, {quote_ident(db, col)} AS v FROM {quote_ident(db, name)}"
                + (f" WHERE {extra_where}" if extra_where else ""),
                params if params else None,
            )
        except Exception:
            return
        for r in rows:
            v = r.get("v")
            if v is None or str(v).strip() == "":
                continue
            if str(v) not in new_ids.get(ref, set()):
                # 允许：uuid 格式但指向已删除行（历史脏数据）→ 只记一条摘要，不阻断？
                # 不：硬切要求零悬空，脏数据必须暴露。记为错误，由调用方决定中止。
                errors.append(f"{name}.{col}={v}（行 {r.get('id')}）在 {ref}.id 无对应")

    for (t, col), ref in FK_MAP.items():
        _check(t, col, ref)
    # row_id 多态：按 change_type 分组检查
    for ct, ref in ROW_ID_REF.items():
        if ref is not None:
            _check("pending_changes", "row_id", ref, "change_type = ?", (ct,))
    return errors


def verify(db) -> Dict[str, Any]:
    """只校验不改数据：报告当前结构 + FK 悬空情况"""
    result: Dict[str, Any] = {
        "is_migrated": is_migrated(db),
        "tables": {},
    }
    for t in PK_TABLES:
        if not table_exists(db, t):
            result["tables"][t] = {"exists": False}
            continue
        cols = get_table_columns(db, t)
        try:
            n = (db.fetch_one(f"SELECT COUNT(*) AS c FROM {quote_ident(db, t)}") or {}).get("c", 0)
        except Exception:
            n = -1
        result["tables"][t] = {
            "exists": True,
            "id_type": _column_type(db, t, "id"),
            "column_count": len(cols),
            "row_count": n,
        }
    result["ok"] = result["is_migrated"]
    if result["is_migrated"]:
        # 已迁移：在正式表上做悬空检查（id_map 传空，只查 uuid 是否在集合里）
        result["dangling"] = _check_dangling_fks(db, "", {})
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="INTEGER PK → UUIDv7 TEXT PK 迁移")
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
