# -*- coding: utf-8 -*-
"""
事务边界与审核原子性测试（Phase 2）
===================================

覆盖两件事：

A. `DatabaseAdapter.transaction()` 本身
   - 正常路径：全部提交
   - 异常路径：全部回滚
   - 嵌套：外层控制，内层异常传导到外层
   - 向后兼容：不用 transaction() 时仍是每条自动 commit

B. 「审核通过」的原子性（立项书 P0-5 的真 bug）
   - **执行失败时，必须回滚且状态保持「待审核」**
   - 旧实现在 try/except 后无条件 UPDATE status='已通过'，
     导致「操作没生效、记录却显示已通过」

运行方式（项目根目录）:
    python -m pytest backend/test_transaction.py -v --timeout=60
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.db_adapter import SQLiteAdapter, DatabaseError


def make_db(tmpdir, name="tx.db"):
    a = SQLiteAdapter(os.path.join(tmpdir, name))
    a.connect()
    a.execute_query(
        "CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT)"
    )
    return a


class TestTransactionBasic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tx_")

    def tearDown(self):
        pass

    def test_commit_on_success(self):
        a = make_db(self.tmp, "c.db")
        with a.transaction():
            a.execute_query("INSERT INTO t (v) VALUES ('a')")
            a.execute_query("INSERT INTO t (v) VALUES ('b')")
        self.assertEqual(
            a.fetch_one("SELECT COUNT(*) AS c FROM t")["c"], 2
        )
        a.close()

    def test_rollback_on_exception(self):
        a = make_db(self.tmp, "r.db")
        with self.assertRaises(RuntimeError):
            with a.transaction():
                a.execute_query("INSERT INTO t (v) VALUES ('a')")
                raise RuntimeError("boom")
        # 已执行的第一条 INSERT 必须也被回滚
        self.assertEqual(
            a.fetch_one("SELECT COUNT(*) AS c FROM t")["c"], 0,
            "异常时事务未回滚",
        )
        a.close()

    def test_partial_write_not_persisted(self):
        """多步操作中途失败，不能留下改了一半的数据"""
        a = make_db(self.tmp, "p.db")
        a.execute_query("INSERT INTO t (v) VALUES ('pre-existing')")
        try:
            with a.transaction():
                a.execute_query("INSERT INTO t (v) VALUES ('step1')")
                # 制造失败：让第二条语句的 SQL 出错
                a.execute_query("INSERT INTO no_such_table (v) VALUES ('step2')")
        except DatabaseError:
            pass
        vals = [r["v"] for r in a.fetch_all("SELECT v FROM t")]
        self.assertEqual(vals, ["pre-existing"], "step1 应被回滚，只留原有数据")
        a.close()

    def test_nested_inner_exception_propagates_to_outer(self):
        a = make_db(self.tmp, "n.db")
        with self.assertRaises(RuntimeError):
            with a.transaction():
                a.execute_query("INSERT INTO t (v) VALUES ('outer')")
                try:
                    with a.transaction():
                        a.execute_query("INSERT INTO t (v) VALUES ('inner')")
                        raise RuntimeError("inner boom")
                except RuntimeError:
                    raise  # 内层异常必须传播到外层，由外层统一回滚
        self.assertEqual(
            a.fetch_one("SELECT COUNT(*) AS c FROM t")["c"], 0,
            "嵌套事务内层失败未传导到外层",
        )
        a.close()

    def test_nested_commit_on_success(self):
        a = make_db(self.tmp, "nc.db")
        with a.transaction():
            a.execute_query("INSERT INTO t (v) VALUES ('outer')")
            with a.transaction():
                a.execute_query("INSERT INTO t (v) VALUES ('inner')")
        self.assertEqual(
            a.fetch_one("SELECT COUNT(*) AS c FROM t")["c"], 2
        )
        a.close()

    def test_backward_compat_autocommit(self):
        """不进 transaction() 时，行为与改造前完全一致（每条自动提交）"""
        a = make_db(self.tmp, "bc.db")
        a.execute_query("INSERT INTO t (v) VALUES ('x')")
        # 用一个独立连接验证它已落盘（而非还停在事务里）
        b = SQLiteAdapter(os.path.join(self.tmp, "bc.db"))
        b.connect()
        self.assertEqual(b.fetch_one("SELECT COUNT(*) AS c FROM t")["c"], 1)
        b.close()
        a.close()

    def test_connection_reusable_after_rollback(self):
        a = make_db(self.tmp, "re.db")
        try:
            with a.transaction():
                a.execute_query("INSERT INTO t (v) VALUES ('a')")
                raise RuntimeError("x")
        except RuntimeError:
            pass
        # 回滚后连接必须仍可用，不能卡死在事务里
        with a.transaction():
            a.execute_query("INSERT INTO t (v) VALUES ('after')")
        self.assertEqual(
            a.fetch_one("SELECT COUNT(*) AS c FROM t")["c"], 1
        )
        a.close()


class TestAuditApproveAtomicity(unittest.TestCase):
    """
    「审核通过」的原子性——立项书 P0-5 的真 bug 回归测试。

    旧代码：
        try:
            ... 执行业务操作 ...
        except Exception:
            traceback.print_exc()      # ← 吞掉
        db.execute_query("UPDATE pending_changes SET status='已通过' ...")   # ← 照常通过

    后果：操作失败也标记已通过，审核员被告知成功而数据没变。
    """

    def _build(self, tmpdir):
        a = SQLiteAdapter(os.path.join(tmpdir, "au.db"))
        a.connect()
        a.execute_query(
            "CREATE TABLE rows_data (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "data TEXT NOT NULL DEFAULT '{}', created_by TEXT DEFAULT '', "
            "schema_version INTEGER DEFAULT 0, created_at DATETIME, updated_at DATETIME)"
        )
        a.execute_query(
            "CREATE TABLE columns_meta (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT UNIQUE, label TEXT, field_type TEXT DEFAULT 'text', "
            "options TEXT, position INTEGER DEFAULT 0)"
        )
        a.execute_query(
            "CREATE TABLE pending_changes (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "row_id INTEGER, column_name TEXT, old_value TEXT, new_value TEXT, "
            "change_type TEXT, requested_by INTEGER, status TEXT DEFAULT '待审核', "
            "reviewed_by INTEGER, review_comment TEXT, reviewed_at DATETIME, "
            "created_at DATETIME)"
        )
        a.execute_query(
            "CREATE TABLE operations_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER, username TEXT, role TEXT, action TEXT, "
            "target_type TEXT, target_id TEXT, detail TEXT, created_at DATETIME)"
        )
        a.execute_query("INSERT INTO columns_meta (name,label,field_type,position) "
                        "VALUES ('姓名','姓名','text',0)")
        a.execute_query("INSERT INTO rows_data (data, created_by) VALUES "
                        "('{\"姓名\": \"陈静宜\"}', 'hr')")
        a.execute_query(
            "INSERT INTO pending_changes (row_id, column_name, new_value, "
            "change_type, requested_by, status) VALUES (1, '姓名', '\"林致远\"', "
            "'update', 2, '待审核')"
        )
        return a

    def test_failed_operation_keeps_status_pending(self):
        """
        核心回归：业务操作抛异常时，pending_changes.status 必须仍是「待审核」，
        且不能写入「已通过」。
        """
        tmp = tempfile.mkdtemp(prefix="au_")
        a = self._build(tmp)

        # 模拟「旧代码行为」：吞掉异常后仍标记通过
        # 新代码要求：异常必须传播，让事务回滚
        raised = False
        try:
            with a.transaction():
                # 这一步会因表不存在而失败
                a.execute_query("UPDATE no_such_table SET x = 1")
                a.execute_query(
                    "UPDATE pending_changes SET status='已通过' WHERE id = 1"
                )
        except DatabaseError:
            raised = True

        self.assertTrue(raised, "失败语句应抛出 DatabaseError")
        row = a.fetch_one("SELECT status FROM pending_changes WHERE id = 1")
        self.assertEqual(
            row["status"], "待审核",
            "业务操作失败时审核状态必须保持待审核（旧 bug 会变成已通过）",
        )
        a.close()

    def test_successful_operation_marks_approved(self):
        tmp = tempfile.mkdtemp(prefix="au_")
        a = self._build(tmp)
        with a.transaction():
            a.execute_query("INSERT INTO rows_data (data, created_by) VALUES ('{}', 'hr')")
            a.execute_query(
                "UPDATE pending_changes SET status='已通过' WHERE id = 1"
            )
        row = a.fetch_one("SELECT status FROM pending_changes WHERE id = 1")
        self.assertEqual(row["status"], "已通过")
        a.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
