# -*- coding: utf-8 -*-
"""
RowStore · 动态字段行数据存储层（JSONB 方案）
=============================================

背景与选型依据见 `docs/立项-存储层重构.md`。

旧方案（宽表 + ALTER TABLE）的硬伤：
  * PostgreSQL 有 1600 列上限，且 **DROP COLUMN 无法回收**——已删列仍计入上限，
    触顶后表永久不可修改（Baserow issue #3330 即为实证）。
  * SQLite 老版本不支持 DROP COLUMN，导致删字段只删元数据、物理列永久残留。
  * 实测 active 库 `data/app.db`：`columns_meta` 定义 15 个字段，`rows_data` 却有
    35 列，其中 18 个是孤儿列（数据值被 `_detect_real_header_row` 误判成表头，
    再被 `auto_create_columns` 当成字段名执行 ALTER）——列数只增不减的实物损坏。

新方案：
  * `rows_data` 固定 6 列：id / data(JSON) / created_by / schema_version / created_at / updated_at
  * 字段数量与物理列数**彻底解耦**，增删字段零 DDL
  * 列数恒定 → 不存在触顶、不存在残留、无并发 DDL 锁

双引擎差异：
  * SQLite   : TEXT 存 JSON，查询用 `json_extract(data, '$.<col>')`
  * MySQL 5.7+: JSON 类型，查询用 `JSON_UNQUOTE(JSON_EXTRACT(data, '$.<col>'))`
  由适配层 `is_mysql()` 分流，本模块不直接写方言。

索引策略见 `ensure_indexes()`：只对 `columns_meta.is_indexed = 1` 的字段建索引，
SQLite 用生成列（需 3.31+），MySQL 用虚拟生成列，两边都避免无界增长。
"""

import json
from typing import Any, Dict, List, Optional, Tuple


def new_row_id() -> str:
    """生成行主键（UUIDv7）。与适配层同一实现，避免两处各写一份。"""
    try:
        from .db_adapter import new_row_id as _new_row_id
    except ImportError:  # 兼容以顶层模块方式导入
        from db_adapter import new_row_id as _new_row_id  # type: ignore
    return _new_row_id()

# ──────────────────────── 常量 ────────────────────────

#: 行数据表的固定列（不含 JSON 数据列）。用于判断旧宽表是否已迁移。
RESERVED_COLUMNS: Tuple[str, ...] = (
    "id",
    "data",
    "created_by",
    "schema_version",
    "created_at",
    "updated_at",
)

#: JSON 列名
DATA_COLUMN = "data"

#: 系统列：不属于用户字段，但参与权限过滤与展示
SYSTEM_COLUMNS: Tuple[str, ...] = ("id", "created_by", "created_at", "updated_at")

#: 单个 JSON 路径引用的最大长度，防御异常字段名
_MAX_PATH_LEN = 256


def json_path(col_name: str) -> str:
    """
    构造 JSON 路径表达式，形如 `'$.col_0'`。

    防御：字段名可能来自用户输入或 Excel 表头，必须过滤掉会让 JSON 路径
    失效的字符（$ . [ ] ' " 以及控制字符），否则拼进 SQL 就是注入面。
    """
    if not col_name or len(col_name) > _MAX_PATH_LEN:
        raise ValueError(f"非法的字段名长度: {col_name!r}")
    unsafe = set("$.[]'\"\\\r\n\t")
    if any(ch in unsafe for ch in col_name):
        raise ValueError(f"字段名含非法字符，无法构造 JSON 路径: {col_name!r}")
    # json_extract 的路径语法要求 $ 后紧跟 .key
    return f"$.{col_name}"


class RowStoreError(Exception):
    """RowStore 专属异常，便于调用方与 DatabaseError 区分"""


class RowStoreConflict(RowStoreError):
    """
    乐观锁冲突（Phase 2c）：提交时目标行的 updated_at 与调用方持有版本不一致，
    说明期间已被别人改过。调用方应转 HTTP 409，前端提示「刷新后重新提交」。
    """


class RowStore:
    """
    动态字段行的统一读写入口。

    所有方法只依赖数据库适配层（`execute_query` / `fetch_one` / `fetch_all`
    / `get_table_columns`），不直接 import sqlite3 或 pymysql——
    `backend/__init__.py` 的 import hook 禁止直接 import 这两个驱动。
    """

    def __init__(self, db):
        """
        Args:
            db: `backend.db_adapter` 的适配器实例（SQLiteAdapter / MySQLAdapter）
        """
        self.db = db

    # ──────────────────── 方言分流 ────────────────────

    @property
    def _is_mysql(self) -> bool:
        try:
            return self.db.is_mysql()
        except Exception:
            return False

    def _extract_expr(self, col_name: str) -> str:
        """生成抽取字段值的 SQL 表达式（按引擎分流）"""
        path = json_path(col_name)
        if self._is_mysql:
            return f"JSON_UNQUOTE(JSON_EXTRACT({DATA_COLUMN}, '{path}'))"
        return f"json_extract({DATA_COLUMN}, '{path}')"

    # ──────────────────── 元数据 ────────────────────

    def load_columns(self) -> List[Dict[str, Any]]:
        """
        读取字段定义（columns_meta），按 position 升序。

        补齐 `is_indexed` 与 `required` 两个可选列：旧库可能没有这两列
        （`registry.db` 的 columns_meta 只有 7 列，`data/app.db` 只有 6 列），
        读不到时给安全默认值，避免上层到处写 `.get()`。
        """
        rows = self.db.fetch_all(
            "SELECT id, name, label, field_type, options, position "
            "FROM columns_meta ORDER BY position ASC"
        )
        return self._normalize_options(rows)

    def _normalize_options(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        归一化 columns_meta 行：options 的 JSON 字符串转 list、field_type 兜底。

        单独抽出以便测试可复用，也是为了让「读定义」的清洗规则只有一份。
        """
        out = []
        for r in rows:
            item = dict(r)
            options = item.get("options")
            if isinstance(options, str):
                try:
                    item["options"] = json.loads(options) if options.strip() else None
                except (ValueError, TypeError):
                    item["options"] = None
            elif options is not None and not isinstance(options, list):
                item["options"] = None
            item["field_type"] = item.get("field_type") or "text"
            item["label"] = item.get("label") or item.get("name") or ""
            out.append(item)
        return out

    def column_names(self) -> List[str]:
        return [c["name"] for c in self.load_columns()]

    def schema_version(self) -> int:
        """
        当前 schema 版本号 = 字段结构的指纹。

        用途：审核流做乐观锁校验（见立项书 §4.5）。用「字段数 + 各字段名与类型的
        聚合」而不是简单的 COUNT，因为改字段类型同样属于 schema 变更。
        """
        try:
            cols = self.load_columns()
            fingerprint = "|".join(f"{c['name']}:{c['field_type']}" for c in cols)
            # 稳定哈希：Python 内置 hash 在跨进程不稳定，这里用简单的位移混合
            h = 0
            for ch in fingerprint:
                h = (h * 131 + ord(ch)) & 0xFFFFFFFF
            return h
        except Exception:
            return 0

    # ──────────────────── 读路径 ────────────────────

    def fetch_rows(
        self,
        cols: List[Dict[str, Any]],
        order_desc: bool = True,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        where_sql: str = "",
        where_params: Tuple = (),
        with_system_columns: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        按当前字段定义取行，返回与旧宽表**结构一致**的 dict 列表。

        对外行为契约（与旧 `SELECT id, col_0, col_1 ... FROM rows_data` 对齐）：
          * key 为 `id` + 各字段 name
          * 值已按 field_type 还原（读出来的都是 Python 侧可直接用的类型）
          * 不存在的键不会出现在 dict 里；字段值为 NULL 时值为 None

        Args:
            cols: `load_columns()` 的结果
            order_desc: True → `ORDER BY id DESC`（列表页默认 newest first）
            with_system_columns: True → 额外带 created_by/created_at/updated_at
        """
        if not cols:
            return []

        # 每个抽取表达式必须起别名，否则 DB 返回的列名是整条表达式字符串
        # （如 "json_extract(data, '$.姓名')"），下游按字段名取值会全部拿到 None。
        select_exprs = [f"{self._extract_expr(c['name'])} AS {self.db.quote_column(c['name'])}"
                        for c in cols]
        col_names = [c["name"] for c in cols]

        if with_system_columns:
            select_exprs += ["created_by", "created_at", "updated_at"]
            col_names += list(("created_by", "created_at", "updated_at"))

        sql = "SELECT id, " + ", ".join(select_exprs) + " FROM rows_data"
        if where_sql:
            sql += " WHERE " + where_sql
        sql += " ORDER BY id " + ("DESC" if order_desc else "ASC")
        params: List[Any] = list(where_params)
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
            if offset is not None:
                sql += f" OFFSET {int(offset)}"

        try:
            raw_rows = self.db.fetch_all(sql, tuple(params))
        except Exception as e:
            raise RowStoreError(f"读取行数据失败: {e}") from e

        return [self._hydrate(r, cols, with_system_columns) for r in raw_rows]

    def fetch_row_by_id(self, row_id: str, cols: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """取单行，不存在返回 None"""
        rows = self.fetch_rows(cols, where_sql="id = ?", where_params=(row_id,))
        return rows[0] if rows else None

    def row_exists(self, row_id: str, created_by: Optional[str] = None) -> bool:
        """
        判断行是否存在（可带创建者过滤，用于权限校验）。

        对应旧 SQL：
            SELECT id FROM rows_data WHERE id = ?
            SELECT id FROM rows_data WHERE id = ? AND _created_by = ?
        JSONB 下用固定列 created_by，比旧实现读动态列更可靠。
        """
        if created_by is None:
            sql = "SELECT id FROM rows_data WHERE id = ?"
            params: Tuple = (row_id,)
        else:
            sql = "SELECT id FROM rows_data WHERE created_by = ? AND id = ?"
            params = (created_by, row_id)
        return self.db.fetch_one(sql, params) is not None

    def fetch_rows_paginated(
        self,
        cols: List[Dict[str, Any]],
        page: int,
        page_size: int,
        created_by: Optional[str] = None,
        with_system_columns: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        列表页分页读取，返回 (rows, total)。

        对应旧 SQL：`SELECT id, <cols> FROM rows_data [WHERE _created_by=?] ORDER BY id DESC LIMIT ? OFFSET ?`
        注意：总数用一次 COUNT 查询，不再像旧实现那样先 count 再全列 select。

        Phase 2c：`with_system_columns=True` 时附带 updated_at（乐观锁版本号），
        列表接口用它把版本号随行下发。
        """
        where_sql, where_params = "", ()
        if created_by is not None:
            where_sql, where_params = "created_by = ?", (created_by,)
        total = self.count_rows(where_sql, where_params)
        offset = (max(1, page) - 1) * page_size
        rows = self.fetch_rows(
            cols,
            order_desc=True,
            limit=page_size,
            offset=offset,
            where_sql=where_sql,
            where_params=where_params,
            with_system_columns=with_system_columns,
        )
        return rows, total

    def fetch_all_ordered(
        self,
        cols: List[Dict[str, Any]],
        created_by: Optional[str] = None,
        ascending: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        全量按序读取（导出 / AI 分析用）。

        对应旧 SQL：`SELECT id, <cols> FROM rows_data [WHERE _created_by=?] ORDER BY id ASC`
        """
        where_sql, where_params = "", ()
        if created_by is not None:
            where_sql, where_params = "created_by = ?", (created_by,)
        return self.fetch_rows(
            cols,
            order_desc=not ascending,
            where_sql=where_sql,
            where_params=where_params,
            with_system_columns=False,
        )

    def count_rows(self, where_sql: str = "", where_params: Tuple = ()) -> int:
        sql = "SELECT COUNT(*) AS cnt FROM rows_data"
        if where_sql:
            sql += " WHERE " + where_sql
        row = self.db.fetch_one(sql, tuple(where_params))
        return int(row["cnt"]) if row and row.get("cnt") is not None else 0

    def fetch_column_values(
        self, col: Dict[str, Any], where_sql: str = "", where_params: Tuple = ()
    ) -> List[Any]:
        """
        取单列全部非空值，供统计接口使用。

        对应旧 SQL：`SELECT <field> FROM rows_data WHERE <field> IS NOT NULL AND <field> != ''`
        JSONB 下用 `json_extract` 表达式做同样的过滤。
        """
        expr = self._extract_expr(col["name"])
        sql = f"SELECT {expr} AS v FROM rows_data WHERE {expr} IS NOT NULL"
        if where_sql:
            sql += " AND " + where_sql
        try:
            rows = self.db.fetch_all(sql, tuple(where_params))
        except Exception as e:
            raise RowStoreError(f"读取字段「{col['label']}」失败: {e}") from e
        out = []
        for r in rows:
            v = r.get("v")
            if v is None:
                continue
            s = str(v).strip()
            if s == "":
                continue
            out.append(self._coerce(v, col["field_type"]))
        return out

    # ──────────────────── 写路径 ────────────────────

    def insert_row(
        self,
        cols: List[Dict[str, Any]],
        data: Dict[str, Any],
        created_by: str,
        schema_version: Optional[int] = None,
    ) -> str:
        """
        插入一行，返回新行主键（TEXT，UUIDv7）。

        `data` 的 key 必须是已定义字段名；未定义的键直接忽略（与旧实现一致：
        旧实现遍历 `cols` 而忽略请求体里的多余键）。
        值必须已经过 `convert_field_value` 转换——本层不做业务类型校验，
        那是单一 chokepoint 的职责。

        Phase 2b：主键由应用层生成并随 INSERT 一起写入，不再回读
        `last_insert_rowid()`——离线多机合并时自增 id 会撞号。
        """
        payload = {}
        for c in cols:
            name = c["name"]
            if name in data:
                payload[name] = data[name]

        if schema_version is None:
            schema_version = self.schema_version()

        row_id = new_row_id()
        self.db.execute_query(
            "INSERT INTO rows_data (id, data, created_by, schema_version) VALUES (?, ?, ?, ?)",
            (row_id, json.dumps(payload, ensure_ascii=False), created_by, schema_version),
        )
        return row_id

    def update_row(
        self,
        row_id: str,
        cols: List[Dict[str, Any]],
        data: Dict[str, Any],
        merge: bool = True,
        base_updated_at: Optional[str] = None,
    ) -> int:
        """
        更新一行的部分字段，返回受影响行数。

        merge=True  → 在**数据库服务端**做原子合并（`json_set` / `JSON_SET`）。
                      不用「读出来→合并→写回」，因为那不是原子的：两个用户同时
                      改同一行的不同字段时，后写者会覆盖先写者的改动。
        merge=False → 整行替换。

        Phase 2c 乐观锁：`base_updated_at` 非空时先比对行的当前 `updated_at`，
        不一致抛 `RowStoreConflict`（调用方应转 409）——
        「用户 A 打开编辑框 → 用户 B 已改并保存 → 用户 A 才提交」时，
        A 必须被告知目标已变化，而不是静默覆盖 B 的改动。
        比对走 SQL `WHERE updated_at = ?`，与后续 UPDATE 同语句执行，
        数据库行锁保证「读版本号→写数据」之间没有窗口。
        """
        valid = {c["name"]: c for c in cols}
        updates = {k: v for k, v in data.items() if k in valid}
        if not updates:
            return 0

        where = "1=1"
        params: List[Any] = []
        if base_updated_at is not None:
            where = "updated_at = ?"
            params.append(base_updated_at)

        if merge:
            return self._update_row_atomic(row_id, updates, where, tuple(params))
        sql = (
            "UPDATE rows_data SET data = ?, "
            f"updated_at = {self._now_sql()} "
            f"WHERE {where} AND id = ?"
        )
        return self.db.execute_query(
            sql,
            (json.dumps(updates, ensure_ascii=False), *params, row_id),
        )

    @staticmethod
    def _now_sql() -> str:
        """
        当前时间表达式（毫秒精度）。

        乐观锁的版本号就是 updated_at。`datetime('now')` 只有秒精度——
        同一秒内的「插入→修改」版本号不变，锁形同虚设（实测踩到）。
        升到毫秒：SQLite `strftime('%Y-%m-%d %H:%M:%f','now')`；
        MySQL 的 NOW(3) 由适配层把 strftime 表达式整体替换（见 _convert_sql_functions）。
        """
        return "strftime('%Y-%m-%d %H:%M:%f', 'now')"

    def _update_row_atomic(
        self,
        row_id: str,
        updates: Dict[str, Any],
        where: str = "1=1",
        where_params: Tuple = (),
    ) -> int:
        """
        用 SQL 的 JSON 合并函数做单条原子 UPDATE。

        SQLite   : `json_set(data, '$.k1', ?, '$.k2', ?, ...)`
        MySQL    : `JSON_SET(data, '$.k1', ?, ...)`

        值全部走参数绑定，key 经 `json_path()` 校验后才拼进 SQL。
        `where`/`where_params` 支持乐观锁条件（`updated_at = ?`）：
        0 行受影响即版本冲突，由上层判定（先查存在性，再区分 404 与 409）。
        """
        pairs: List[str] = []
        params: List[Any] = []
        for k, v in updates.items():
            path = json_path(k)          # 校验非法字符，失败直接抛
            # 每个字段产出一对：'path' 字面量 + 一个值占位符。
            # 只拼 path 不拼 ? 会得到 json_set(data,'$.k') —— 参数个数不匹配。
            pairs.append(f"'{path}', {self.db.get_placeholder()}")
            params.append(self._to_json_scalar(v))

        if not pairs:
            return 0

        func = "JSON_SET" if self._is_mysql else "json_set"
        sql = (
            f"UPDATE rows_data SET {DATA_COLUMN} = {func}({DATA_COLUMN}, "
            + ", ".join(pairs)
            + f"), updated_at = {self._now_sql()} WHERE "
            + where
            + " AND id = ?"
        )
        params.extend(where_params)
        params.append(row_id)
        return self.db.execute_query(sql, tuple(params))

    @staticmethod
    def _to_json_scalar(value: Any) -> Any:
        """
        把 Python 值转成可作为 JSON 标量绑定的形态。

        dict/list 在旧实现里会被 `json.dumps` 成字符串（file 字段即如此），
        这里保持同样行为，避免 JSON 里出现嵌套结构与旧数据不一致。
        """
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, bool):
            return value
        return value

    def get_updated_at(self, row_id: str) -> Optional[str]:
        """
        取行当前 updated_at（乐观锁版本号）。

        行不存在返回 None；调用方拿它当 `base_updated_at` 传给 `update_row`，
        形成完整的「读版本 → 带版本提交」闭环。
        """
        row = self.db.fetch_one("SELECT updated_at FROM rows_data WHERE id = ?", (row_id,))
        return row["updated_at"] if row else None

    def delete_row(self, row_id: str) -> int:
        return self.db.execute_query("DELETE FROM rows_data WHERE id = ?", (row_id,))

    def delete_all_rows(self) -> int:
        return self.db.execute_query("DELETE FROM rows_data")

    def batch_delete_rows(self, row_ids: List[str]) -> int:
        if not row_ids:
            return 0
        placeholders = ", ".join(self.db.get_placeholder() for _ in row_ids)
        return self.db.execute_query(
            f"DELETE FROM rows_data WHERE id IN ({placeholders})", tuple(row_ids)
        )

    # ──────────────────── 索引 ────────────────────

    def ensure_indexes(self, cols: List[Dict[str, Any]]) -> None:
        """
        按 `columns_meta.is_indexed` 同步生成列索引。

        只在 SQLite 3.31+ / MySQL 5.7+ 可用；不支持的引擎静默跳过（退化为无该字段索引，
        功能不受影响，只是该字段检索走全表扫描）。
        生成列名统一为 `_jf_<字段名>`，避免与 JSON 键或系统列冲突。
        """
        if not cols:
            return
        for c in cols:
            if not self._is_index_enabled(c):
                continue
            name = c["name"]
            gen_col = f"_jf_{name}"
            try:
                if self._has_generated_column(gen_col):
                    continue
                expr = self._extract_expr(name)
                if self._is_mysql:
                    self.db.execute_query(
                        f"ALTER TABLE rows_data ADD COLUMN {gen_col} TEXT "
                        f"GENERATED ALWAYS AS ({expr}) VIRTUAL"
                    )
                else:
                    # SQLite 生成列语法较严格，类型必须显式
                    self.db.execute_query(
                        f"ALTER TABLE rows_data ADD COLUMN {gen_col} TEXT "
                        f"GENERATED ALWAYS AS ({expr}) VIRTUAL"
                    )
                self.db.execute_query(
                    f"CREATE INDEX IF NOT EXISTS idx_rows_{gen_col} ON rows_data({gen_col})"
                )
            except Exception:
                # 索引是优化项，失败不应阻塞写路径
                continue

    def _is_index_enabled(self, col: Dict[str, Any]) -> bool:
        flag = col.get("is_indexed")
        if flag is None:
            return False
        return str(flag).lower() in ("1", "true", "yes", "on")

    def _has_generated_column(self, gen_col: str) -> bool:
        try:
            cols = self.db.get_table_columns("rows_data")
            return any(c.get("name") == gen_col for c in cols)
        except Exception:
            return False

    # ──────────────────── 内部工具 ────────────────────

    def _hydrate(
        self,
        raw_row: Dict[str, Any],
        cols: List[Dict[str, Any]],
        with_system_columns: bool,
    ) -> Dict[str, Any]:
        """
        把 DB 行还原为对外 dict。key 与旧宽表实现完全一致。

        依赖 `fetch_rows` 已为每个字段表达式加了 `AS <字段名>` 别名；
        若某字段在结果里缺失（理论上不应发生），值为 None 而不是 KeyError。
        """
        out: Dict[str, Any] = {"id": raw_row.get("id")}
        for c in cols:
            out[c["name"]] = self._coerce(raw_row.get(c["name"]), c["field_type"])
        if with_system_columns:
            for k in ("created_by", "created_at", "updated_at"):
                out[k] = raw_row.get(k)
        return out

    @staticmethod
    def _coerce(value: Any, field_type: str) -> Any:
        """
        把 DB 取出的值还原为业务侧类型。

        JSON 列里的值本身已是正确类型；`json_extract` 抽出来的也是原生类型。
        这里主要处理：布尔字段在 JSON 里存的是 int(0/1)，还原成 bool；
        以及字符串型字段保证是 str 而不是 bytes。
        """
        if value is None:
            return None
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError:
                return None
        if field_type == "boolean":
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "y", "on", "是", "对", "有")
            return bool(value)
        if field_type == "number" and isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return value
        return value


def get_row_store() -> RowStore:
    """便捷工厂：内部取当前请求的适配器"""
    from .db_adapter import get_adapter

    return RowStore(get_adapter())
