import sqlite3, json, os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'registry.db')
db = sqlite3.connect(db_path)
db.row_factory = sqlite3.Row

print("=" * 50)
print("1. pending_changes 表数据")
print("=" * 50)
r = db.execute("SELECT COUNT(*) AS cnt FROM pending_changes").fetchone()
print(f"总数: {r['cnt']}")

rows = db.execute("SELECT * FROM pending_changes ORDER BY id DESC LIMIT 10").fetchall()
for row in rows:
    d = dict(row)
    print(f"  [{d['id']}] type={d['change_type']}, status={repr(d['status'])}, requested_by={d['requested_by']}")

print("\n" + "=" * 50)
print("2. 用户 global_audit 状态")
print("=" * 50)
users = db.execute("SELECT id, username, role, global_audit FROM users").fetchall()
for u in users:
    print(f"  id={u['id']}, name={u['username']}, role={u['role']}, audit={u['global_audit']}")

print("\n" + "=" * 50)
print("3. pending_changes 表结构（含列是否存在）")
print("=" * 50)
cols = db.execute("PRAGMA table_info(pending_changes)").fetchall()
col_names = [c['name'] for c in cols]
for c in cols:
    print(f"  {c['name']:20s} {c['type']:10s} default={c['dflt_value']}")
print(f"\n  review_comment 列存在: {'review_comment' in col_names}")

print("\n" + "=" * 50)
print("4. 模拟审核查询（Boss视角，待审核）")
print("=" * 50)
rows = db.execute("""
    SELECT pc.*, u.username AS applicant, u.role AS applicant_role 
    FROM pending_changes pc 
    LEFT JOIN users u ON pc.requested_by = u.id 
    WHERE pc.status = ? 
    ORDER BY pc.created_at DESC
""", ('待审核',)).fetchall()
print(f"结果数: {len(rows)}")
for row in rows:
    print(f"  [{row['id']}] type={row['change_type']}, status={row['status']}, applicant={row['applicant']}")

db.close()