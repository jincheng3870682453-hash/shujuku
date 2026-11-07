# -*- coding: utf-8 -*-
"""
drsync 变更事件流（Phase 4，背景见 docs/立项-存储层重构.md §0.1）。

事件单元 = 「整行 + updated_at/created_at + id」：
    {"table": <表名>, "id": <TEXT 主键>, "created_at": ..., "updated_at": ..., "row": {整行}}

导出（export_events）：
    从 SQLite 直接读 8 张同步表（system_config 属本机配置，不入同步流），
    以「自上次同步水位」做增量：since=None 全量对账；否则只导出
    updated_at / created_at 严格晚于水位的行（两列都存在的表任一命中即导出）。
    返回 JSON 可序列化的 list[dict]，TEXT 值原样。

导入（import_events）：
    按主键 upsert——id 不存在则整行插入；存在则「新者胜」：
      * 行级时间戳比较（updated_at 优先，退回 created_at；时间相同来者胜）；
      * rows_data.data 额外做 JSON 字段级 union 合并：两侧字段取并集，
        同字段值冲突时以 updated_at 较新一行为准（行级时间戳决定了
        做不到字段级 LWW，合并语义详见 docs/drsync.md）；
      * pending_changes 导入后保持源库原 status（不重置为默认『待审核』），
        本地较新的审核状态也不会被旧包覆盖（新者胜天然保护）。

所有数据库访问都走 backend.db_adapter.SQLiteAdapter（backend/__init__.py
禁止业务层直接 import sqlite3）；写侧整体包在一个显式事务里，要么全进要么全不进。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from ..db_adapter import DatabaseAdapter, SQLiteAdapter

#: 参与同步的 8 张表（顺序即导出顺序）
SYNC_TABLES = (
    "users",
    "columns_meta",
    "rows_data",
    "pending_changes",
    "operations_log",
    "audit_log",
    "backups",
    "ai_analysis_history",
)

#: 「新者胜」比较用的时间列，按优先级排序
_TS_COLUMNS = ("updated_at", "created_at")

__all__ = ["SYNC_TABLES", "export_events", "import_events", "compute_watermark"]


# ────────────────────── 内部工具 ──────────────────────


def _open(db: Union[str, DatabaseAdapter]) -> Tuple[DatabaseAdapter, bool]:
    """字符串/路径 → 新建 SQLiteAdapter（调用方负责关闭）；适配器 → 直接复用。"""
    if isinstance(db, DatabaseAdapter):
        return db, False
    adapter = SQLiteAdapter(os.fspath(db))
    adapter.connect()
    return adapter, True


def _row_ts(row: Dict[str, Any]) -> str:
    """行级时间戳：updated_at 优先，退回 created_at，都没有按最老处理。"""
    for col in _TS_COLUMNS:
        value = row.get(col)
        if value:
            return str(value)
    return ""


def _json_or_none(text: Any) -> Any:
    if text is None or text == "":
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _since_value(since: Union[None, str, Dict[str, str]], table: str) -> Optional[str]:
    """水位取值：None 全量；str 全表共用；dict 每表各自的水位。"""
    if since is None:
        return None
    if isinstance(since, dict):
        return since.get(table)
    return since


# ────────────────────── 导出 ──────────────────────


def export_events(db: Union[str, DatabaseAdapter],
                  since: Union[None, str, Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """
    从 SQLite 读 8 张同步表，生成增量事件流。

    Args:
        db: 库文件路径，或已连接的 DatabaseAdapter。
        since: 同步水位。None = 全量对账；str = 所有表共用的水位时间戳；
               dict = 每表各自的水位 {表名: 时间戳或 max(id)}（见 compute_watermark）。
    Returns:
        list[dict]，每项 {"table", "id", "created_at", "updated_at", "row"}，
        JSON 可序列化，TEXT 值原样。

    特例：columns_meta 没有任何时间戳列，无法按时间增量——
      * since 为 dict 且含它的水位（= max(id)）时按 `"id" > 水位` 增量
        （UUIDv7 字符串比较即时间比较）；
      * 否则整表导出做全量对账（字段定义行数极少，代价可忽略）。
    """
    adapter, owned = _open(db)
    result: List[Dict[str, Any]] = []
    try:
        for table in SYNC_TABLES:
            try:
                columns = [c["name"] for c in adapter.get_table_columns(table)]
            except Exception:
                continue  # 旧库缺表：跳过该表，不阻塞其余表的同步
            ts_cols = [c for c in _TS_COLUMNS if c in columns]
            where = ""
            params: Tuple = ()
            if ts_cols:
                mark = _since_value(since, table)
                if mark:
                    where = " WHERE " + " OR ".join(f'"{c}" > ?' for c in ts_cols)
                    params = tuple([mark] * len(ts_cols))
            elif isinstance(since, dict):
                # 无时间戳列的表（columns_meta）：按 id 水位增量（UUIDv7 时间有序）
                mark = since.get(table)
                if mark:
                    where = ' WHERE "id" > ?'
                    params = (mark,)
            order_col = f'"{ts_cols[0]}"' if ts_cols else '"id"'
            col_list = ", ".join(f'"{c}"' for c in columns)
            sql = f'SELECT {col_list} FROM "{table}"{where} ORDER BY {order_col}, "id"'
            for row in adapter.fetch_all(sql, params):
                result.append({
                    "table": table,
                    "id": row.get("id"),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "row": row,
                })
    finally:
        if owned:
            adapter.close()
    return result


def compute_watermark(events: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    从一批事件算出每表水位：有时间戳的表取 max(updated_at/created_at)，
    无时间戳的表（columns_meta）取 max(id)。结果直接可作为
    export_events(db, since=...) 的 dict 水位。
    """
    marks: Dict[str, Dict[str, str]] = {}
    for event in events:
        table = event.get("table")
        row_id = event.get("id")
        if table not in SYNC_TABLES or not row_id:
            continue
        ts = event.get("updated_at") or event.get("created_at") or ""
        kind_value = ("ts", str(ts)) if ts else ("id", str(row_id))
        prev = marks.get(table)
        if prev is None or kind_value[1] > prev[1]:
            marks[table] = kind_value
    return {table: value for table, (kind, value) in marks.items()}


# ────────────────────── 导入 ──────────────────────


def import_events(db: Union[str, DatabaseAdapter],
                  events: List[Dict[str, Any]],
                  source_node: str = "") -> Dict[str, Any]:
    """
    按主键 upsert 导入事件流，返回统计 dict。

    统计项：total / inserted / updated / merged(rows_data 合并) / skipped(旧者放弃) /
    unknown_table / source_node / by_table(分表明细)。
    整个导入在一个显式事务里执行，中途失败全部回滚。
    """
    adapter, owned = _open(db)
    stats: Dict[str, Any] = {
        "total": 0,
        "inserted": 0,
        "updated": 0,
        "merged": 0,
        "skipped": 0,
        "unknown_table": 0,
        "source_node": source_node,
        "by_table": {},
    }
    try:
        with adapter.transaction():
            for event in events:
                stats["total"] += 1
                table = event.get("table")
                if table not in SYNC_TABLES:
                    stats["unknown_table"] += 1
                    continue
                row = dict(event.get("row") or {})
                row_id = row.get("id") or event.get("id")
                if not row_id:
                    stats["skipped"] += 1
                    continue
                per = stats["by_table"].setdefault(
                    table, {"inserted": 0, "updated": 0, "merged": 0, "skipped": 0})
                # 字段级防御：事件里多出来的列（对端 schema 更新）直接丢弃
                columns = {c["name"] for c in adapter.get_table_columns(table)}
                row = {k: v for k, v in row.items() if k in columns}
                existing = adapter.fetch_one(
                    f'SELECT * FROM "{table}" WHERE "id" = ?', (row_id,))
                if existing is None:
                    payload = dict(row)
                    payload["id"] = row_id
                    adapter.insert(table, payload)
                    stats["inserted"] += 1
                    per["inserted"] += 1
                    continue
                incoming_ts = _row_ts(row) or _row_ts(event)
                existing_ts = _row_ts(existing)
                if table == "rows_data":
                    merged_payload = _merged_rows_data_payload(
                        row, existing, incoming_newer=incoming_ts >= existing_ts,
                        columns=columns)
                    if _rows_equal(merged_payload, existing):
                        # 合并后无变化（含幂等重放 / 旧包无贡献）：不写库，计 skipped
                        stats["skipped"] += 1
                        per["skipped"] += 1
                    else:
                        _update_row(adapter, "rows_data", row_id, merged_payload, columns)
                        stats["merged"] += 1
                        per["merged"] += 1
                elif incoming_ts >= existing_ts:
                    _update_row(adapter, table, row_id, row, columns)
                    stats["updated"] += 1
                    per["updated"] += 1
                else:
                    # 本地行较新：放弃来者。pending_changes 的本地审核状态由此不被旧包覆盖
                    stats["skipped"] += 1
                    per["skipped"] += 1
    finally:
        if owned:
            adapter.close()
    return stats


def _update_row(adapter: DatabaseAdapter, table: str, row_id: str,
                row: Dict[str, Any], columns: set) -> int:
    fields = {k: v for k, v in row.items() if k in columns and k != "id"}
    if not fields:
        return 0
    sets = ", ".join(f'"{k}" = ?' for k in fields)
    params = tuple(fields.values()) + (row_id,)
    return adapter.execute_query(f'UPDATE "{table}" SET {sets} WHERE "id" = ?', params)


def _merged_rows_data_payload(incoming: Dict[str, Any], existing: Dict[str, Any],
                              incoming_newer: bool, columns: set) -> Dict[str, Any]:
    """
    rows_data 冲突合并：非 data 列整行新者胜；data 列做 JSON 字段级 union。

    返回不含 id、已按本地表结构过滤的 payload；调用方负责与 existing 比较后写库。
    """
    base = incoming if incoming_newer else existing
    payload = {k: v for k, v in base.items()
               if k in columns and k != "data" and k != "id"}
    payload["data"] = _merge_data_column(existing.get("data"), incoming.get("data"),
                                         incoming_newer)
    return payload


def _rows_equal(candidate: Dict[str, Any], existing: Dict[str, Any]) -> bool:
    """candidate 的每个键值都与 existing 一致（candidate 已不含 id）。"""
    return all(existing.get(k) == v for k, v in candidate.items())


def _merge_data_column(old_text: Any, new_text: Any, incoming_newer: bool) -> str:
    """
    rows_data.data 的 JSON 合并：字段级 union，同字段冲突时较新一侧胜。

    * 两侧都能解析成 JSON 对象 → 取字段并集：先铺「旧侧」，再用「新侧」覆盖，
      于是新侧改过的字段胜出、只有旧侧才有的字段保留（A 改姓名 + B 改部门都活着）。
    * 任一侧不是 JSON 对象（空/损坏/标量）→ 整体取较新的非空侧。
    """
    old = _json_or_none(old_text)
    new = _json_or_none(new_text)
    if isinstance(old, dict) and isinstance(new, dict):
        loser, winner = (old, new) if incoming_newer else (new, old)
        merged = dict(loser)
        merged.update(winner)
        return json.dumps(merged, ensure_ascii=False)
    if incoming_newer:
        chosen = new_text if new_text is not None else (old_text if old_text is not None else "{}")
    else:
        chosen = old_text if old_text is not None else (new_text if new_text is not None else "{}")
    return chosen if isinstance(chosen, str) else json.dumps(chosen, ensure_ascii=False)
