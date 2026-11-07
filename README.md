# 🔮 Dynamic Registry · 动态数据登记系统

<p align="center">
  <img src="https://img.shields.io/badge/version-6.1-blue?style=for-the-badge" alt="version">
  <img src="https://img.shields.io/badge/license-PolyForm%20Noncommercial-orange?style=for-the-badge" alt="license">
  <img src="https://img.shields.io/badge/python-3.9+-orange?style=for-the-badge&logo=python" alt="python">
  <img src="https://img.shields.io/badge/react-18-blue?style=for-the-badge&logo=react" alt="react">
  <img src="https://img.shields.io/badge/electron-28-47848f?style=for-the-badge&logo=electron" alt="electron">
  <img src="https://img.shields.io/badge/docker-ready-2496ed?style=for-the-badge&logo=docker" alt="docker">
</p>

<p align="center">
  <a href="README.md"><b>中文</b></a> · <a href="README_EN.md">English</a>
</p>

**一句话：开箱即用的团队数据登记台——自定义字段像表格软件一样灵活，但带账号、权限、审核流、操作留痕，数据 100% 存在自己电脑上。**

- 🧩 **动态字段**：字段即加即用（文本/数字/日期/下拉/布尔/附件），底层 JSONB 存储，加 1000 个字段也不动表结构
- 👥 **权限 + 审核流**：boss / hr / employee 三级角色 + 21 项细粒度权限；敏感操作走「提交→审批」而不是直接生效；并发编辑冲突自动检测（409 提示刷新）
- 🔑 **主键全局唯一**：全表 UUIDv7 主键，离线各机生成不撞号——多台电脑同步数据零冲突
- 🔄 **去中心化同步**：`.drsync` 加密增量包（U盘/网盘/微信传文件都行），同局域网内还能 P2P 自动发现互相同步——不需要任何服务器，密文离开硬盘前生成，口令不上网
- 🔎 **本地语义检索**：不联网、零外部 API，「静宜」能搜到「陈静宜」——检索全在本机
- 🚀 **一键迁移**：旧库（宽表/自增 id）自动迁移到新结构，迁前可 dry-run，旧表保留可秒级回滚
- 🖥️ **三种部署**：桌面单文件（Electron）/ Docker 服务器 / 纯本地浏览器，默认 SQLite 零配置

默认账户：`boss / 123456`（管理员）、`hr / 123456`、`employee / 123456`——**登录后立即改密**。

## 快速开始

```bash
# 本地跑（Python 3.9+）
pip install -r requirements.txt
python app.py                      # http://127.0.0.1:5000

# 或 Docker
docker compose up -d
```

桌面版见 [electron/](electron/)；压测脚本见 [locustfile.py](locustfile.py)。

## 文档导航

| 文档 | 内容 |
|---|---|
| [README_EN.md](README_EN.md) | 英文版介绍 |
| [docs/立项-存储层重构.md](docs/立项-存储层重构.md) | 存储层重构全程记录：JSONB 选型论证、UUIDv7 主键硬切、乐观锁、同步、检索——含每阶段踩坑与验证证据 |
| [docs/drsync.md](docs/drsync.md) | 多机同步三种用法、安全模型、端口说明 |
| [docs/vecsearch.md](docs/vecsearch.md) | 本地检索的定位、局限、换真模型的预留路径 |
| [docs/更新公告.md](docs/更新公告.md) | 版本更新公告 |
| [docs/架构图.md](docs/架构图.md) | 完整架构图 / ER 图 |
| [docs/项目亮点.md](docs/项目亮点.md) | 项目亮点汇总 |
| [docs/PPT白皮书资料包_v6.0.md](docs/PPT白皮书资料包_v6.0.md) | 汇报/白皮书素材 |
| [docs/legal/](docs/legal/) | 用户协议 / 隐私政策 |
| [docs/archive/](docs/archive/) | 历史文档归档（旧版亮点、开发日志、对话记录） |
| [docs/design-demos/](docs/design-demos/) | UI 设计方向草案 |
| [scripts/](scripts/) | 冒烟测试 / 全新部署验证 / 迁移 E2E / 基线校验 / drsync CLI |
| [scripts/dev/](scripts/dev/) | 开发期一次性调试脚本归档 |

<details>
<summary><b>架构速览（点开）</b></summary>

```
浏览器 / Electron 桌面壳
   │ REST API（Session + Bearer 双认证，21 项权限）
   ▼
Flask + Waitress ──── 审核网关（非 boss 操作 → pending_changes 待审）
   │
   ├─ RowStore        rows_data 固定 6 列 + JSON 数据区（写路径零 DDL）
   ├─ DatabaseAdapter SQLite（默认）/ PostgreSQL 规划中，方言自动转换
   ├─ uuid7           应用层 UUIDv7 主键（时间有序，离线不撞号）
   ├─ drsync          加密增量包 + UDP beacon 局域网 P2P（可选）
   └─ vecsearch       n-gram TF-IDF 本地检索（零依赖零网络）
```

完整架构图、ER 图、权限矩阵见 [docs/立项-存储层重构.md](docs/立项-存储层重构.md)。

</details>

<details>
<summary><b>数据库切换 / 迁移（点开）</b></summary>

默认 SQLite 单文件（`data/app.db`）。已有旧库自动检测并给出迁移指引：

```bash
python -m backend.migrate_jsonb     # 旧宽表 → JSONB（6 固定列 + JSON）
python -m backend.migrate_uuid7 --dry-run
python -m backend.migrate_uuid7     # 自增 id → UUIDv7 TEXT（8 表 + 外键全改写）
python -m backend.migrate_uuid7 --verify-only
```

迁移全程只读旧表、新表原子改名、旧表保留（`*_legacy_*` / `*_uuid_legacy_*`）可回滚。
`--dry-run` 只检查不执行。服务器模式（PostgreSQL）规划见立项书 §0.1。

</details>

<details>
<summary><b>测试与验证（点开）</b></summary>

```bash
python -m pytest backend/ -q                  # 224 passed, 6 skipped
python scripts/api_smoke.py                   # 31/31（真实数据副本全链路）
python scripts/fresh_deploy.py                # 21/21（全新空库部署）
python scripts/e2e_migrate.py                 # 迁移 E2E（逐行比对）
python scripts/verify_baseline.py             # 真库未被测试触碰
cd frontend && npx tsc --noEmit               # 前端类型检查
```

</details>

## License

[PolyForm Noncommercial](LICENSE) — 个人与内部团队使用免费，商用需授权。
