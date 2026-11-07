# -*- coding: utf-8 -*-
"""
数据库适配层 - 支持 SQLite 和 MySQL 双引擎无缝切换

提供统一的 DatabaseAdapter 抽象接口，屏蔽底层数据库差异。
业务层统一使用 ? 占位符和 SQLite 函数名，适配器内部自动转换为目标数据库格式。

使用方式:
    from backend.db_adapter import get_adapter

    adapter = get_adapter()                          # 自动根据配置返回适配器
    rows = adapter.fetch_all("SELECT * FROM users WHERE role = ?", ("admin",))
    adapter.close()
"""

import os
import re
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────── 主键生成 ────────────────────────


def new_row_id() -> str:
    """
    生成新的 TEXT 主键（UUIDv7，见 `backend/uuid7.py`）。

    Phase 2b 起主键不再由数据库自增：`insert()` 在插入前用本函数生成 id。
    两个理由：
      * 离线多机各自写库时 AUTOINCREMENT 会生成相同 id，合并即冲突；
        UUIDv7 可离线生成且全局唯一。
      * MySQL 的 `LAST_INSERT_ID()` / PostgreSQL 的 `lastval()` 都与连接绑定，
        并发或连接池复用下回读到的可能不是刚插入的那一行。
    """
    try:
        from .uuid7 import uuid7
    except ImportError:  # 兼容以顶层模块方式导入（脚本 / 独立测试）
        from uuid7 import uuid7  # type: ignore
    return uuid7()


# ──────────────────────── 统一异常类 ────────────────────────


class DatabaseError(Exception):
    """
    统一的数据库异常基类。

    将所有底层数据库驱动异常（sqlite3.Error / pymysql.Error）
    转换为此类型，便于业务层统一处理。

    Attributes:
        original_error: 原始的底层异常对象（如有）
    """

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class ConnectionError(DatabaseError):
    """数据库连接失败异常"""
    pass


class TimeoutError(DatabaseError):
    """数据库操作超时异常"""
    pass


class DeadlockError(DatabaseError):
    """数据库死锁异常"""
    pass


# ──────────────────────── 抽象基类 ────────────────────────


class DatabaseAdapter(ABC):
    """
    数据库适配器抽象基类。

    定义所有子类必须实现的标准接口，确保 SQLite 和 MySQL 之间
    可以无缝切换而不影响业务代码。
    """

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，自动关闭连接"""
        self.close()
        return False

    # ──────── 引擎检测 ────────

    def is_mysql(self) -> bool:
        """当前适配器是否为 MySQL 引擎"""
        return False

    def is_sqlite(self) -> bool:
        """当前适配器是否为 SQLite 引擎"""
        return False

    # ──────── 连接管理 ────────

    @abstractmethod
    def connect(self) -> None:
        """
        建立数据库连接。
        Raises:
            ConnectionError: 连接失败时抛出
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """关闭数据库连接，释放资源"""
        ...

    # ──────── 核心查询方法 ────────

    @abstractmethod
    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> int:
        """
        执行非查询 SQL 语句（INSERT / UPDATE / DELETE / DDL）。
        Args:
            sql: SQL 语句，使用 ? 作为占位符
            params: 参数元组，与 ? 一一对应
        Returns:
            int: 受影响的行数
        Raises:
            DatabaseError: 执行失败时抛出
        """
        ...

    @abstractmethod
    def fetch_one(self, sql: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """
        查询并返回单行记录。
        Args:
            sql: SQL 查询语句，使用 ? 作为占位符
            params: 参数元组
        Returns:
            Optional[Dict[str, Any]]: 查询结果字典，无结果时返回 None
        """
        ...

    @abstractmethod
    def fetch_all(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        查询并返回全部结果行。
        Args:
            sql: SQL 查询语句，使用 ? 作为占位符
            params: 参数元组
        Returns:
            List[Dict[str, Any]]: 结果字典列表，无结果时返回空列表
        """
        ...

    # ──────── CRUD 快捷方法 ────────

    @abstractmethod
    def insert(self, table: str, data: Dict[str, Any]) -> str:
        """
        向指定表插入一行数据，返回新行的 TEXT 主键。

        主键由**应用层**生成（UUIDv7）：`data` 里没有 `id` 时自动补一个，
        已有时沿用调用方给的值。插入后不再回读自增 id。
        """
        ...

    @abstractmethod
    def update(self, table: str, data: Dict[str, Any], where: str, params: Tuple) -> int:
        """更新表中符合条件的行，返回受影响的行数"""
        ...

    @abstractmethod
    def delete(self, table: str, where: str, params: Tuple) -> int:
        """删除表中符合条件的行，返回受影响的行数"""
        ...

    # ──────── 初始化 ────────

    @abstractmethod
    def init_db(self, schema_file: str) -> None:
        """从 SQL 模式文件初始化数据库结构"""
        ...

    # ──────── 占位符 ────────

    @abstractmethod
    def get_placeholder(self) -> str:
        """返回当前引擎的参数占位符：SQLite 为 '?'，MySQL 为 '%s'"""
        ...

    # ──────── 时间函数 ────────

    @abstractmethod
    def get_current_timestamp_sql(self) -> str:
        """返回当前时间戳的 SQL 表达式"""
        ...

    # ──────── 主键定义 ────────

    @abstractmethod
    def get_primary_key_sql(self) -> str:
        """
        返回主键列的 SQL 定义片段。

        Phase 2b 起统一为 `TEXT PRIMARY KEY`（值是 UUIDv7 字符串）。
        MySQL 不允许 TEXT 直接做 PK，由 `convert_create_table_sql` 转成
        `VARCHAR(36) PRIMARY KEY`。
        """
        ...

    # ──────── 列名引用 ────────

    @abstractmethod
    def get_column_quote(self) -> str:
        """
        返回列名引用符。
        SQLite: 返回 '"'（双引号，SQL 标准）
        MySQL:  返回 '`'（反引号，MySQL 专属）
        """
        ...

    def quote_column(self, name: str) -> str:
        """返回正确引用的列名，如 `col_0` 或 "col_0" """
        q = self.get_column_quote()
        return f"{q}{name}{q}"

    # ──────── 建表语句转换 ────────

    def convert_create_table_sql(self, sql: str) -> str:
        """
        将 SQLite 建表语法转换为当前数据库引擎兼容的语法。
        基类默认返回原 SQL，MySQL 子类覆盖做转换。
        """
        return sql

    # ──────── 表结构查询 ────────

    @abstractmethod
    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """
        获取指定表的所有列信息。
        SQLite: 使用 PRAGMA table_info(表名)
        MySQL:  使用 SHOW COLUMNS FROM 表名
        返回格式统一为 [{'name': 'col_name', 'type': 'VARCHAR(255)'}, ...]
        """
        ...

    # ──────── 健康检查 ────────

    @abstractmethod
    def health_check(self) -> bool:
        """执行 SELECT 1 验证数据库连接是否存活"""
        ...

    # ──────── 内部辅助：SQL 转换 ────────

    def _convert_placeholders(self, sql: str) -> str:
        """
        将 SQL 中的 ? 占位符转换为当前引擎的实际占位符，
        并替换引擎专属函数名。
        """
        # 第一步：替换占位符
        placeholder = self.get_placeholder()
        converted = sql if placeholder == "?" else sql.replace("?", placeholder)

        # 第二步：替换引擎专属函数
        converted = self._convert_sql_functions(converted)
        return converted

    def _convert_sql_functions(self, sql: str) -> str:
        """
        将 SQL 中的引擎专属函数名转换为当前引擎兼容的形式。
        基类不做转换（即保持 SQLite 函数名），MySQL 子类覆盖。
        """
        return sql

    # ──────── 事务边界 ────────

    def _in_transaction(self) -> bool:
        """当前是否处于显式事务中（由 `transaction()` 上下文管理器设置）"""
        return getattr(self, "_tx_depth", 0) > 0

    @contextmanager
    def transaction(self):
        """
        显式事务上下文（Phase 2，见 docs/立项-存储层重构.md）。

        为什么需要：`execute_query` 默认每条语句自己 commit，导致
        「审核通过」这类多步操作（执行业务 + 写操作日志 + 改审核状态）**不是原子的**——
        中途失败会留下改了一半的数据，而旧代码还会把审核标记成「已通过」。

        特性：
          * **可嵌套**：内层 `with` 只增加深度，真正的事务由最外层控制
          * **回滚安全**：内层异常向上传播，由最外层统一回滚
          * **向后兼容**：不进入本上下文时 `execute_query` 行为与原来完全一致

        用法：
            with db.transaction():
                db.execute_query(...)
                db.execute_query(...)   # 任一失败 → 全部回滚
        """
        if not hasattr(self, "_tx_depth"):
            self._tx_depth = 0
        self._tx_depth += 1

        # 只有最外层负责发起与收尾事务
        outermost = self._tx_depth == 1
        if outermost:
            self._begin_transaction_impl()

        try:
            yield self
        except BaseException:
            self._tx_depth -= 1
            if outermost:
                self._rollback_transaction_impl()
            raise
        else:
            self._tx_depth -= 1
            if outermost:
                self._commit_transaction_impl()

    # ── 以下三个由子类按引擎实现；基类默认 no-op（兼容无事务能力的适配器）──

    def _begin_transaction_impl(self) -> None:
        pass

    def _commit_transaction_impl(self) -> None:
        pass

    def _rollback_transaction_impl(self) -> None:
        pass


# ──────────────────────── SQLite 适配器 ────────────────────────


class SQLiteAdapter(DatabaseAdapter):
    """
    SQLite 数据库适配器。
    使用 sqlite3 标准库实现，适用于开发环境和单机部署。
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn = None
        self._encrypted_db = None  # 加密数据库管理器（可选）

    def set_encryption(self, encrypted_db) -> None:
        """
        设置加密数据库管理器。
        当启用加密时，SQLiteAdapter 的连接将指向临时解密文件。
        """
        self._encrypted_db = encrypted_db
        if encrypted_db:
            self._db_path = encrypted_db.open()

    # ──────── 引擎检测 ────────

    def is_sqlite(self) -> bool:
        return True

    # ──────── 连接管理 ────────

    def connect(self) -> None:
        """建立 SQLite 数据库连接，自动创建父目录"""
        try:
            db_dir = os.path.dirname(os.path.abspath(self._db_path))
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            import sqlite3

            self._conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                timeout=30,
                isolation_level=None,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.Error as e:
            raise ConnectionError(f"SQLite 连接失败 [{self._db_path}]: {e}", e)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            finally:
                self._conn = None
        # 如果启用了加密，关闭时加密回写并清理临时文件
        if self._encrypted_db:
            try:
                self._encrypted_db.close()
            except Exception:
                pass
            finally:
                self._encrypted_db = None

    def _begin_transaction_impl(self) -> None:
        # isolation_level=None 是 autocommit 模式，必须显式 BEGIN 才能形成事务
        self._conn.execute("BEGIN")

    def _commit_transaction_impl(self) -> None:
        # 同样不能用 self._conn.commit()：autocommit 模式下它是 no-op。
        # 实测：isolation_level=None 时只有 execute("COMMIT") 才真正提交。
        if self._conn.in_transaction:
            self._conn.execute("COMMIT")

    def _rollback_transaction_impl(self) -> None:
        # 同上，必须用显式 ROLLBACK；self._conn.rollback() 在 autocommit 模式下无效
        if self._conn.in_transaction:
            try:
                self._conn.execute("ROLLBACK")
            except Exception:
                pass

    def _ensure_connection(self) -> None:
        if self._conn is None:
            self.connect()

    # ──────── 核心查询 ────────

    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> int:
        self._ensure_connection()
        import sqlite3

        converted_sql = self._convert_placeholders(sql)
        try:
            cur = self._conn.execute(converted_sql, params or ())
            # 事务内不单独 commit，交由外层 transaction() 统一收尾
            if not self._in_transaction():
                self._conn.commit()
            return cur.rowcount if cur.rowcount >= 0 else 0
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            if "timeout" in error_msg or "busy" in error_msg:
                raise TimeoutError(f"SQLite 操作超时: {e}", e)
            raise DatabaseError(f"SQLite 执行失败: {e}", e)
        except sqlite3.Error as e:
            raise DatabaseError(f"SQLite 执行失败: {e}", e)

    def fetch_one(self, sql: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        self._ensure_connection()
        import sqlite3

        converted_sql = self._convert_placeholders(sql)
        try:
            row = self._conn.execute(converted_sql, params or ()).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            raise DatabaseError(f"SQLite 查询失败: {e}", e)

    def fetch_all(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        self._ensure_connection()
        import sqlite3

        converted_sql = self._convert_placeholders(sql)
        try:
            rows = self._conn.execute(converted_sql, params or ()).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            raise DatabaseError(f"SQLite 查询失败: {e}", e)

    # ──────── CRUD 快捷方法 ────────

    def insert(self, table: str, data: Dict[str, Any]) -> str:
        """
        插入一行，返回该行的 TEXT 主键（UUIDv7）。

        id 由应用层生成后随 INSERT 一起写入，因此不再回读
        `last_insert_rowid()` / `LAST_INSERT_ID()`——那两个函数都与连接绑定，
        并发或连接池复用时未必指向刚插入的行。
        """
        payload = dict(data)
        row_id = payload.get("id")
        if row_id is None:
            row_id = new_row_id()
            payload["id"] = row_id

        columns = list(payload.keys())
        ph = self.get_placeholder()
        placeholders = ", ".join(ph for _ in columns)
        col_names = ", ".join(columns)

        sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
        self.execute_query(sql, tuple(payload.values()))
        return str(row_id)

    def update(self, table: str, data: Dict[str, Any], where: str, params: Tuple) -> int:
        ph = self.get_placeholder()
        set_clauses = [f"{col} = {ph}" for col in data.keys()]
        values = tuple(data.values()) + params
        sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {where}"
        return self.execute_query(sql, values)

    def delete(self, table: str, where: str, params: Tuple) -> int:
        sql = f"DELETE FROM {table} WHERE {where}"
        return self.execute_query(sql, params)

    # ──────── 初始化 ────────

    def init_db(self, schema_file: str) -> None:
        self._ensure_connection()
        if not os.path.exists(schema_file):
            raise DatabaseError(f"模式文件不存在: {schema_file}")

        with open(schema_file, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
        for stmt in statements:
            self.execute_query(stmt)

    # ──────── 占位符 ────────

    def get_placeholder(self) -> str:
        return "?"

    # ──────── 时间函数 ────────

    def get_current_timestamp_sql(self) -> str:
        return "datetime('now','localtime')"

    # ──────── 主键定义 ────────

    def get_primary_key_sql(self) -> str:
        return "TEXT PRIMARY KEY"

    # ──────── 列名引用 ────────

    def get_column_quote(self) -> str:
        """SQLite: 使用双引号（SQL 标准）"""
        return '"'

    # ──────── 建表转换 ────────

    def convert_create_table_sql(self, sql: str) -> str:
        """SQLite 不需要转换，原样返回"""
        return sql

    # ──────── 表结构查询 ────────

    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """
        SQLite: 使用 PRAGMA table_info 获取列信息
        返回格式统一为 [{'name': 'col_name', 'type': 'VARCHAR(255)'}, ...]
        """
        self._ensure_connection()
        import sqlite3
        try:
            rows = self._conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            return [{'name': dict(r)['name'], 'type': dict(r)['type']} for r in rows]
        except sqlite3.Error as e:
            raise DatabaseError(f"SQLite 获取表结构失败: {e}", e)

    # ──────── 健康检查 ────────

    def health_check(self) -> bool:
        try:
            self._ensure_connection()
            self._conn.execute("SELECT 1")
            return True
        except Exception:
            return False


# ──────────────────────── MySQL 适配器 ────────────────────────


class MySQLAdapter(DatabaseAdapter):
    """
    MySQL 数据库适配器。
    使用 pymysql 驱动，支持自动重连机制和 DictCursor 返回格式。
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        charset: str = "utf8mb4",
    ):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._charset = charset
        self._conn = None

    # ──────── 引擎检测 ────────

    def is_mysql(self) -> bool:
        return True

    # ──────── 连接管理 ────────

    def connect(self) -> None:
        try:
            import pymysql

            self._conn = pymysql.connect(
                host=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                database=self._database,
                charset=self._charset,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
            )
        except pymysql.Error as e:
            raise ConnectionError(
                f"MySQL 连接失败 [{self._host}:{self._port}/{self._database}]: {e}", e
            )

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            finally:
                self._conn = None

    def _ensure_connection(self) -> None:
        if self._conn is None:
            self.connect()
            return

        try:
            self._conn.ping(reconnect=False)
        except Exception:
            try:
                self.close()
                self.connect()
            except Exception as e:
                raise ConnectionError(f"MySQL 重连失败: {e}", e)

    def _begin_transaction_impl(self) -> None:
        # pymysql 连接默认 autocommit=False，语句已在隐式事务中，
        # 无需显式 BEGIN；这里只做连接确保。
        self._ensure_connection()

    def _commit_transaction_impl(self) -> None:
        try:
            self._conn.commit()
        except Exception:
            pass

    def _rollback_transaction_impl(self) -> None:
        try:
            self._conn.rollback()
        except Exception:
            pass

    # ──────────────────────────────────────────
    # SQL 函数转换：自动将 SQLite 专属函数替换为 MySQL 兼容语法
    # ──────────────────────────────────────────

    def _convert_sql_functions(self, sql: str) -> str:
        """
        将 SQL 中的 SQLite 专属函数替换为 MySQL 兼容函数。
        业务层写 SQLite 语法，适配层自动转换。
        """
        # Phase 2b：主键改 TEXT + 应用层生成，不再有 last_insert_rowid() 调用。
        # datetime('now') / datetime('now','localtime') → NOW()
        converted = re.sub(
            r"datetime\s*\(\s*'now'(?:\s*,\s*'localtime')?\s*\)",
            "NOW()",
            sql,
            flags=re.IGNORECASE,
        )

        # Phase 2c：RowStore 乐观锁的毫秒时间戳表达式 → MySQL NOW(3)
        converted = re.sub(
            r"strftime\s*\(\s*'[^']*'\s*,\s*'now'\s*\)",
            "NOW(3)",
            converted,
            flags=re.IGNORECASE,
        )

        return converted

    # ──────────────────────────────
    # 建表语句自动转换
    # ──────────────────────────────

    def convert_create_table_sql(self, sql: str) -> str:
        """
        将 SQLite 建表语法转换为 MySQL 兼容语法：
          1. TEXT PRIMARY KEY → VARCHAR(36) PRIMARY KEY
             （MySQL 不允许 TEXT 直接做主键；UUIDv7 定长 36 字符）
          2. TEXT 带 UNIQUE / NOT NULL 约束 → VARCHAR(255)
          3. 仅带 DEFAULT 的 TEXT → 移除 DEFAULT，保持 TEXT

        Phase 2b 起主键是应用层生成的 TEXT（UUIDv7），建表语句里已不存在
        AUTOINCREMENT / AUTO_INCREMENT，相关转换规则一并删除。
        """
        converted = re.sub(
            r"\bTEXT\s+PRIMARY\s+KEY\b",
            "VARCHAR(36) PRIMARY KEY",
            sql,
            flags=re.IGNORECASE,
        )
        converted = self._replace_text_for_mysql(converted)
        return converted

    @staticmethod
    def _replace_text_for_mysql(sql: str) -> str:
        """
        处理 MySQL 对 TEXT 列的限制：
        - 带 UNIQUE 或 NOT NULL 的 TEXT → VARCHAR(255)
        - 仅带 DEFAULT 的 TEXT → 移除 DEFAULT，保持 TEXT
        """
        # 第1步：带 UNIQUE 或 NOT NULL 约束的 TEXT → VARCHAR(255)
        pattern_key = (
            r"TEXT\s+"
            r"((?:(?:NOT\s+NULL|UNIQUE)(?:\s+(?:UNIQUE|NOT\s+NULL))*"
            r"\s*(?:DEFAULT\s+(?:'[^']*'|\"[^\"]*\"|\([^)]*\)))?\s*)+)"
        )
        sql = re.sub(
            pattern_key,
            lambda m: f"VARCHAR(255) {m.group(1).strip()}",
            sql,
            flags=re.IGNORECASE,
        )

        # 第2步：仅带 DEFAULT 的 TEXT（无 UNIQUE/NOT NULL）→ 移除 DEFAULT，保持 TEXT
        pattern_default_only = (
            r"TEXT\s+DEFAULT\s+(?:'[^']*'|\"[^\"]*\"|\([^)]*\))"
        )
        sql = re.sub(pattern_default_only, "TEXT", sql, flags=re.IGNORECASE)

        return sql

    # ──────── 核心查询 ────────

    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> int:
        self._ensure_connection()
        import pymysql

        converted_sql = self._convert_placeholders(sql)
        try:
            with self._conn.cursor() as cur:
                affected = cur.execute(converted_sql, params or ())
                # 事务内不单独 commit，交由外层 transaction() 统一收尾
                if not self._in_transaction():
                    self._conn.commit()
                return affected
        except pymysql.err.OperationalError as e:
            error_code = getattr(e, "args", [None])[0] if e.args else None
            if error_code in (2006, 2013):
                try:
                    self.connect()
                    with self._conn.cursor() as cur:
                        affected = cur.execute(converted_sql, params or ())
                        if not self._in_transaction():
                            self._conn.commit()
                        return affected
                except pymysql.Error as e2:
                    raise DatabaseError(f"MySQL 重连后执行仍失败: {e2}", e2)
            if error_code == 1205:
                raise TimeoutError(f"MySQL 锁等待超时: {e}", e)
            if error_code == 1213:
                raise DeadlockError(f"MySQL 检测到死锁: {e}", e)
            raise DatabaseError(f"MySQL 执行失败: {e}", e)
        except pymysql.Error as e:
            raise DatabaseError(f"MySQL 执行失败: {e}", e)

    def fetch_one(self, sql: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        self._ensure_connection()
        import pymysql

        converted_sql = self._convert_placeholders(sql)
        try:
            with self._conn.cursor() as cur:
                cur.execute(converted_sql, params or ())
                row = cur.fetchone()
                return dict(row) if row else None
        except pymysql.err.OperationalError as e:
            error_code = getattr(e, "args", [None])[0] if e.args else None
            if error_code in (2006, 2013):
                self.connect()
                with self._conn.cursor() as cur:
                    cur.execute(converted_sql, params or ())
                    row = cur.fetchone()
                    return dict(row) if row else None
            raise DatabaseError(f"MySQL 查询失败: {e}", e)
        except pymysql.Error as e:
            raise DatabaseError(f"MySQL 查询失败: {e}", e)

    def fetch_all(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        self._ensure_connection()
        import pymysql

        converted_sql = self._convert_placeholders(sql)
        try:
            with self._conn.cursor() as cur:
                cur.execute(converted_sql, params or ())
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        except pymysql.err.OperationalError as e:
            error_code = getattr(e, "args", [None])[0] if e.args else None
            if error_code in (2006, 2013):
                self.connect()
                with self._conn.cursor() as cur:
                    cur.execute(converted_sql, params or ())
                    rows = cur.fetchall()
                    return [dict(row) for row in rows]
            raise DatabaseError(f"MySQL 查询失败: {e}", e)
        except pymysql.Error as e:
            raise DatabaseError(f"MySQL 查询失败: {e}", e)

    # ──────── CRUD 快捷方法 ────────

    def insert(self, table: str, data: Dict[str, Any]) -> str:
        """
        插入一行，返回该行的 TEXT 主键（UUIDv7）。

        id 由应用层生成后随 INSERT 一起写入，因此不再回读
        `last_insert_rowid()` / `LAST_INSERT_ID()`——那两个函数都与连接绑定，
        并发或连接池复用时未必指向刚插入的行。
        """
        payload = dict(data)
        row_id = payload.get("id")
        if row_id is None:
            row_id = new_row_id()
            payload["id"] = row_id

        columns = list(payload.keys())
        ph = self.get_placeholder()
        placeholders = ", ".join(ph for _ in columns)
        col_names = ", ".join(columns)

        sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
        self.execute_query(sql, tuple(payload.values()))
        return str(row_id)

    def update(self, table: str, data: Dict[str, Any], where: str, params: Tuple) -> int:
        ph = self.get_placeholder()
        set_clauses = [f"{col} = {ph}" for col in data.keys()]
        values = tuple(data.values()) + params
        sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {where}"
        return self.execute_query(sql, values)

    def delete(self, table: str, where: str, params: Tuple) -> int:
        sql = f"DELETE FROM {table} WHERE {where}"
        return self.execute_query(sql, params)

    # ──────── 初始化 ────────

    def init_db(self, schema_file: str) -> None:
        self._ensure_connection()
        if not os.path.exists(schema_file):
            raise DatabaseError(f"模式文件不存在: {schema_file}")

        with open(schema_file, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
        for stmt in statements:
            self.execute_query(stmt)

    # ──────── 占位符 ────────

    def get_placeholder(self) -> str:
        return "%s"

    # ──────── 时间函数 ────────

    def get_current_timestamp_sql(self) -> str:
        return "NOW()"

    # ──────── 主键定义 ────────

    def get_primary_key_sql(self) -> str:
        # MySQL 不允许 TEXT 列直接做主键（必须有前缀长度），
        # UUIDv7 是固定 36 字符，用 VARCHAR(36) 既合法又省空间。
        return "VARCHAR(36) PRIMARY KEY"

    # ──────── 列名引用 ────────

    def get_column_quote(self) -> str:
        """MySQL: 使用反引号（MySQL 专属）"""
        return '`'

    # ──────── 表结构查询 ────────

    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """
        MySQL: 使用 SHOW COLUMNS FROM 获取列信息
        返回格式统一为 [{'name': 'col_name', 'type': 'varchar(255)'}, ...]
        """
        self._ensure_connection()
        import pymysql
        try:
            with self._conn.cursor() as cur:
                cur.execute(f"SHOW COLUMNS FROM {table_name}")
                rows = cur.fetchall()
                return [{'name': r['Field'], 'type': r['Type']} for r in rows]
        except pymysql.Error as e:
            raise DatabaseError(f"MySQL 获取表结构失败: {e}", e)

    # ──────── 健康检查 ────────

    def health_check(self) -> bool:
        try:
            self._ensure_connection()
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False


# ──────────────────────── 工厂函数（每次返回新连接） ────────────────────────


def get_adapter() -> DatabaseAdapter:
    """
    获取数据库适配器实例。

    每次调用都创建并返回一个新的适配器实例（独立连接）。
    调用者负责在使用完毕后调用 adapter.close() 关闭连接。
    """
    from .config import (
        DB_ENGINE,
        SQLITE_PATH,
        DB_ENCRYPTION_KEY,
        MYSQL_HOST,
        MYSQL_PORT,
        MYSQL_USER,
        MYSQL_PASSWORD,
        MYSQL_DATABASE,
        MYSQL_CHARSET,
    )

    engine = DB_ENGINE.lower().strip()
    if engine == "sqlite":
        adapter = SQLiteAdapter(SQLITE_PATH)

        # 如果启用了加密，设置加密数据库管理器
        if DB_ENCRYPTION_KEY:
            from .db_crypto import EncryptedDatabase

            encrypted_path = SQLITE_PATH + ".enc"
            encrypted_db = EncryptedDatabase(encrypted_path, DB_ENCRYPTION_KEY)
            adapter.set_encryption(encrypted_db)
    elif engine == "mysql":
        adapter = MySQLAdapter(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset=MYSQL_CHARSET,
        )
    else:
        raise ValueError(f"不支持的数据库引擎: {engine}，请使用 'sqlite' 或 'mysql'")

    adapter.connect()
    return adapter


def validate_sqlite_file(path: str, require_table: str = "users") -> Dict[str, Any]:
    """
    校验一个文件是否为本系统可用的 SQLite 数据库（恢复备份前的安全门）。

    检查项：
      1) 文件头 magic：b'SQLite format 3\x00'
      2) sqlite3 真实打开 + PRAGMA integrity_check == 'ok'
      3) 必须存在 require_table 表（默认 users，挡"合法 SQLite 但不是本系统库"）

    返回 {'ok': True} 或 {'ok': False, 'error': 原因}。只读打开，不改文件。
    """
    try:
        with open(path, 'rb') as f:
            header = f.read(16)
        if header != b'SQLite format 3\x00':
            return {'ok': False, 'error': '不是有效的 SQLite 数据库文件'}
    except OSError as e:
        return {'ok': False, 'error': f'文件不可读: {e}'}

    import sqlite3
    con = None
    try:
        con = sqlite3.connect(path)
        ic = con.execute('PRAGMA integrity_check').fetchone()[0]
        if ic != 'ok':
            return {'ok': False, 'error': f'数据库完整性校验失败: {ic}'}
        has = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (require_table,),
        ).fetchone()
        if not has:
            return {'ok': False, 'error': f'不是本系统的数据库（缺少 {require_table} 表）'}
        return {'ok': True}
    except sqlite3.Error as e:
        return {'ok': False, 'error': f'数据库校验失败: {e}'}
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass


def reset_adapter() -> None:
    """重置适配器（兼容旧接口）"""
    pass


def test_mysql_connection(host: str, port: int, user: str, password: str, database: str) -> Dict[str, Any]:
    """测试 MySQL 连接是否正常"""
    import pymysql
    try:
        conn = pymysql.connect(
            host=host, port=port, user=user,
            password=password, database=database,
            charset='utf8mb4', connect_timeout=5
        )
        conn.close()
        return {'success': True, 'message': '连接成功'}
    except Exception as e:
        return {'success': False, 'message': f'连接失败: {str(e)}'}