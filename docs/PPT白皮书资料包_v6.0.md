# 动态数据登记系统 v6.0 — PPT / 白皮书资料包

> 本文件汇总了项目的全部核心资料，供 AI 制作演示 PPT 与白皮书使用。
> 数据来源：README.md、项目亮点_v6.0.md、开发日志.md、架构图.md、demo.html（演示页）
> 整理日期：2026-08-13 ｜ 当前版本：v6.0

---

## 一、项目速览（PPT 封面 / 白皮书摘要用）

| 项目 | 内容 |
|:---|:---|
| **项目名称** | 动态数据登记系统 · Dynamic Registry |
| **版本** | v6.0.0（2026-08-14） |
| **一句话定位** | 一个动态字段、双数据库引擎、三级权限审核的 Web/桌面一体化数据管理平台 |
| **核心卖点** | 零代码字段建模 · 多模型 AI 分析 · 9 种背景质感 · 四级权限管控 · 四种部署形态 |
| **开发周期** | 12 天（2026-07-19 → 08-14） |
| **迭代规模** | 25 个版本 · 20 项新增 · 3 项修复 · 3 项优化 · 1 次回滚 |
| **作者** | 金呈（@jincheng3870682453-hash） |
| **开源协议** | MIT License |
| **技术底色** | Python (Flask) + React 18 + Electron + SQLite/MySQL |
| **演示页面** | 本地 `demo.html`（滚动动效展示页） |
| **掘金文章** | 《不知道玩什么，就写了个系统》 https://juejin.cn/post/7672852599783587874 |
| **GitHub** | https://github.com/jincheng3870682453-hash |

**Slogan 候选（PPT 用）**：
- 「快、聪明、好看」
- 「从无聊开始，做到企业级」
- 「一个字段写死引发的重建工程」
- 「12 天 · 25 个版本 · 0% 失败」

---

## 二、核心数据（PPT 数字金句页）

| 指标 | 数值 |
|:---|:---|
| API 端点 | **49 个** |
| 前端页面 | **12 个** |
| 角色层级 | **4 级**（Boss / HR / Employee / 自定义） |
| 细粒度权限 | **21 项** |
| 动态字段类型 | **7 种**（文本/数字/日期/下拉/布尔/长文本/文件） |
| 审核操作类型 | **15+ 种** |
| 背景质感 | **9 种** |
| 并发压测 | **170 并发 · 2100+ 请求 · 0% 失败率** |
| 聚合 RPS | **39.4** |
| 平均响应 | **42ms**（中位 32ms / P95 120ms / P99 190ms） |
| 部署形态 | **4 种**（Web / Electron 桌面 / Docker / 打包 EXE） |
| AI 模型支持 | **5 种**（OpenAI / DeepSeek / 通义千问 / 文心一言 / 自定义） |

---

## 三、十大核心亮点（PPT 分页素材）

### 1. 🧩 动态字段引擎
零代码数据建模：7 种字段类型可视化配置，数据库自动 `ALTER TABLE` 适配表结构。元数据驱动渲染，前端根据字段配置自动生成表单与表格，**新增字段无需修改一行代码**。

### 2. 🗄️ 双数据库引擎
SQLite + MySQL 8.0 无缝切换。基于 `DatabaseAdapter` 抽象层，**一行配置切换引擎、业务代码零改动**。桌面端零配置 SQLite，生产环境 MySQL 高并发。

### 3. 🔐 三级安全网关
**认证（Session + Bearer Token）→ 权限（21 项细粒度检查）→ 审核（待审核队列）**，全链路不可绕过。密码 PBKDF2-SHA256 加盐哈希 + 数据 AES-256-GCM 加密。

### 4. 🤖 AI 多模型分析（v6.0 升级）
- **5 种模型预设**：OpenAI / DeepSeek / 通义千问 / 文心一言 / 自定义端点，一键切换
- **语音输入**：Web Speech API 语音转文字
- **智能联网搜索**：DeepSeek 模型实时联网
- **历史记录**：`ai_analysis_history` 表按用户隔离，换设备不丢
- **按角色裁剪**：AI 看到的始终是权限范围内的数据（员工只看自己的数据）
- **报错中文化**：所有 AI 错误信息友好化

### 5. ⚡ 性能全面优化（v6.0 升级）
- **SQL 分页查询**：数据/审核/日志/用户列表全部分页（pageSize ≤ 100）
- **React Query 缓存**：`staleTime: 30s` + `placeholderData`，翻页零闪烁
- **4 处防抖**：搜索 500ms / 字段编辑 300ms / AI 历史 800ms / 主题配色 500ms
- **渲染优化**：`useMemo` / `useCallback` 避免无效重渲染
- **统计取样**：字段统计按取样（LIMIT 1000）计算，避免全表扫描
- **ECharts 实例复用**：按需加载

### 6. 🎨 9 种背景质感系统（v6.0 升级）
| 质感 | 说明 |
|:---|:---|
| 🪟 玻璃 Glass | 毛玻璃 + 透明叠加 |
| 🌫️ 磨砂 Frosted | 磨砂颗粒 + 柔和过渡 |
| ⚙️ 金属 Metallic | 金属拉丝高光 |
| 📄 纸张 Paper | 纸张纹理 |
| 💡 霓虹 Neon | 发光强调色 |
| 🌊 液态网格 Liquid-Mesh | 动态流动网格 |
| 🌌 深度 Depth | 渐变景深 |
| 👁️ 透明 Transparent | 极简半透明 |
| ▦ 极简平面 Flat | 纯色扁平 |

- **全 CSS 变量驱动**：`data-texture` + `data-theme` 双属性，150ms 平滑过渡
- **四色自定义配色**：强调色 / 背景色 / 卡片色 / 文本色
- **玻璃透明度可调** + **自定义背景图上传**
- **按用户隔离**：主题配置存入后端 `users.theme`

### 7. ✅ 企业级审核工作流
覆盖数据增删改、字段增删改、用户管理、数据库重置等 **15+ 种操作**。Boss 直接执行，非 Boss 进入待审核队列，审批通过后自动解析原始操作执行，全程审计日志。

### 8. 📦 4 种部署形态
| 形态 | 场景 |
|:---|:---|
| 🖥️ Electron 桌面 | Windows / macOS / Linux，SQLite 本地库 |
| 🐳 Docker Compose | Nginx + Flask + MySQL，生产首选 |
| 📦 PyInstaller EXE | 单文件便携交付，零依赖 |
| 🌐 纯 Web | Nginx + Gunicorn，任意云服务器 |

### 9. 🛡️ 全链路数据安全
密码 PBKDF2-SHA256 加盐哈希 · 数据库 AES-256-GCM 加密 · **API Key 仅存内存不落盘** · 审计日志全量记录不可篡改 · 会话隔离 + Token 校验。

### 10. ⏱️ 12 天 25 版本极速迭代
07-19 MVP → 07-20 功能完善 → 07-21 架构升级 → 07-22~27 AI 集成 → 07-28~08-13 UX & 个性化 → 08-13~14 v6.0 性能与质感升级。

---

## 四、功能特性清单（白皮书章节素材）

| 类别 | 功能 | 说明 |
|:---|:---|:---|
| 🔐 认证授权 | 多角色登录 | Boss / HR / Employee / 自定义 四角色 |
| | 细粒度权限 | 21 项功能点，自由勾选组合 |
| | Session + Token | 双模认证，兼容浏览器 & API 客户端 |
| 📊 动态数据 | 7 种字段类型 | 文本/数字/日期/下拉/布尔/长文本/文件上传 |
| | 内联编辑 | 表格内直接修改，即时保存 |
| | 分页排序搜索 | 大数据量流畅交互 |
| | 文件上传 | 图片/PDF/Office，自动分日期存储 |
| ✅ 审核流 | 全局审核开关 | 每个用户独立控制 |
| | 待审核队列 | 15+ 种操作类型 |
| | 自动执行 | 审批通过后自动解析原始操作并执行 |
| 📈 统计分析 | ECharts 可视化 | 饼图/柱状图/折线图 |
| | 按字段统计 | 任意字段自由统计 |
| 🤖 AI 分析 | 多模型支持 | DeepSeek / OpenAI / 通义千问 / 文心一言 / 自定义 |
| | 对话式分析 | 自然语言提问，报告 + 多轮追问 |
| | 流式输出 | 实时查看 AI 分析过程 |
| | 语音输入 | Web Speech API 语音转文字 |
| | 历史记录 | 报告与对话按用户隔离自动保存 |
| 🎨 主题质感 | 9 种背景质感 | 玻璃/磨砂/金属/纸张/霓虹/液态网格/深度/透明/极简平面 |
| | 四色自定义配色 | 品牌强调色、背景色、卡片色、文本色 |
| | 按用户隔离 | 主题配置独立存储，登录自动恢复 |
| 🗄️ 数据库 | SQLite + MySQL | 双引擎无缝切换，一行配置 |
| | 统一适配层 | DatabaseAdapter ABC 抽象，SQL 方言自动转换 |
| 📦 导入导出 | Excel 导入 | 智能识别表头，自动创建字段 |
| | Excel 导出 | 紫色渐变表头，专业格式 |
| | 备份恢复 | 一键备份 DB 文件，上传恢复 |
| 📝 审计日志 | 全量记录 | 所有操作不可篡改 |
| | 导出 TXT | UTF-8 BOM 编码，Excel 友好 |
| 🖥️ 多端部署 | Electron 桌面 | Windows/macOS/Linux 原生窗口 |
| | Docker Compose | 一键启动 MySQL + Flask + Nginx |
| | PyInstaller | 单 EXE 交付 |

---

## 五、技术架构（白皮书核心章节）

### 5.1 系统总体架构（分层）

```
用户层     浏览器 / Electron 桌面客户端
前端层     React 18 + TypeScript + Vite + Ant Design 5 + TailwindCSS + ECharts + Zustand + React Query
网关层     认证中间件（Session + Bearer Token）→ 权限检查（@require_perm，21 项）→ 审核网关
后端层     Flask 3.x + Waitress（生产级 WSGI，20 线程）+ 49 个 REST API
数据层     DatabaseAdapter（ABC 抽象基类 + 工厂模式）→ SQLiteAdapter / MySQLAdapter
附加层     AI 服务（5 模型 · 流式解析 · 联网搜索 · 历史）· 文件存储（uploads/ backups/）
```

**设计亮点**：从用户操作到数据库落盘，经过 **认证 → 权限 → 审核** 三层网关，每一步可控、可追溯。

### 5.2 技术栈清单

| 层级 | 技术 | 版本 |
|:---|:---|:---:|
| 前端框架 | React + TypeScript | 18.x |
| UI 组件库 | Ant Design | 5.x |
| 样式方案 | TailwindCSS + CSS Modules | — |
| 状态管理 | Zustand | — |
| 数据请求 | TanStack Query (React Query) | — |
| 图表可视化 | ECharts | — |
| 路由 | React Router | v6 |
| 构建工具 | Vite | — |
| 后端框架 | Flask | 3.x |
| 生产服务器 | Waitress | 20 线程 / 150+ 并发 |
| 数据库 | SQLite / MySQL 8.0 | 双引擎适配层 |
| 桌面壳 | Electron | 28.x |
| 打包 | electron-builder / PyInstaller / Inno Setup | — |
| 容器化 | Docker + docker-compose | — |
| 压测 | Locust | — |
| AI 模型 | DeepSeek / OpenAI / 通义千问 / 文心一言 / 自定义 | — |
| 安全加密 | PBKDF2-SHA256 · AES-256-GCM | — |

### 5.3 前端页面（12 个）
登录页、数据登记页、字段管理页、统计分析页、审核中心、操作日志、用户管理、AI 分析页、备份恢复、系统设置，加上主题质感系统、悬浮主题切换组件。

### 5.4 核心接口与功能模块（49 个 API 端点）
auth（登录/登出/当前用户）、columns（字段 CRUD）、rows（数据 CRUD + 分页搜索）、stats（统计）、audit（审核队列 + 审批）、logs（操作日志 + 导出）、users（用户管理）、theme（主题配置）、backup（备份恢复）、ai（models/test/analyze/chat/history）、health。

---

## 六、数据库设计（白皮书数据章节）

8 张核心表：

| 表名 | 用途 | 关键字段 |
|:---|:---|:---|
| `users` | 用户 | username, password_hash(PBKDF2-SHA256), role, permissions(JSON 21项), global_audit, theme(JSON) |
| `columns_meta` | 动态字段定义 | name(col_0), label, field_type(7种), options(JSON), position, required |
| `rows_data` | 业务数据 | _created_by, dynamic_columns（随 columns_meta 自动扩展） |
| `pending_changes` | 待审核队列 | row_id, column_name, old/new_value(JSON), change_type(15+), status, review_comment |
| `operations_log` | 操作审计日志 | user_id, username, role, action, target_type, target_id, detail(JSON) |
| `system_config` | 系统配置 | key, value |
| `backups` | 备份管理 | filename, size_bytes |
| `ai_analysis_history` | AI 分析历史（v5.1 新增） | user_id(隔离), report, chat_history(JSON) |

表关系：users → pending_changes / operations_log / rows_data / ai_analysis_history；columns_meta → rows_data。

---

## 七、权限模型与审核工作流（白皮书安全章节）

### 7.1 四级角色
| 角色 | 权限 | 特点 |
|:---|:---|:---|
| 👑 Boss | 21 项全开 | 直接执行，无需审核 |
| 👔 HR | 18 项 | 高级操作需审核（含删除） |
| 👤 Employee | 5 项只读 | 查看 + 搜索 |
| 🔧 自定义 | JSON 自由组合 | 任意勾选 |

### 7.2 21 项细粒度权限分组
- 数据操作（5）：view / search / add / edit / delete
- 字段管理（4）：add / edit / delete / batch_add
- 导入导出（2）：import_excel / export_excel
- 日志管理（3）：view / export / clear_logs
- 高级管理（4）：audit_center / approve_reject / manage_users / reset_database
- 其他（3）：customize_theme / view_structure / view_stats

### 7.3 审核工作流（状态机）
```
用户操作 → 权限检查(@require_perm) → [Boss 角色] 直接执行
                                  → [HR/Employee] 检查 global_audit
                                       ├─ 关闭 → 直接执行
                                       └─ 开启 → pending_changes 待审核队列
                                                 ├─ 审批通过 → 解析原始操作自动执行
                                                 └─ 驳回 → 记录日志
→ 全部写入 operations_log 审计日志
```

---

## 八、性能测试（白皮书数据章节 / PPT 说服力页）

测试工具：**Locust** ｜ 测试环境：本地开发环境（SQLite 模式）

### 总体数据
| 项目 | 数值 |
|:---|:---|
| 并发用户 | **170** |
| 总请求数 | **2,100+** |
| 失败率 | **0%** |
| 聚合 RPS | **39.4** |
| 中位响应 | 32ms |
| 平均响应 | 42.38ms |
| P95 | 120ms |
| P99 | 190ms |

### 核心接口明细
| 接口 | 请求数 | Median | P95 | P99 | Average | 失败 |
|:---|---:|---:|---:|---:|---:|---:|
| GET /api/health | 72 | 3ms | 16ms | 22ms | 4.35ms | 0 |
| GET /api/audit/count | 64 | 24ms | 65ms | 140ms | 30.77ms | 0 |
| GET /api/columns | 746 | 31ms | 110ms | 140ms | 38.36ms | 0 |
| GET /api/rows | 746 | 32ms | 95ms | 160ms | 39.82ms | 0 |
| GET /api/stats/fields | 200 | 33ms | 110ms | 190ms | 38.64ms | 0 |
| GET /api/me | 117 | 33ms | 85ms | 110ms | 36.79ms | 0 |
| GET /api/logs | 57 | 36ms | 120ms | 130ms | 44.22ms | 0 |
| POST /api/login | 98 | 130ms | 220ms | 270ms | 141.08ms | 0 |
| **Aggregated** | **2,100** | **32ms** | **120ms** | **190ms** | **42.38ms** | **0** |

> 压测命令：`locust -f locustfile.py --host=http://127.0.0.1:5001`
> 压测截图：`docs/assets/locust-benchmark.jpg`

---

## 九、版本演进与开发历程（PPT 故事线 / 白皮书附录）

### 9.1 版本时间线
| 版本 | 日期 | 里程碑 |
|:---|:---|:---|
| v0.1-alpha | 07-19 | MVP：动态字段 + 数据录入 + 列表展示 |
| v1.0-beta | 07-20 | 权限系统：3 角色 + 登录/登出 |
| v1.1-beta | 07-20 | 审核机制：pending_changes + 审批流程 |
| v2.0-rc | 07-21 | 21 项细粒度权限 + 自定义角色 |
| v2.2-rc | 07-21 | ECharts 统计看板 |
| v3.0 | 07-22 | 正式版 + EXE 安装包交付 |
| v4.0 | 07-27 | 架构重构（React + Electron + 双库 + Docker）+ 压测 + 开源 |
| v4.1 | 07-27 | AI 数据分析：多模型对话式智能分析 |
| v5.0 | 07-28 | UX 大升级 + 安全增强 + AI 稳定性修复 |
| v5.1 | 08-13 | 个性化与合规：用户主题系统、HR 删除纳入审核、AI 按角色定制 |
| v6.0 | 08-14 | 性能优化 + AI 操作逻辑升级 + 9 种背景质感系统 |

### 9.2 开发历程故事线（PPT 叙事素材）
> 一个"从无聊开始"的项目，12 天迭代 25 个版本。

**起因**：暑假打游戏打腻了、刷视频刷吐了，看到一个字段写死的登记系统想加列却加不了——"要不，我自己写一个？"

**关键节点**：
1. **第 1 天**：敲了一晚上，跑通了，界面丑但能动
2. **第 2 天**：疯狂加功能，代码全线崩溃，凌晨烂尾
3. **第 3 天**：编码错误全量报错，没 git 去回收站翻备份，从此被逼学会 git
4. **第 4 天**：发小红书被喷，但两条建议在理（SQLite 太单调、UI 太难看）——后来都成了核心功能
5. **第 5 天**：换到 2026 年的开发工具流，之前拧巴的地方全顺了
6. **第 6 天**：MySQL 双库跑通
7. **第 7 天**：170 并发压测，72 小时 0 失败
8. **第 8 天**：UI 全面优化，8 种质感 + 自定义背景 + 协议文档
9. **第 9 天**：接 AI 数据分析（API Key 加密、超时调优、Prompt 收窄）
10. **第 10 天**：Docker 本地失败 → 绕道 GitHub Actions 在线构建成功
11. **第 11 天**：补 HR 审核窟窿 + 主题系统 + AI 按角色定制（v5.1）
12. **第 12 天**：性能优化 + AI 多模型 + 9 种质感（v6.0），git push 见绿

**沉淀的经验**（白皮书结语可用）：
1. git 越早学越好
2. 一个功能加一个验证，别一次堆一堆
3. 被喷不全是坏事，虚心接受有效反馈
4. 不熟悉的工作流先摸清再铺开
5. 数据多了先分页，别急着上框架

**完整迭代统计**：25 版本 / 20 新增 / 3 修复 / 3 优化 / 1 回滚 / 12 天 / 阶段跨度 alpha → beta → rc → 正式版 → 架构重构 → AI 增强 → UX 升级 → 个性化合规 → 性能质感

---

## 十、部署方案（白皮书部署章节 / PPT 一页）

| 方式 | 架构 | 适用场景 |
|:---|:---|:---|
| Electron 桌面 | BrowserWindow + Flask 子进程(:5001) + React SPA + SQLite | 单机 / 离线 |
| Docker Compose | Nginx(:80) + Flask(:5001 Waitress) + MySQL 8.0 | 生产环境首选 |
| PyInstaller 单文件 | desktop.exe（pywebview 内嵌）+ Flask + SQLite | 便携交付 |
| 纯 Web | 浏览器 + Nginx/CDN + Flask 生产模式 + MySQL/SQLite | 云服务器 |

**默认账户**（演示用）：boss / hr / employee，密码均为 `123456`（首次登录后请修改）。

---

## 十一、安全与合规（白皮书合规章节）

**安全措施**：
- 密码 PBKDF2-SHA256 加盐哈希
- 数据库 AES-256-GCM 透明加密
- API Key 仅存 React 内存，不落盘、不传服务器
- 审计日志全量记录不可篡改
- 认证（Session + Bearer Token）→ 权限 → 审核三层网关
- 文件上传类型校验，自动分日期存储

**隐私承诺**（隐私政策要点）：
- 软件完全运行于本地设备，不主动收集、上传、存储任何个人数据
- 不使用 Cookie 追踪，无第三方 SDK / 广告 / 分析工具
- 核心功能无需联网，仅主动点击检查更新时发起请求
- 用户对数据拥有完全控制权：查阅、修改、导出、备份、删除

**用户协议要点**：MIT 许可（个人/商业免费使用）、禁止违法用途、业务数据归用户所有、本地存储免责声明。

---

## 十二、可引用素材清单（做 PPT / 白皮书时直接取用）

| 素材 | 位置 | 用途 |
|:---|:---|:---|
| Locust 压测截图 | `docs/assets/locust-benchmark.jpg` | 性能章节配图 |
| 数据概览截图 | `docs/assets/screenshot-overview.jpg` | 产品截图 |
| 桌面端 UI 截图 | `docs/assets/demo-app-overview.png` | 产品截图 |
| 角色形象（透明PNG） | `docs/assets/character-pack.png` | 视觉装饰 |
| 梗图 | `docs/assets/meme-spine.png` | 彩蛋素材 |
| GitHub 头像 | `docs/assets/github-avatar.png` | 作者介绍页 |
| 演示页 | `demo.html` / `demo/demo.html` | 在线演示（含滚动动效） |
| 架构图 | `架构图.md`（7 张 Mermaid 图） | 白皮书插图 |
| GitHub 仓库 | https://github.com/jincheng3870682453-hash | 开源链接 |
| 掘金文章 | https://juejin.cn/post/7672852599783587874 | 开发历程引用 |

---

## 十三、PPT 页结构建议（可直接采用）

1. **封面**：项目名 + Slogan + 作者 + 版本
2. **核心数据**：9 个数字卡片（49 API / 12 页面 / 4 角色 / 21 权限 / 7 字段 / 15+ 审核 / 9 质感 / 170 并发 / 42ms）
3. **项目背景**：字段写死的登记系统 → 自己动手（讲故事）
4. **系统架构**：四层架构图（用户/前端/网关/后端/数据）
5. **功能全景**：12 个页面模块
6. **动态字段引擎**：7 种字段类型
7. **权限与审核**：4 级角色 + 21 项权限 + 审核工作流
8. **AI 分析**：5 模型 + 语音 + 联网 + 历史
9. **性能优化**：v6.0 全链路优化点
10. **压测结果**：170 并发 / 0% 失败 / 42ms
11. **9 种背景质感**：视觉效果展示
12. **部署方案**：4 种形态
13. **版本演进**：时间线 12 天 25 版本
14. **开发历程**：第 1 天到第 12 天的故事
15. **安全与合规**：加密 / 隐私 / 协议
16. **结尾**：GitHub + 掘金 + 致谢
