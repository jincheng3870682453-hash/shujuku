# -*- coding: utf-8 -*-
"""
Phase 1c API 冒烟测试：迁移后用 Flask test client 打真实端点。

在**真实数据副本**上执行完整迁移，然后：
  1. 迁移
  2. 以 boss 登录
  3. 打 GET /api/rows（列表）、POST /api/rows（新增）、
     PUT /api/rows/<id>（改）、GET /api/stats、GET /api/export
  4. 比对每一次操作的返回与数据库实际状态

不触碰 live 库。
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(PROJECT_ROOT, "data", "app.db")
if not os.path.exists(LIVE):
    # 运行环境没有真库（CI / 全新克隆）：退回 backups/phase0 快照或临时空库
    _snap = os.path.join(PROJECT_ROOT, "backups", "phase0", "app.db")
    if os.path.exists(_snap):
        LIVE = _snap
    else:
        LIVE = os.path.join(tempfile.gettempdir(), "api_smoke_seed.db")
        if not os.path.exists(LIVE):
            _seed = sqlite3.connect(LIVE)
            _seed.execute("CREATE TABLE IF NOT EXISTS rows_data (id TEXT PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}', created_by TEXT NOT NULL DEFAULT '', schema_version INTEGER NOT NULL DEFAULT 0, created_at DATETIME, updated_at DATETIME)")
            _seed.execute("CREATE TABLE IF NOT EXISTS columns_meta (id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, label TEXT NOT NULL, field_type TEXT NOT NULL DEFAULT 'text', options TEXT, position INTEGER DEFAULT 0)")
            _seed.commit()
            _seed.close()
sys.path.insert(0, PROJECT_ROOT)

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(f"  {'✓' if cond else '✗'} {name}" + (f"  {extra}" if extra and not cond else ""))


def make_writable_copy(dest):
    """
    用 sqlite3 的 backup API 生成可写副本。

    不用 shutil.copy2：live 库是 WAL 模式，复制 .db 文件不带走 -wal/-shm，
    且继承的权限会让副本变成只读（Phase 0 已见过 backups/ 目录的同类问题）。
    只读打开失败（沙箱/锁/权限）时退化为普通文件复制——backup API 只是保真手段，
    快照文件本身不需要 WAL 重放。
    """
    try:
        src = sqlite3.connect(f"file:{LIVE}?mode=ro", uri=True)
        dst = sqlite3.connect(dest)
        src.backup(dst)
        dst.close()
        src.close()
    except sqlite3.Error:
        # 连接对象可能还占着 dest，先彻底关掉再覆盖
        try:
            dst.close()
        except Exception:
            pass
        try:
            src.close()
        except Exception:
            pass
        import gc

        gc.collect()
        if os.path.exists(dest):
            for _ in range(5):
                try:
                    os.remove(dest)
                    break
                except PermissionError:
                    import time

                    time.sleep(0.2)
        shutil.copy2(LIVE, dest)
    return dest


def main():
    tmp = tempfile.mkdtemp(prefix="api_smoke_")
    work_db = make_writable_copy(os.path.join(tmp, "app.db"))
    print(f"工作副本: {work_db}")
    _w = sqlite3.connect(work_db)
    _w.execute("PRAGMA journal_mode=DELETE")   # 换成回滚日志，便于外部工具读
    _w.close()
    print("副本可写性 OK")

    # ── 必须在 import app 之前设好 DB 路径 ──
    os.environ["REGISTRY_DB_PATH"] = work_db
    os.environ.pop("REGISTRY_INIT_ON_IMPORT", None)

    from backend.db_adapter import SQLiteAdapter, reset_adapter
    from backend import migrate_jsonb as M
    from backend import migrate_uuid7 as M7

    # 直接指定副本路径：get_adapter() 用的是 config 的模块级 SQLITE_PATH，
    # 环境变量 REGISTRY_DB_PATH 对它无效（只影响 app.py 的 DATABASE_PATH）。
    a = SQLiteAdapter(work_db)
    a.connect()
    stats = M.migrate(a)
    print(f"\n[迁移] {stats['status']}, {stats.get('rows_moved')} 行")
    check("迁移成功", stats["status"] == "migrated")

    # Phase 2b：再把副本迁到 TEXT 主键（UUIDv7）。smoke 测的是「迁移后的真实库」，
    # 与生产上线顺序一致：先 migrate_jsonb，再 migrate_uuid7。
    if not M7.is_migrated(a):
        s7 = M7.migrate(a)
        print(f"[迁移] uuid7 -> {s7.get('status')}")
        check("uuid7 迁移成功", s7.get("status") in ("migrated", "already-migrated"), f"got {s7.get('status')}")
    v7 = M7.verify(a)
    check("uuid7 校验通过", bool(v7.get("ok")), json.dumps(v7, ensure_ascii=False)[:300])
    a.close()
    reset_adapter()

    # 让 app.py 也用这个副本：把 config 的 SQLITE_PATH 改掉
    from backend import config as cfg
    cfg.SQLITE_PATH = work_db
    from backend import db_adapter as da
    da.SQLITE_PATH = work_db

    # ── 2. import app（此时已不触发 init_db）──
    import app as appmod
    appmod.app.config["TESTING"] = True
    client = appmod.app.test_client()

    # ── 3. 登录 ──
    r = client.post("/api/login", json={"username": "boss", "password": "123456"})
    check("boss 登录成功", r.status_code == 200, f"status={r.status_code} body={r.get_data(as_text=True)[:200]}")
    if r.status_code != 200:
        print("\n无法登录，中止")
        return 1
    token = r.get_json().get("token")
    print(f"  token = {token[:24]}...")

    # ── 4. GET /api/rows ──
    r = client.get("/api/rows?page=1&pageSize=10")
    body = r.get_json()
    check("GET /api/rows 200", r.status_code == 200)
    check("返回 10 条", len(body["data"]) == 10, f"got {len(body['data'])}")
    check("total = 49", body["total"] == 49, f"got {body['total']}")
    first = body["data"][0]
    check("含 id 字段", "id" in first)
    check("含字段「姓名」", "姓名" in first, f"keys={list(first.keys())[:8]}")
    check("姓名有值", bool(first.get("姓名")), f"value={first.get('姓名')!r}")

    # ── 5. POST /api/rows 新增 ──
    before = _count(work_db)
    payload = {"姓名": "测试新人", "工号": "EMP-9999", "部门": "技术研发部"}
    r = client.post("/api/rows", json=payload)
    check("POST /api/rows 201", r.status_code == 201, f"status={r.status_code} body={r.get_data(as_text=True)[:300]}")
    new_id = r.get_json().get("id")
    after = _count(work_db)
    check("行数 +1", after == before + 1, f"{before} → {after}")

    # 读回验证
    row = _read_row(work_db, new_id)
    check("新行姓名正确", row.get("姓名") == "测试新人", f"got {row.get('姓名')!r}")
    check("新行工号正确", row.get("工号") == "EMP-9999")
    check("新行部门正确", row.get("部门") == "技术研发部")
    check("新行 created_by = boss", row.get("created_by") == "boss", f"got {row.get('created_by')!r}")

    # ── 6. PUT /api/rows/<id> 更新 ──
    r = client.put(f"/api/rows/{new_id}", json={"部门": "财务审计部", "备注": "改部门了"})
    check("PUT /api/rows 200", r.status_code == 200, f"status={r.status_code} body={r.get_data(as_text=True)[:200]}")
    row = _read_row(work_db, new_id)
    check("部门已更新", row.get("部门") == "财务审计部", f"got {row.get('部门')!r}")
    check("姓名未被清掉（部分更新）", row.get("姓名") == "测试新人", f"got {row.get('姓名')!r}")
    check("工号未被清掉（部分更新）", row.get("工号") == "EMP-9999", f"got {row.get('工号')!r}")

    # ── 7. GET /api/stats（第 6 节已把新行部门改成「财务审计部」，故统计应见新值）──
    r = client.get("/api/stats?field=部门")
    check("GET /api/stats 200", r.status_code == 200, f"status={r.status_code}")
    st = r.get_json() or {}
    if r.status_code == 200:
        names = [i["name"] for i in st.get("items", [])]
        check("统计返回 items", "items" in st)
        check("统计总数为 50（49 + 新插入）", st.get("total") == 50, f"total={st.get('total')}")
        check("统计含 PUT 后的值", "财务审计部" in names, f"names={names}")

    # ── 7b. GET /api/export ──
    r = client.get("/api/export")
    check("GET /api/export 200", r.status_code == 200, f"status={r.status_code}")
    check("导出是 xlsx", "spreadsheet" in (r.headers.get("Content-Type") or ""))

    # ── 7c. 第 6 节已把新行部门改成「财务审计部」，统计应反映这个最新值，
    #      且总数应为 50（原 49 + 新插入 1）。这是对「统计读的是同一份 JSON 数据」的验证。
    r = client.get("/api/stats?field=部门")
    st = r.get_json() or {}
    names = [i["name"] for i in st.get("items", [])]
    check("统计反映 PUT 后的值", "财务审计部" in names, f"names={names}")
    check("统计总数为 50", st.get("total") == 50, f"got {st.get('total')}")

    # ── 9. DELETE /api/rows/<id> ──
    before = _count(work_db)
    r = client.delete(f"/api/rows/{new_id}")
    check("DELETE /api/rows 200", r.status_code == 200, f"status={r.status_code}")
    check("行数 -1", _count(work_db) == before - 1)

    # ── 10. 物理列数仍未变 ──
    from backend.db_adapter import SQLiteAdapter as _SA
    a2 = _SA(work_db)
    a2.connect()
    ncols = len(a2.get_table_columns("rows_data"))
    a2.close()
    check("经过增删改后物理列数仍为 6", ncols == 6, f"got {ncols}")

    # ── 汇总 ──
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print("\n" + "=" * 60)
    print(f"API SMOKE: {passed}/{total} " + ("PASS ✅" if passed == total else "FAIL ❌"))
    for name, ok in results:
        if not ok:
            print(f"   ✗ {name}")
    print("=" * 60)

    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if passed == total else 1


def _count(path):
    c = sqlite3.connect(path)
    n = c.execute("SELECT COUNT(*) FROM rows_data").fetchone()[0]
    c.close()
    return n


def _read_row(path, row_id):
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    r = c.execute("SELECT data, created_by FROM rows_data WHERE id = ?", (row_id,)).fetchone()
    c.close()
    if not r:
        return {}
    out = json.loads(r["data"]) if r["data"] else {}
    out["created_by"] = r["created_by"]
    return out


if __name__ == "__main__":
    sys.exit(main())
