# -*- coding: utf-8 -*-
"""
数据库适配层单元测试

测试 SQLite 适配器的完整 CRUD 流程、占位符转换、health_check 等。
MySQL 测试需要本地 MySQL 环境，若不可用则自动跳过。

运行方式:
    cd backend
    python -m pytest test_adapter.py -v
    或
    python test_adapter.py
"""

import os
import sys
import unittest
import tempfile

# 确保 backend 包可以被导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.db_adapter import (
    DatabaseAdapter,
    DatabaseError,
    ConnectionError,
    TimeoutError,
    DeadlockError,
    SQLiteAdapter,
    MySQLAdapter,
    get_adapter,
    reset_adapter,
)
from backend import config


# ========== SQLite 适配器测试 ==========


class TestSQLiteAdapter(unittest.TestCase):
    """SQLite 适配器 CRUD 全流程测试"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化：创建临时 SQLite 数据库"""
        cls.temp_dir = tempfile.mkdtemp(prefix="test_sqlite_")
        cls.db_path = os.path.join(cls.temp_dir, "test.db")
        cls.adapter = SQLiteAdapter(cls.db_path)
        cls.adapter.connect()

        # 建表
        cls.adapter.execute_query("""
            CREATE TABLE IF NOT EXISTS test_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER,
                created_at TEXT
            )
        """)

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        if cls.adapter:
            cls.adapter.close()
        # 清理临时文件
        import shutil

        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        """每个测试前清空表"""
        self.adapter.execute_query("DELETE FROM test_users")

    # ──────── 连接与健康检查 ────────

    def test_connect(self):
        """测试数据库连接是否正常建立"""
        self.assertTrue(self.adapter.health_check())

    def test_health_check(self):
        """测试 health_check 返回 True"""
        self.assertTrue(self.adapter.health_check())

    # ──────── 占位符 ────────

    def test_get_placeholder(self):
        """SQLite 占位符应为 ?"""
        self.assertEqual(self.adapter.get_placeholder(), "?")

    def test_placeholder_conversion_noop(self):
        """SQLite 的占位符转换应保持 ? 不变"""
        sql = "SELECT * FROM t WHERE a = ? AND b = ?"
        converted = self.adapter._convert_placeholders(sql)
        self.assertEqual(converted, sql)

    # ──────── 时间函数 ────────

    def test_current_timestamp_sql(self):
        """SQLite 时间戳函数应为 datetime('now','localtime')"""
        ts = self.adapter.get_current_timestamp_sql()
        self.assertIn("datetime", ts)

    # ──────── 自增主键 ────────

    def test_auto_increment_sql(self):
        """SQLite 自增主键语法"""
        ai = self.adapter.get_auto_increment_sql()
        self.assertIn("AUTOINCREMENT", ai)

    # ──────── CRUD：插入 ────────

    def test_insert_single(self):
        """测试插入单行数据"""
        new_id = self.adapter.insert("test_users", {"name": "Alice", "age": 25})
        self.assertGreater(new_id, 0)

        row = self.adapter.fetch_one("SELECT * FROM test_users WHERE id = ?", (new_id,))
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "Alice")
        self.assertEqual(row["age"], 25)

    def test_insert_multiple(self):
        """测试插入多行数据"""
        id1 = self.adapter.insert("test_users", {"name": "Bob", "age": 30})
        id2 = self.adapter.insert("test_users", {"name": "Charlie", "age": 35})
        self.assertNotEqual(id1, id2)

    # ──────── CRUD：查询 ────────

    def test_fetch_one_found(self):
        """测试 fetch_one 查询到数据"""
        self.adapter.insert("test_users", {"name": "David", "age": 40})
        row = self.adapter.fetch_one(
            "SELECT * FROM test_users WHERE name = ?", ("David",)
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "David")
        self.assertIsInstance(row, dict)

    def test_fetch_one_not_found(self):
        """测试 fetch_one 查询不到数据返回 None"""
        row = self.adapter.fetch_one(
            "SELECT * FROM test_users WHERE name = ?", ("Nobody",)
        )
        self.assertIsNone(row)

    def test_fetch_all(self):
        """测试 fetch_all 返回全部数据"""
        self.adapter.insert("test_users", {"name": "Eve", "age": 22})
        self.adapter.insert("test_users", {"name": "Frank", "age": 28})
        rows = self.adapter.fetch_all("SELECT * FROM test_users ORDER BY id")
        self.assertEqual(len(rows), 2)
        self.assertIsInstance(rows, list)
        self.assertIsInstance(rows[0], dict)

    def test_fetch_all_empty(self):
        """测试空表 fetch_all 返回空列表"""
        rows = self.adapter.fetch_all("SELECT * FROM test_users")
        self.assertEqual(rows, [])

    # ──────── CRUD：更新 ────────

    def test_update(self):
        """测试更新数据"""
        new_id = self.adapter.insert("test_users", {"name": "Grace", "age": 26})
        affected = self.adapter.update(
            "test_users", {"age": 27}, "id = ?", (new_id,)
        )
        self.assertEqual(affected, 1)

        row = self.adapter.fetch_one("SELECT * FROM test_users WHERE id = ?", (new_id,))
        self.assertEqual(row["age"], 27)
        # name 应保持不变
        self.assertEqual(row["name"], "Grace")

    def test_update_no_match(self):
        """测试更新不存在的记录，受影响行数应为 0"""
        affected = self.adapter.update(
            "test_users", {"name": "???"}, "id = ?", (99999,)
        )
        self.assertEqual(affected, 0)

    # ──────── CRUD：删除 ────────

    def test_delete(self):
        """测试删除数据"""
        new_id = self.adapter.insert("test_users", {"name": "ToDelete", "age": 50})
        affected = self.adapter.delete("test_users", "id = ?", (new_id,))
        self.assertEqual(affected, 1)

        row = self.adapter.fetch_one("SELECT * FROM test_users WHERE id = ?", (new_id,))
        self.assertIsNone(row)

    def test_delete_no_match(self):
        """测试删除不存在的记录"""
        affected = self.adapter.delete("test_users", "id = ?", (99999,))
        self.assertEqual(affected, 0)

    # ──────── execute_query ────────

    def test_execute_query_insert(self):
        """测试 execute_query 执行 INSERT"""
        affected = self.adapter.execute_query(
            "INSERT INTO test_users (name, age) VALUES (?, ?)", ("Ivan", 33)
        )
        self.assertEqual(affected, 1)

    def test_execute_query_delete(self):
        """测试 execute_query 执行 DELETE"""
        self.adapter.insert("test_users", {"name": "Judy", "age": 29})
        affected = self.adapter.execute_query(
            "DELETE FROM test_users WHERE name = ?", ("Judy",)
        )
        self.assertEqual(affected, 1)

    # ──────── 上下文管理器 ────────

    def test_context_manager(self):
        """测试 with 语句上下文管理器"""
        adapter2 = SQLiteAdapter(os.path.join(self.temp_dir, "test_ctx.db"))
        with adapter2 as ad:
            ad.execute_query("CREATE TABLE IF NOT EXISTS t(x)")
            ad.insert("t", {"x": "hello"})
            row = ad.fetch_one("SELECT * FROM t")
            self.assertEqual(row["x"], "hello")

    # ──────── 返回格式验证 ────────

    def test_fetch_one_return_type(self):
        """验证 fetch_one 返回格式统一为 dict"""
        self.adapter.insert("test_users", {"name": "Format", "age": 1})
        row = self.adapter.fetch_one("SELECT * FROM test_users WHERE name = ?", ("Format",))
        self.assertIsInstance(row, dict)

    def test_fetch_all_return_type(self):
        """验证 fetch_all 返回格式统一为 list[dict]"""
        self.adapter.insert("test_users", {"name": "F1", "age": 1})
        rows = self.adapter.fetch_all("SELECT * FROM test_users")
        self.assertIsInstance(rows, list)
        if rows:
            self.assertIsInstance(rows[0], dict)


# ========== MySQL 适配器测试（条件跳过） ==========


class TestMySQLAdapter(unittest.TestCase):
    """
    MySQL 适配器测试。

    需要本地或可访问的 MySQL 实例。
    如果无法连接则自动跳过所有测试。
    """

    @classmethod
    def setUpClass(cls):
        """尝试连接 MySQL，连接失败则跳过"""
        try:
            cls.adapter = MySQLAdapter(
                host=config.MYSQL_HOST,
                port=config.MYSQL_PORT,
                user=config.MYSQL_USER,
                password=config.MYSQL_PASSWORD,
                database=config.MYSQL_DATABASE,
                charset=config.MYSQL_CHARSET,
            )
            cls.adapter.connect()

            # 建测试表
            cls.adapter.execute_query("""
                CREATE TABLE IF NOT EXISTS __test_adapter_users (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(100) NOT NULL,
                    age INT,
                    created_at DATETIME
                )
            """)
        except Exception as e:
            raise unittest.SkipTest(f"MySQL 不可用，跳过测试: {e}")

    @classmethod
    def tearDownClass(cls):
        """清理测试表"""
        if hasattr(cls, "adapter") and cls.adapter:
            try:
                cls.adapter.execute_query("DROP TABLE IF EXISTS __test_adapter_users")
            except Exception:
                pass
            cls.adapter.close()

    def setUp(self):
        """每个测试前清空表"""
        self.adapter.execute_query("DELETE FROM __test_adapter_users")

    def test_placeholder_is_percent_s(self):
        """MySQL 占位符应为 %s"""
        self.assertEqual(self.adapter.get_placeholder(), "%s")

    def test_placeholder_conversion(self):
        """MySQL 应把 ? 转换为 %s"""
        sql = "SELECT * FROM t WHERE a = ? AND b = ?"
        converted = self.adapter._convert_placeholders(sql)
        self.assertNotIn("?", converted)
        self.assertIn("%s", converted)

    def test_health_check(self):
        """MySQL 健康检查"""
        self.assertTrue(self.adapter.health_check())

    def test_crud(self):
        """MySQL 完整 CRUD 流程"""
        # Insert
        new_id = self.adapter.insert(
            "__test_adapter_users", {"name": "Alice", "age": 25}
        )
        self.assertGreater(new_id, 0)

        # Fetch
        row = self.adapter.fetch_one(
            "SELECT * FROM __test_adapter_users WHERE id = ?", (new_id,)
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "Alice")

        # Update
        affected = self.adapter.update(
            "__test_adapter_users", {"age": 26}, "id = ?", (new_id,)
        )
        self.assertEqual(affected, 1)

        # Delete
        affected = self.adapter.delete(
            "__test_adapter_users", "id = ?", (new_id,)
        )
        self.assertEqual(affected, 1)

    def test_current_timestamp_sql(self):
        """MySQL 时间戳应为 NOW()"""
        ts = self.adapter.get_current_timestamp_sql()
        self.assertIn("NOW", ts.upper())

    def test_auto_increment_sql(self):
        """MySQL 自增主键语法"""
        ai = self.adapter.get_auto_increment_sql()
        self.assertIn("AUTO_INCREMENT", ai.upper())


# ========== 异常处理测试 ==========


class TestExceptions(unittest.TestCase):
    """异常类测试"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="test_exc_")
        cls.db_path = os.path.join(cls.temp_dir, "test.db")
        cls.adapter = SQLiteAdapter(cls.db_path)
        cls.adapter.connect()
        cls.adapter.execute_query("CREATE TABLE IF NOT EXISTS t(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")

    @classmethod
    def tearDownClass(cls):
        cls.adapter.close()
        import shutil

        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_unique_constraint_violation(self):
        """测试唯一约束违反时抛出 DatabaseError"""
        self.adapter.insert("t", {"name": "unique_name"})
        with self.assertRaises(DatabaseError):
            self.adapter.insert("t", {"name": "unique_name"})

    def test_syntax_error(self):
        """测试 SQL 语法错误抛出 DatabaseError"""
        with self.assertRaises(DatabaseError):
            self.adapter.execute_query("INVALID SQL STATEMENT")

    def test_database_error_contains_original(self):
        """测试 DatabaseError 保留原始异常"""
        try:
            self.adapter.execute_query("INVALID SQL")
        except DatabaseError as e:
            self.assertIsNotNone(e.original_error)


# ========== 工厂函数测试 ==========


class TestFactory(unittest.TestCase):
    """get_adapter 工厂函数测试"""

    def setUp(self):
        reset_adapter()

    def tearDown(self):
        reset_adapter()

    def test_get_adapter_returns_sqlite_by_default(self):
        """默认配置应返回 SQLiteAdapter"""
        # 临时设置环境变量
        os.environ["DB_ENGINE"] = "sqlite"
        os.environ["SQLITE_PATH"] = ":memory:"
        reset_adapter()
        adapter = get_adapter()
        self.assertIsInstance(adapter, SQLiteAdapter)

    def test_get_adapter_returns_independent_instances(self):
        """多次调用 get_adapter 应返回独立实例（工厂模式，非单例）"""
        os.environ["DB_ENGINE"] = "sqlite"
        os.environ["SQLITE_PATH"] = ":memory:"
        reset_adapter()
        a1 = get_adapter()
        a2 = get_adapter()
        try:
            self.assertIsNot(a1, a2)
        finally:
            a1.close()
            a2.close()


# ========== 运行入口 ==========

if __name__ == "__main__":
    # 使用 unittest 运行，verbosity=2 显示详细输出
    unittest.main(verbosity=2)