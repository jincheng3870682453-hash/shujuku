# -*- coding: utf-8 -*-
"""
基线校验：确认测试/冒烟运行未改变 live 数据库结构。

比对 `data/app.db` 与 `registry.db` 的 rows_data 列数、行数、columns_meta 字段数
是否与 `backups/phase0/` 里的 Phase 0 备份一致。

用法（项目根目录）:
    python scripts/verify_baseline.py

依赖：脚本会先把备份复制到 .dsh-tmp/ 再打开——因为 backups/phase0/ 目录下
SQLite 无法原地打开（缺建文件权限，见 docs/立项-存储层重构.md §0.5）。
"""
import os
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, ".dsh-tmp")
os.makedirs(TMP, exist_ok=True)

TARGETS = [
    ("data/app.db", os.path.join(ROOT, "data", "app.db"),
     os.path.join(ROOT, "backups", "phase0", "app.db")),
    ("registry.db", os.path.join(ROOT, "registry.db"),
     os.path.join(ROOT, "backups", "phase0", "registry.db")),
]


def snapshot(path):
    # 用普通连接而非 mode=ro URI：WAL 模式下只读 URI 需要 -shm/-wal 写权限
    c = sqlite3.connect(path)
    cols = [r[1] for r in c.execute("PRAGMA table_info(rows_data)")]
    rows = c.execute("SELECT COUNT(*) FROM rows_data").fetchone()[0]
    cm = c.execute("SELECT COUNT(*) FROM columns_meta").fetchone()[0]
    c.close()
    return len(cols), rows, cm


def readable_copy(path, tag):
    """把文件复制到 .dsh-tmp/ 再返回路径（原目录下 SQLite 无法原地打开）"""
    dest = os.path.join(TMP, f"baseline_{tag}.db")
    shutil.copy2(path, dest)
    return dest


all_ok = True
for label, live, backup in TARGETS:
    a = snapshot(readable_copy(live, label.replace("/", "_") + "_live"))
    b = snapshot(readable_copy(backup, label.replace("/", "_") + "_bak"))
    same = a == b
    all_ok &= same
    print("=" * 62)
    print(f"{label}")
    print(f"  live   : {a[0]} cols, {a[1]} rows, {a[2]} fields")
    print(f"  backup : {b[0]} cols, {b[1]} rows, {b[2]} fields")
    print(f"  => {'IDENTICAL' if same else '*** CHANGED BY TEST RUN ***'}")

print("=" * 62)
print("BASELINE INTACT" if all_ok else "BASELINE MUTATED")
sys.exit(0 if all_ok else 1)
