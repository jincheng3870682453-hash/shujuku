import os, sqlite3

for path in ['registry.db', 'data/app.db']:
    full = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    exists = os.path.exists(full)
    size = os.path.getsize(full) if exists else 0
    print(f"{path}: exists={exists}, size={size}")
    if exists:
        db = sqlite3.connect(full)
        r = db.execute("SELECT COUNT(*) as cnt FROM pending_changes").fetchone()
        print(f"  pending_changes: {r[0]}")
        r = db.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        print(f"  users: {r[0]}")
        db.close()