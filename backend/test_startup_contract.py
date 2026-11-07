# -*- coding: utf-8 -*-
"""
app.py 启动初始化契约测试
=========================

背景：原先 `app.py` 在 **import 期**裸调 `init_db()`，即任何 `import app`
都会执行全部 DDL（包括给 rows_data 补列的 ALTER TABLE）。Phase 0 实测发现
这会让单测改写生产库 schema，`test_ai_client.py` 因此无法从 `backend/` 目录运行。

Phase 1c 改为：import 期跳过，只有入口进程（`__main__`）或显式调用才初始化。

本测试锁住该契约：
  1. import app **不**触发 init_db（不产生任何 DDL）
  2. `init_db()` 可显式调用且幂等
  3. 启动入口都覆盖了显式初始化（用静态检查，防止漏改 Dockerfile / 脚本）

运行方式（项目根目录）:
    python -m pytest backend/test_startup_contract.py -v --timeout=60
"""

import os
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = r"G:\dynamic_registry"


class TestImportDoesNotInitDb(unittest.TestCase):
    """import app 不得触发数据库初始化"""

    def test_import_app_does_not_touch_database(self):
        """
        在干净的临时目录下 import app，断言：
          * 没有创建任何 .db 文件
          * 输出里没有 '[INFO] 数据库初始化完成'
        """
        with tempfile.TemporaryDirectory() as tmp:
            # 把工作目录切到临时目录：若 import 期跑 init_db，
            # 它会在这里创建 registry.db（老逻辑会）
            env = dict(os.environ)
            env["REGISTRY_DB_PATH"] = os.path.join(tmp, "should_not_exist.db")
            env.pop("REGISTRY_INIT_ON_IMPORT", None)

            code = (
                "import sys;"
                "sys.path.insert(0, %r);"
                "import app;"
                "print('IMPORT_OK');"
                "import os;"
                "print('DB_CREATED', os.path.exists(%r))"
            ) % (PROJECT_ROOT, os.path.join(tmp, "should_not_exist.db"))

            r = subprocess.run(
                [sys.executable, "-c", code],
                cwd=tmp, env=env,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=90,
            )
            self.assertIn("IMPORT_OK", r.stdout, f"import 失败:\n{r.stderr[-800:]}")
            self.assertNotIn(
                "[INFO] 数据库初始化完成", r.stdout,
                "import 期仍在执行 init_db()——Phase 1c 的修正被回退了",
            )
            self.assertIn("DB_CREATED False", r.stdout, "import 期创建了数据库文件")
            self.assertFalse(
                os.path.exists(os.path.join(tmp, "should_not_exist.db")),
                "import 期创建了数据库文件",
            )

    def test_import_skip_message_is_printed(self):
        """默认行为下应打印跳过提示，让运维知道去哪开启"""
        env = dict(os.environ)
        env.pop("REGISTRY_INIT_ON_IMPORT", None)
        code = (
            "import sys;sys.path.insert(0, %r);import app" % PROJECT_ROOT
        )
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT, env=env,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=90,
        )
        self.assertIn("跳过 import 期 init_db", r.stdout + r.stderr)


class TestExplicitInit(unittest.TestCase):
    """init_db() 可显式调用，且幂等"""

    def test_init_db_is_callable_and_idempotent(self):
        env = dict(os.environ)
        env.pop("REGISTRY_INIT_ON_IMPORT", None)
        code = (
            "import sys;sys.path.insert(0, %r);"
            "import app;"
            "app.init_db();"
            "print('FIRST_OK');"
            "app.init_db();"
            "print('SECOND_OK')"
        ) % PROJECT_ROOT
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT, env=env,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=120,
        )
        self.assertIn("FIRST_OK", r.stdout, f"首次 init_db 失败:\n{r.stderr[-800:]}")
        self.assertIn("SECOND_OK", r.stdout, f"二次 init_db 失败:\n{r.stderr[-800:]}")

    def test_init_db_on_legacy_wide_table_must_not_crash(self):
        """
        回归测试：在**仍是旧宽表**（无 data 列）的库上跑 init_db 必须不报错。

        历史 bug：init_db 无条件执行
            CREATE INDEX ... ON rows_data(created_by)
        而旧宽表没有 created_by 列 → "no such column: created_by" → 启动即崩。
        正确行为：检测到旧结构只打印迁移指引，不建索引、不 ALTER。
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            legacy = os.path.join(tmp, "legacy.db")
            # 用一个不 import backend 包的子进程建旧宽表，
            # 避开 backend/__init__.py 的 sqlite3 import hook（白名单只认
            # 文件名含 db_adapter / test_adapter 的调用方）。
            setup = (
                "import sqlite3,sys;"
                "c=sqlite3.connect(sys.argv[1]);"
                "c.execute('CREATE TABLE rows_data (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "col_0 TEXT, col_1 TEXT, _created_by VARCHAR(255))');"
                "c.execute(\"INSERT INTO rows_data (col_0, col_1, _created_by) "
                "VALUES ('a','b','hr')\");"
                "c.commit();c.close()"
            )
            subprocess.run(
                [sys.executable, "-c", setup, legacy],
                cwd=tmp, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60,
                check=True,
            )

            env = dict(os.environ)
            env.pop("REGISTRY_INIT_ON_IMPORT", None)
            code = (
                "import sys;sys.path.insert(0, %r);"
                "from backend import config as cfg, db_adapter as da;"
                "cfg.SQLITE_PATH = %r; da.SQLITE_PATH = %r;"
                "import app;"
                "app.init_db();"
                "print('LEGACY_INIT_OK')"
            ) % (PROJECT_ROOT, legacy, legacy)
            r = subprocess.run(
                [sys.executable, "-c", code],
                cwd=PROJECT_ROOT, env=env,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=120,
            )
            self.assertIn(
                "LEGACY_INIT_OK", r.stdout,
                f"旧宽表上 init_db 崩溃了:\n{r.stderr[-800:]}",
            )
            self.assertIn("旧宽表", r.stdout + r.stderr,
                          "应提示检测到旧宽表结构")
            # 绝不能自动 ALTER 改结构（用子进程读，避开 import hook）
            inspect = (
                "import sqlite3,sys;"
                "c=sqlite3.connect(sys.argv[1]);"
                "cols=[x[1] for x in c.execute('PRAGMA table_info(rows_data)')];"
                "n=c.execute('SELECT COUNT(*) FROM rows_data').fetchone()[0];"
                "c.close();"
                "print('COLS='+','.join(cols));"
                "print('ROWS=%d' % n)"
            )
            r2 = subprocess.run(
                [sys.executable, "-c", inspect, legacy],
                cwd=tmp, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60,
            )
            out = r2.stdout
            self.assertNotIn("data", out.split("ROWS=")[0],
                             f"init_db 不应擅自改造旧表结构: {out}")
            self.assertIn("ROWS=1", out, f"init_db 不应丢失旧数据: {out}")


class TestStartupEntriesCovered(unittest.TestCase):
    """
    静态检查所有启动入口都覆盖了显式初始化。
    防止有人漏改 Dockerfile / 启动脚本，导致部署得到空库。
    """

    def _read(self, *parts):
        with open(os.path.join(PROJECT_ROOT, *parts), encoding="utf-8") as f:
            return f.read()

    def test_dockerfile_initializes_explicitly(self):
        content = self._read("Dockerfile")
        self.assertIn(
            "init_db()", content,
            "Dockerfile 的 CMD 必须显式调用 init_db()（它的启动方式不走 __main__）",
        )
        self.assertNotIn(
            'python -c \\"from waitress import serve; from app import app;',
            content,
            "Dockerfile CMD 仍是纯 import 方式启动，会跳过初始化",
        )

    def test_app_main_block_initializes(self):
        content = self._read("app.py")
        self.assertIn(
            "if __name__ == '__main__':", content,
            "app.py 必须有 __main__ 入口",
        )
        # __main__ 块内必须调 init_db（粗略但有效的存在性检查）
        idx = content.index("if __name__ == '__main__':")
        main_block = content[idx:]
        self.assertIn("init_db()", main_block)

    def test_import_guard_exists(self):
        content = self._read("app.py")
        self.assertIn("_INIT_ON_IMPORT", content)
        self.assertIn("if _INIT_ON_IMPORT:", content)

    def test_bat_and_sh_use_app_py_entry(self):
        """启动脚本都以 `python app.py` 方式启动，走 __main__ → 已覆盖"""
        bat = self._read("启动.bat")
        self.assertIn("python app.py", bat)
        sh = self._read("start.sh")
        self.assertIn("app.py", sh)


if __name__ == "__main__":
    unittest.main(verbosity=2)
