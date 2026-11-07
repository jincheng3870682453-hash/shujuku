# 🔮 Dynamic Registry

<p align="center">
  <img src="https://img.shields.io/badge/version-6.1-blue?style=for-the-badge" alt="version">
  <img src="https://img.shields.io/badge/license-PolyForm%20Noncommercial-orange?style=for-the-badge" alt="license">
  <img src="https://img.shields.io/badge/python-3.9+-orange?style=for-the-badge&logo=python" alt="python">
  <img src="https://img.shields.io/badge/react-18-blue?style=for-the-badge&logo=react" alt="react">
  <img src="https://img.shields.io/badge/electron-28-47848f?style=for-the-badge&logo=electron" alt="electron">
  <img src="https://img.shields.io/badge/docker-ready-2496ed?style=for-the-badge&logo=docker" alt="docker">
</p>

<p align="center">
  <a href="README.md">中文</a> · <a href="README_EN.md"><b>English</b></a>
</p>

**One line: a batteries-included team data registry — custom fields as flexible as a spreadsheet, but with accounts, permissions, an approval workflow and full audit trail, and the data never leaves your own machine.**

- 🧩 **Dynamic fields** — text / number / date / select / boolean / attachment; JSONB storage means zero DDL no matter how many fields you add
- 👥 **Permissions + approval** — boss / hr / employee roles, 21 fine-grained permissions; sensitive operations go through submit → review; concurrent edit conflicts detected (HTTP 409)
- 🔑 **Globally unique primary keys** — UUIDv7 everywhere, so offline machines never collide; multi-machine sync is conflict-free by design
- 🔄 **Decentralized sync** — encrypted `.drsync` delta packages (USB stick / cloud folder / chat file transfer), plus optional LAN peer discovery over UDP beacon. No server needed; everything is encrypted before it leaves the disk, and the passphrase never travels
- 🔎 **Local semantic search** — no network calls, no external APIs; "静宜" finds "陈静宜"; runs entirely on-device
- 🚀 **One-shot migration** — legacy databases (wide tables / auto-increment ids) migrate automatically, with dry-run support and rollback-safe legacy tables
- 🖥️ **Three ways to run** — Electron desktop, Docker server, or plain local browser; SQLite by default, zero config

Default accounts: `boss / 123456`, `hr / 123456`, `employee / 123456` — **change them right after first login**.

## Quick Start

```bash
pip install -r requirements.txt
python app.py                      # http://127.0.0.1:5000

# or Docker
docker compose up -d
```

## Documentation

| Doc | Content |
|---|---|
| [README.md](README.md) | Chinese intro & docs index |
| [docs/立项-存储层重构.md](docs/立项-存储层重构.md) | Full storage-layer rework log: JSONB rationale, UUIDv7 hard-cut, optimistic locking, sync, search — pitfalls & evidence per phase |
| [docs/drsync.md](docs/drsync.md) | Sync usage, security model, ports |
| [docs/vecsearch.md](docs/vecsearch.md) | Local search scope, limitations, upgrade path |
| [scripts/](scripts/) | Smoke tests / fresh-deploy check / migration E2E / drsync CLI |

## Test

```bash
python -m pytest backend/ -q      # 224 passed, 6 skipped
python scripts/api_smoke.py       # 31/31
```

## License

[PolyForm Noncommercial](LICENSE) — free for personal and internal team use; commercial use requires a license.
