# -*- coding: utf-8 -*-
"""
从零建库验证：init_db() 直接创建 JSONB 结构的新库，不走迁移脚本。

这对应「全新部署」场景——README 的一键启动 / Docker 首次启动。
旧方案从空表开始靠 ALTER 补列；新方案 CREATE TABLE 就是最终形态。
"""
import json
import os
import sqlite3
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(f"  {'✓' if cond else '✗'} {name}" + (f"  {extra}" if extra and not cond else ""))


def main():
    tmp = tempfile.mkdtemp(prefix="fresh_")
    fresh = os.path.join(tmp, "fresh.db")

    # 关键：必须在 import app 前把适配层路径改掉
    os.environ.pop("REGISTRY_INIT_ON_IMPORT", None)

    from backend.db_adapter import SQLiteAdapter, reset_adapter
    from backend import config as cfg
    from backend import db_adapter as da

    # 建一个空库文件
    sqlite3.connect(fresh).close()
    cfg.SQLITE_PATH = fresh
    da.SQLITE_PATH = fresh

    import app as appmod

    # ── 1. init_db 建表 ──
    appmod.init_db()

    a = SQLiteAdapter(fresh)
    a.connect()
    cols = [c["name"] for c in a.get_table_columns("rows_data")]
    print(f"\n新建库 rows_data 列: {cols}")
    check("新库 rows_data 为 JSONB 6 列",
          set(cols) == {"id", "data", "created_by", "schema_version", "created_at", "updated_at"},
          f"got {set(cols)}")
    check("种子账户 boss 已建",
          a.fetch_one("SELECT id FROM users WHERE username = 'boss'") is not None)
    check("columns_meta 为空（新库无字段）",
          a.fetch_one("SELECT COUNT(*) AS c FROM columns_meta")["c"] == 0)

    # ── 2. 全新库上跑 API ──
    appmod.app.config["TESTING"] = True
    client = appmod.app.test_client()

    # 未登录应 401（权限守卫正常）
    r = client.get("/api/rows")
    check("未登录 GET /api/rows 返回 401", r.status_code == 401, f"status={r.status_code}")

    r = client.post("/api/login", json={"username": "boss", "password": "123456"})
    check("新库可登录 boss", r.status_code == 200, f"status={r.status_code}")

    # 登录后、无字段时列表应为空数据而非报错
    r = client.get("/api/rows")
    check("登录后无字段 GET /api/rows 200", r.status_code == 200, f"status={r.status_code} body={r.get_data(as_text=True)[:200]}")
    check("无字段时 data 为空列表", (r.get_json() or {}).get("data") == [])

    # ── 3. 加字段 → 录数据 → 读回 ──
    # 注意：数据 key 是字段的 name（col_0 之类），label 仅用于显示。
    # 前端 DataTable 也是用 col.key 做 dataIndex，与此一致。
    r = client.post("/api/columns", json={
        "label": "姓名", "type": "text", "options": None, "required": False,
    })
    check("新增字段 201", r.status_code == 201, f"status={r.status_code} body={r.get_data(as_text=True)[:200]}")
    f_name = r.get_json().get("name")
    check("字段有 name", bool(f_name), f"got {f_name}")
    r = client.post("/api/columns", json={
        "label": "部门", "type": "select",
        "options": [{"label": "技术部", "value": "技术部"}], "required": False,
    })
    check("新增下拉字段 201", r.status_code == 201, f"status={r.status_code}")
    f_dept = r.get_json().get("name")

    ncols = len(a.get_table_columns("rows_data"))
    check("加了 2 个字段后物理列数仍为 6", ncols == 6, f"got {ncols}")

    r = client.post("/api/rows", json={f_name: "陈静宜", f_dept: "技术部"})
    check("新库新增数据 201", r.status_code == 201, f"status={r.status_code} body={r.get_data(as_text=True)[:200]}")
    new_id = r.get_json().get("id") if r.status_code == 201 else None

    r = client.get("/api/rows")
    body = r.get_json()
    check("列表读到 1 条", body.get("total") == 1, f"total={body.get('total')}")
    if body.get("data"):
        row = body["data"][0]
        check("姓名正确", row.get(f_name) == "陈静宜", f"got {row.get(f_name)!r}")
        check("部门正确", row.get(f_dept) == "技术部", f"got {row.get(f_dept)!r}")

    r = client.put(f"/api/rows/{new_id}", json={f_name: "陈静宜-改"})
    check("更新 200", r.status_code == 200, f"status={r.status_code} body={r.get_data(as_text=True)[:200]}")
    c = sqlite3.connect(fresh); c.row_factory = sqlite3.Row
    raw = c.execute("SELECT data FROM rows_data WHERE id = ?", (new_id,)).fetchone()
    c.close()
    payload = json.loads(raw["data"])
    check("更新落库", payload.get(f_name) == "陈静宜-改", f"got {payload}")
    check("部分更新未丢部门", payload.get(f_dept) == "技术部", f"got {payload}")

    # ── 4. 删字段（旧方案的灾难场景）──
    r = client.request("DELETE", "/api/columns/姓名",
                       headers={"Authorization": f"Bearer {client.get('/api/me').get_json().get('token')}"}) \
        if False else None
    # boss 不走审核，直接删
    from backend.db_adapter import get_adapter
    col = a.fetch_one("SELECT name FROM columns_meta WHERE label = '姓名'")
    if col:
        r = client.delete(f"/api/columns/{col['name']}")
        check("删除字段 200", r.status_code == 200, f"status={r.status_code} body={r.get_data(as_text=True)[:150]}")
        ncols2 = len(a.get_table_columns("rows_data"))
        check("删字段后物理列数不变", ncols2 == 6, f"got {ncols2}")
        # 删字段后：JSON 中的数据键是否保留？
        c = sqlite3.connect(fresh); c.row_factory = sqlite3.Row
        raw = c.execute("SELECT data FROM rows_data WHERE id = ?", (new_id,)).fetchone()
        c.close()
        payload = json.loads(raw["data"])
        print(f"    删字段后 JSON: {payload}")
        check("旧数据 JSON 未丢该键（历史数据保留）",
              "col_0" in payload or f_name in payload,
              f"keys={list(payload.keys())}")

    a.close()
    reset_adapter()

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print("\n" + "=" * 60)
    print(f"FRESH DEPLOY: {passed}/{total} " + ("PASS ✅" if passed == total else "FAIL ❌"))
    for name, ok in results:
        if not ok:
            print(f"   ✗ {name}")
    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
