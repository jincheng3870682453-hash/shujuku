# 🔮 动态数据登记系统 · Dynamic Registry

<p align="center">
  <img src="https://img.shields.io/badge/version-5.0-blue?style=for-the-badge" alt="version">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="license">
  <img src="https://img.shields.io/badge/python-3.9+-orange?style=for-the-badge&logo=python" alt="python">
  <img src="https://img.shields.io/badge/react-18-blue?style=for-the-badge&logo=react" alt="react">
  <img src="https://img.shields.io/badge/electron-28-47848f?style=for-the-badge&logo=electron" alt="electron">
  <img src="https://img.shields.io/badge/docker-ready-2496ed?style=for-the-badge&logo=docker" alt="docker">
</p>

<p align="center">
  <b>一个动态字段、双数据库引擎、三级权限审核的 Web/桌面一体化数据管理平台</b>
</p>

<p align="center">
  <a href="#-系统架构">架构</a> ·
  <a href="#-快速开始">快速开始</a> ·
  <a href="#-项目结构">项目结构</a> ·
  <a href="#-数据库表结构">ER 图</a> ·
  <a href="#-审核工作流">审核流程</a> ·
  <a href="#-部署方案">部署</a> ·
  <a href="#-性能测试">压测</a> ·
  <a href="#-v50-更新公告">更新公告</a> ·
  <a href="#-完整版本历史">版本历史</a> ·
  <a href="#-用户协议">用户协议</a> ·
  <a href="#-隐私政策">隐私政策</a>
</p>

---

## 📖 目录

- [系统架构](#-系统架构)
- [功能特性](#-功能特性)
- [技术栈](#-技术栈)
- [请求处理流程](#-请求处理流程)
- [前端组件树](#-前端组件树)
- [数据库表结构 (ER 图)](#-数据库表结构)
- [权限模型](#-权限模型)
- [审核工作流](#-审核工作流)
- [部署架构](#-部署方案)
- [性能测试](#-性能测试)
- [v4.1 更新公告](#-v41-更新公告)
- [v5.0 更新公告](#-v50-更新公告)
- [完整版本历史](#-完整版本历史)
- [用户协议](#-用户协议)
- [隐私政策](#-隐私政策)
- [快速开始](#-快速开始)
- [项目结构](#-项目结构)
- [默认账户](#-默认账户)
- [数据库切换](#-数据库切换)
- [打包发布](#-打包发布)
- [FAQ](#-常见问题)
- [License](#-license)

---

## 🏗 系统架构

```mermaid
graph TB
    subgraph UserLayer["👤 用户层"]
        Browser["🌐 浏览器"]
        Desktop["🖥️ 桌面客户端 (Electron)"]
    end

    subgraph FrontendLayer["⚛️ 前端层 (React 18 + TypeScript + Vite)"]
        direction TB
        Login["🔐 登录页<br/>极简暗色认证"]
        DataTable["📊 数据登记<br/>内联编辑 + 折叠 + 平滑滑动"]
        Columns["📋 字段管理<br/>7 种字段类型自由配置"]
        Stats["📈 统计分析<br/>ECharts 饼图/柱状图/折线图"]
        Audit["✅ 审核中心<br/>待审核队列 + 审批操作"]
        Logs["📝 操作日志<br/>全量记录 + 导出"]
        Users["👥 用户管理<br/>增删改 + 细粒度权限"]
        AIAnalysis["🤖 AI 分析<br/>多模型对话式数据分析"]
        Backup["💾 备份恢复<br/>一键备份 + 上传恢复"]
        Settings["⚙️ 系统设置<br/>主题 + 数据库引擎切换"]
    end

    subgraph GatewayLayer["🛡️ 网关层 (Flask Middleware)"]
        Auth["认证中间件<br/>Session + Bearer Token 双模"]
        PermCheck["权限检查<br/>@require_perm 装饰器<br/>21 项细粒度权限"]
        AuditGate["审核网关<br/>非 Boss 操作 → pending_changes"]
    end

    subgraph BackendLayer["🐍 后端层 (Flask + Waitress 生产模式)"]
        direction TB
        API["REST API<br/>30+ 端点"]
        BizLogic["业务逻辑<br/>CRUD / 统计 / 导入导出<br/>备份恢复 / 用户管理"]
        AuditEngine["审核引擎<br/>解析原始操作 → 自动执行<br/>支持 15+ 种 change_type"]
    end

    subgraph DataLayer["🗄️ 数据抽象层"]
        Adapter["DatabaseAdapter 统一接口<br/>ABC 抽象基类 + 工厂模式"]
        SQLite["SQLiteAdapter<br/>默认引擎 · 零配置<br/>适合单机/桌面"]
        MySQL["MySQLAdapter<br/>生产级引擎<br/>适合多用户/高并发"]
        FileStore["📁 文件存储<br/>uploads/ backups/"]
    end

    Browser --> Login
    Desktop --> Login
    Login --> Auth
    Auth --> PermCheck
    PermCheck --> AuditGate
    AuditGate --> API
    API --> BizLogic
    API --> AuditEngine
    BizLogic --> Adapter
    AuditEngine --> Adapter
    Adapter --> SQLite
    Adapter --> MySQL
    BizLogic --> FileStore

    style UserLayer fill:#1a1a2e,stroke:#e94560,color:#fff
    style FrontendLayer fill:#0f3460,stroke:#61dafb,color:#fff
    style GatewayLayer fill:#16213e,stroke:#f39c12,color:#fff
    style BackendLayer fill:#0a0a23,stroke:#00d2ff,color:#fff
    style DataLayer fill:#1a1a2e,stroke:#27ae60,color:#fff
```

> 🔍 **设计亮点**：从用户操作到数据库落盘，经过 **认证 → 权限 → 审核** 三层网关，确保每一步都可控、可追溯。

---

## ✨ 功能特性

| 类别 | 功能 | 说明 |
|:---|:---|:---|
| 🔐 **认证授权** | 多角色登录 | Boss / HR / Employee / 自定义 四角色 |
| | 细粒度权限 | 21 项功能点，自由勾选组合 |
| | Session + Token | 双模认证，兼容浏览器 & API 客户端 |
| 📊 **动态数据** | 7 种字段类型 | 文本/数字/日期/下拉/布尔/长文本/文件上传 |
| | 内联编辑 | 表格内直接修改，即时保存 |
| | 分页排序搜索 | 大数据量流畅交互 |
| | 文件上传 | 支持图片/PDF/Office，自动分日期存储 |
| ✅ **审核流** | 全局审核开关 | 每个用户独立控制 |
| | 待审核队列 | 支持 15+ 种操作类型审核 |
| | 自动执行 | 审批通过后自动解析原始操作并执行 |
| 📈 **统计分析** | ECharts 可视化 | 饼图/柱状图/折线图 |
| | 按字段统计 | 任意字段自由统计 |
| 🤖 **AI 分析** | 多模型支持 | DeepSeek / OpenAI / 通义千问 一键切换 |
| | 对话式分析 | 自然语言提问，智能数据洞察 |
| | 流式输出 | 实时查看 AI 分析过程 |
| 🗄️ **数据库** | SQLite + MySQL | 双引擎无缝切换，一行配置 |
| | 统一适配层 | DatabaseAdapter ABC 抽象，? 占位符统一 |
| 📦 **导入导出** | Excel 导入 | 智能识别表头，自动创建字段 |
| | Excel 导出 | 紫色渐变表头，专业格式 |
| | 备份恢复 | 一键备份 DB 文件，上传恢复 |
| 📝 **审计日志** | 全量记录 | 所有操作不可篡改 |
| | 导出 TXT | UTF-8 BOM 编码，Excel 友好 |
| 🖥️ **多端部署** | Electron 桌面 | Windows/macOS/Linux 原生窗口 |
| | Docker Compose | 一键启动 MySQL + Flask + Nginx |
| | PyInstaller | 单 EXE 交付 |

---

## 🛠️ 技术栈

| 层级 | 技术 | 版本 |
|:---|:---|:---:|
| **前端框架** | React + TypeScript | 18.x |
| **UI 组件库** | Ant Design | 5.x |
| **样式方案** | TailwindCSS + CSS Modules | — |
| **状态管理** | Zustand | — |
| **数据请求** | TanStack Query (React Query) | — |
| **图表可视化** | ECharts | — |
| **路由** | React Router | v6 |
| **构建工具** | Vite | — |
| **后端框架** | Flask | 3.x |
| **生产服务器** | Waitress | 20 线程 / 150+ 并发 |
| **数据库** | SQLite / MySQL 8.0 | 双引擎适配层 |
| **桌面壳** | Electron | 28.x |
| **打包** | electron-builder / PyInstaller / Inno Setup | — |
| **容器化** | Docker + docker-compose | — |
| **压测** | Locust | — |

---

## 🔄 请求处理流程

```mermaid
sequenceDiagram
    actor U as 👤 用户
    participant FE as ⚛️ React 前端
    participant GW as 🐍 Flask 网关
    participant Auth as 🔐 认证模块
    participant Perm as 🛡️ 权限检查
    participant Audit as ✅ 审核引擎
    participant BL as ⚙️ 业务逻辑
    participant DB as 🔌 数据库适配器
    participant DS as 🗄️ SQLite / MySQL

    U->>FE: 点击操作（新增/编辑/删除）
    FE->>GW: HTTP Request<br/>Authorization: Bearer session-{uid}
    GW->>Auth: @before_request<br/>从 Token 恢复 Session
    Auth->>Perm: @require_perm 装饰器<br/>检查 21 项细粒度权限

    alt ❌ 权限不足
        Perm-->>FE: 403 Forbidden
    else ✅ 权限通过
        Perm->>Audit: 检查审核状态

        alt 🔒 非 Boss + 审核开启
            Audit->>DB: INSERT INTO pending_changes
            Audit-->>FE: 200 {"message": "已提交审核"}
        else 🔓 Boss 或审核关闭
            Audit->>BL: 直接执行业务逻辑
            BL->>DB: SQL 操作 (统一 ? 占位符)
            DB->>DS: 执行 (自动转换 SQL 方言)
            DS-->>DB: 结果
            DB-->>BL: 结果
            BL->>DB: INSERT INTO operations_log
            BL-->>FE: 200 操作成功
        end
    end
```

---

## 🌳 前端组件树

```mermaid
graph TB
    App["App.tsx<br/>Ant Design ConfigProvider<br/>紫色渐变主题"]

    Router["RouterProvider<br/>React Router v6"]

    LoginPage["Login.tsx<br/>🔐 极简暗色认证页<br/>毛玻璃效果"]

    AuthGuard["AuthGuard 路由守卫<br/>未登录自动跳转"]

    AppLayout["AppLayout.tsx<br/>📐 侧边导航 + 顶栏<br/>用户菜单 + 退出"]

    subgraph Pages["📄 页面组件"]
        DataTable["DataTable.tsx<br/>📊 数据表格<br/>统计卡片 + 内联编辑"]
        Columns["Columns.tsx<br/>📋 字段配置<br/>7 种类型 + 拖拽排序"]
        Stats["Stats.tsx + Charts.tsx<br/>📈 ECharts 可视化<br/>饼图/柱状图/折线图"]
        AuditPage["Audit.tsx<br/>✅ 审核列表<br/>通过/驳回 + 评论"]
        LogsPage["Logs.tsx<br/>📝 操作日志<br/>搜索 + 导出TXT"]
        UsersPage["Users.tsx<br/>👥 用户管理<br/>增删改 + 权限勾选"]
        AIAnalysis["AIAnalysis.tsx<br/>🤖 AI 数据分析<br/>多模型 + 对话式"]
        BackupPage["Backup.tsx<br/>💾 备份恢复<br/>上传DB + 一键下载"]
        SettingsPage["Settings.tsx<br/>⚙️ 主题 + DB引擎切换<br/>MySQL 连接测试"]
    end

    subgraph Shared["🧩 共享组件"]
        EditableCell["EditableCell.tsx<br/>✏️ 内联编辑单元格"]
        FloatingBtn["FloatingThemeButton.tsx<br/>🎨 悬浮主题切换"]
    end

    subgraph State["🗃️ 状态管理"]
        ReactQuery["@tanstack/react-query<br/>服务端状态缓存"]
        Zustand["Zustand Stores<br/>columnStore / dataStore"]
    end

    subgraph APILayer["🌐 API 层 (自动检测环境)"]
        AuthAPI["api/auth.ts"]
        ColumnsAPI["api/columns.ts"]
        DataAPI["api/data.ts"]
        AuditAPI["api/audit.ts"]
        LogsAPI["api/logs.ts"]
        OtherAPI["users / backup / settings / stats"]
    end

    App --> Router
    Router --> LoginPage
    Router --> AuthGuard
    AuthGuard --> AppLayout
    AppLayout --> Pages
    Pages --> Shared
    Pages --> State
    State --> APILayer

    style App fill:#0f3460,stroke:#e94560,color:#fff
    style Pages fill:#16213e,stroke:#00d2ff,color:#fff
    style State fill:#1a1a2e,stroke:#f39c12,color:#fff
    style APILayer fill:#0a0a23,stroke:#27ae60,color:#fff
```

---

## 🗄️ 数据库表结构

```mermaid
erDiagram
    users {
        int id PK "自增主键"
        string username UK "用户名（唯一）"
        string password_hash "PBKDF2-SHA256 哈希"
        string role "boss / hr / employee / custom"
        json permissions "21 项细粒度权限数组"
        bool global_audit "全局审核开关"
        string created_at "创建时间"
    }

    columns_meta {
        int id PK "自增主键"
        string name UK "内部列名 col_0"
        string label "显示标签"
        string field_type "text/number/date/select/boolean/textarea/file"
        string options "下拉选项 JSON"
        int position "排序位置"
        bool required "是否必填"
    }

    rows_data {
        int id PK "自增主键"
        string _created_by "创建者用户名"
        varchar dynamic_columns "动态列（随 columns_meta 自动扩展）"
    }

    pending_changes {
        int id PK "自增主键"
        int row_id "目标行ID"
        string column_name "目标列名"
        text old_value "旧值 JSON"
        text new_value "新值 JSON"
        string change_type "操作类型（15+ 种）"
        int requested_by FK "申请人ID"
        string status "待审核/已通过/已驳回"
        int reviewed_by "审核人ID"
        text review_comment "审核意见"
        string reviewed_at "审核时间"
        string created_at "申请时间"
    }

    operations_log {
        int id PK "自增主键"
        int user_id "操作用户ID"
        string username "操作用户名"
        string role "操作角色"
        string action "操作描述"
        string target_type "目标类型"
        string target_id "目标ID"
        text detail "详情 JSON"
        string created_at "操作时间"
    }

    system_config {
        string key PK "配置键"
        string value "配置值"
        string updated_at "更新时间"
    }

    backups {
        int id PK "自增主键"
        string filename UK "备份文件名"
        int size_bytes "文件大小"
        string created_at "创建时间"
    }

    users ||--o{ pending_changes : "提交审核"
    users ||--o{ operations_log : "产生日志"
    users ||--o{ rows_data : "创建数据"
    columns_meta ||--o{ rows_data : "定义结构"
```

---

## 🔐 权限模型

```mermaid
graph LR
    subgraph Roles["🎭 预设角色"]
        Boss["👑 Boss<br/>21 项权限 · 全部开放"]
        HR["👔 HR<br/>18 项权限 · 需审核"]
        Employee["👤 Employee<br/>5 项权限 · 只读"]
        Custom["🔧 自定义<br/>自由勾选组合"]
    end

    subgraph Perms["🔑 21 项细粒度权限"]
        direction TB

        subgraph DataPerm["📊 数据操作"]
            P_view["view_data"]
            P_search["search_data"]
            P_add["add_data"]
            P_edit["edit_data"]
            P_delete["delete_data"]
        end

        subgraph FieldPerm["📋 字段管理"]
            P_add_f["add_field"]
            P_edit_f["edit_field"]
            P_del_f["delete_field"]
            P_batch["batch_add_field"]
        end

        subgraph IOPerm["📦 导入导出"]
            P_import["import_excel"]
            P_export["export_excel"]
        end

        subgraph LogPerm["📝 日志管理"]
            P_v_log["view_logs"]
            P_e_log["export_logs"]
            P_c_log["clear_logs"]
        end

        subgraph AdminPerm["⚙️ 高级管理"]
            P_audit["audit_center"]
            P_approve["approve_reject"]
            P_manage["manage_users"]
            P_reset["reset_database"]
        end

        subgraph OtherPerm["🎨 其他"]
            P_theme["customize_theme"]
            P_struct["view_structure"]
            P_stats["view_stats"]
        end
    end

    Boss --> DataPerm & FieldPerm & IOPerm & LogPerm & AdminPerm & OtherPerm
    HR --> DataPerm & FieldPerm & IOPerm & LogPerm & OtherPerm
    HR -.->|"🔒 需审核"| AdminPerm
    Employee --> P_view & P_search & P_v_log & P_struct & P_theme
    Custom -->|"JSON 自由配置"| DataPerm & FieldPerm & IOPerm & LogPerm & AdminPerm & OtherPerm

    style Boss fill:#e94560,color:#fff
    style HR fill:#f39c12,color:#fff
    style Employee fill:#27ae60,color:#fff
    style Custom fill:#8e44ad,color:#fff
```

---

## ✅ 审核工作流

```mermaid
stateDiagram-v2
    [*] --> UserAction: 用户操作

    state UserAction {
        Add: 新增数据
        Edit: 编辑数据
        Delete: 删除数据
        AddField: 新增字段
        EditField: 修改字段
        DelField: 删除字段
        AddUser: 添加用户
        EditUser: 修改用户
        DelUser: 删除用户
        Clear: 清空数据/日志
    }

    UserAction --> PermCheck: @require_perm

    PermCheck --> DirectExec: 👑 Boss 角色
    PermCheck --> AuditCheck: 👔 HR / 👤 Employee

    AuditCheck --> DirectExec: global_audit = false
    AuditCheck --> PendingQueue: global_audit = true

    PendingQueue --> Approved: ✅ 管理员审批通过
    PendingQueue --> Rejected: ❌ 管理员驳回

    Approved --> AutoExec: 解析原始操作
    state AutoExec {
        InsertRow: INSERT rows_data
        UpdateRow: UPDATE rows_data
        DeleteRow: DELETE rows_data
        AlterColumn: ALTER columns_meta
        ManageUser: INSERT/UPDATE/DELETE users
    }

    AutoExec --> LogIt: 写入 operations_log
    DirectExec --> LogIt
    Rejected --> LogIt

    LogIt --> [*]
```

---

## 🚀 部署方案

```mermaid
graph TB
    subgraph Deploy1["🖥️ 方式一：Electron 桌面版"]
        direction TB
        E1["Electron 壳<br/>BrowserWindow"]
        E2["Flask 子进程 :5001<br/>自动启动/关闭"]
        E3["React SPA<br/>static/ 目录"]
        E4["SQLite 本地数据库<br/>registry.db"]
        E1 --> E2
        E1 --> E3
        E2 --> E4
    end

    subgraph Deploy2["🐳 方式二：Docker Compose"]
        direction TB
        D1["Nginx :80<br/>反向代理 + 静态文件"]
        D2["Flask :5001<br/>Waitress 20线程"]
        D3["MySQL 8.0 :3306<br/>utf8mb4 + 健康检查"]
        D1 --> D2
        D1 -->|"静态文件"| D_Static["frontend/dist/"]
        D2 --> D3
    end

    subgraph Deploy3["📦 方式三：PyInstaller 单文件"]
        direction TB
        P1["desktop.exe<br/>pywebview 内嵌浏览器"]
        P2["Flask 后端<br/>打包进 EXE"]
        P3["SQLite<br/>便携数据库"]
        P1 --> P2
        P2 --> P3
    end

    subgraph Deploy4["🌐 方式四：纯 Web 部署"]
        direction TB
        W1["浏览器"]
        W2["Nginx / CDN<br/>静态托管"]
        W3["Flask 服务器<br/>生产模式"]
        W4["MySQL / SQLite<br/>按需选择"]
        W1 --> W2
        W2 --> W3
        W3 --> W4
    end

    style Deploy1 fill:#0f3460,stroke:#e94560,color:#fff
    style Deploy2 fill:#1a1a2e,stroke:#2496ed,color:#fff
    style Deploy3 fill:#16213e,stroke:#f39c12,color:#fff
    style Deploy4 fill:#0a0a23,stroke:#27ae60,color:#fff
```

---

## ⚡ 性能测试

使用 **Locust** 对核心 API 进行压力测试（本地开发环境，SQLite 模式）。

### 测试环境

| 项目 | 配置 |
|:---|:---|
| 并发用户 | 170 |
| 总请求数 | 2,100+ |
| 失败率 | **0%** |
| 聚合 RPS | **39.4** |

### 核心接口表现

| 接口 | 请求数 | Median | 95%ile | 99%ile | Average | 失败 |
|:---|---:|---:|---:|---:|---:|---:|
| `GET /api/health` | 72 | 3 ms | 16 ms | 22 ms | 4.35 ms | 0 |
| `GET /api/audit/count` | 64 | 24 ms | 65 ms | 140 ms | 30.77 ms | 0 |
| `GET /api/columns` | 746 | 31 ms | 110 ms | 140 ms | 38.36 ms | 0 |
| `GET /api/rows` | 746 | 32 ms | 95 ms | 160 ms | 39.82 ms | 0 |
| `GET /api/stats/fields` | 200 | 33 ms | 110 ms | 190 ms | 38.64 ms | 0 |
| `GET /api/me` | 117 | 33 ms | 85 ms | 110 ms | 36.79 ms | 0 |
| `GET /api/logs` | 57 | 36 ms | 120 ms | 130 ms | 44.22 ms | 0 |
| `POST /api/login` | 98 | 130 ms | 220 ms | 270 ms | 141.08 ms | 0 |
| **Aggregated** | **2,100** | **32 ms** | **120 ms** | **190 ms** | **42.38 ms** | **0** |

> 测试命令：`locust -f locustfile.py --host=http://127.0.0.1:5001`

<p align="center">
  <img src="docs/assets/locust-benchmark.jpg" alt="Locust 压测结果" width="95%">
</p>

---

## 🚀 快速开始

### 方式一：一键脚本（推荐新手）

**Windows**
```bash
双击 启动.bat，自动检测 Python 环境并安装依赖
```

**macOS / Linux**
```bash
chmod +x start.sh
./start.sh
```

### 方式二：Docker Compose（推荐生产）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 修改数据库密码等

# 2. 一键启动（MySQL + Flask + Nginx）
docker-compose up -d

# 3. 查看日志
docker-compose logs -f backend

# 4. 浏览器打开
# http://localhost
```

### 方式三：手动开发模式

**后端**
```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
python app.py
# 后端运行在 http://localhost:5001
```

**前端**
```bash
cd frontend
npm install
npm run dev
# 前端运行在 http://localhost:3000（自动代理 API 到 5001）
```

**Electron 桌面版**
```bash
# 先启动后端，再运行：
cd electron
npm install
npx tsc
npx electron dist/main.js
```

---

## 📁 项目结构

```
dynamic_registry/
├── app.py                      # 🐍 Flask 后端主入口（1618 行）
├── run.py                      # 🚀 开发启动脚本
├── requirements.txt            # 📦 Python 依赖
├── registry.db                 # 🗄️ SQLite 数据库（默认）
│
├── backend/                    # 🔧 后端核心模块
│   ├── config.py               # ⚙️ 配置管理（.env 读取）
│   ├── db_adapter.py           # 🔌 数据库适配层
│   │   ├── DatabaseAdapter     #    ABC 抽象基类
│   │   ├── SQLiteAdapter       #    SQLite 实现
│   │   └── MySQLAdapter        #    MySQL 实现
│   ├── ai_client.py            # 🤖 AI 多模型客户端（DeepSeek/OpenAI/通义千问）
│   ├── db_crypto.py            # 🔐 数据加密模块
│   ├── test_adapter.py         # 🧪 适配器单元测试
│   └── requirements.txt        # 📦 后端依赖
│
├── frontend/                   # ⚛️ React 前端
│   ├── src/
│   │   ├── api/                # 🌐 API 客户端（自动检测 Electron 环境）
│   │   ├── components/         # 🧩 公共组件
│   │   │   ├── AppLayout.tsx   #    主布局（侧栏 + 顶栏）
│   │   │   └── EditableCell.tsx#    内联编辑单元格
│   │   ├── pages/              # 📄 页面组件
│   │   │   ├── Login.tsx       #    登录页
│   │   │   ├── DataTable.tsx   #    数据登记页
│   │   │   ├── Columns.tsx     #    字段管理页
│   │   │   ├── Stats.tsx       #    统计分析页
│   │   │   ├── Audit.tsx       #    审核中心
│   │   │   ├── Logs.tsx        #    操作日志
│   │   │   ├── Users.tsx       #    用户管理
│   │   │   ├── AIAnalysis.tsx  #    AI 数据分析
│   │   │   └── Settings.tsx    #    系统设置
│   │   ├── stores/             # 🗃️ Zustand 状态管理
│   │   ├── styles/             # 🎨 紫色渐变主题
│   │   ├── types/              # 📐 TypeScript 类型
│   │   └── router/             # 🧭 路由配置
│   ├── vite.config.ts          # ⚡ Vite 构建配置
│   ├── nginx.conf              # 🌐 Nginx 反向代理
│   └── Dockerfile              # 🐳 前端镜像
│
├── electron/                   # 🖥️ Electron 桌面壳
│   ├── src/
│   │   ├── main.ts             # 主进程（Flask 子进程管理）
│   │   └── preload.ts          # 预加载脚本
│   ├── electron-builder.yml    # 打包配置
│   └── package.json
│
├── static/                     # 📦 编译后的前端静态文件
├── templates/                  # 🧩 Flask Jinja2 模板
├── data/                       # 💾 数据存档
├── backups/                    # 💿 数据库备份目录
│
├── docker-compose.yml          # 🐳 Docker 编排
├── Dockerfile                  # 🐳 容器镜像
├── start.bat                   # 🪟 Windows 启动脚本
├── start.sh                    # 🍎 macOS/Linux 启动脚本
│
├── 架构图.md                   # 📐 架构设计文档
├── 更新公告.md                 # 📋 版本迭代记录
└── README.md                   # 📖 本文件
```

---

## 👤 默认账户

| 用户名 | 密码 | 角色 | 权限说明 |
|:---|:---|:---|:---|
| `boss` | `123456` | 👑 Boss | 21 项权限 · 无需审核 |
| `hr` | `123456` | 👔 HR | 18 项权限 · 高级操作需审核 |
| `employee` | `123456` | 👤 Employee | 5 项权限 · 只读查看 |

> ⚠️ **首次登录后请立即修改密码！**

---

## 🗄️ 数据库切换

### SQLite（默认）
零配置，启动即用。数据库文件存储在 `registry.db`。

### MySQL（生产推荐）

```sql
-- 1. 创建数据库和用户
CREATE DATABASE app_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'appuser'@'%' IDENTIFIED BY 'apppass123';
GRANT ALL ON app_db.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
```

```bash
# 2. 创建 backend/.env
DB_ENGINE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=appuser
MYSQL_PASSWORD=apppass123
MYSQL_DATABASE=app_db
```

> 💡 适配器会自动将 SQLite 方言转换为 MySQL 语法（`AUTOINCREMENT → AUTO_INCREMENT`、`TEXT → VARCHAR(255)` 等）。

---

## 📦 打包发布

| 平台 | 命令 | 输出 |
|:---|:---|:---|
| 🪟 Windows | `npm run package:win` | `动态数据登记系统 Setup.exe` |
| 🍎 macOS | `npm run package:mac` | `动态数据登记系统.dmg` |
| 🐧 Linux | `npm run package:linux` | `动态数据登记系统.AppImage` |

---

## 📜 版本历史

| 版本 | 日期 | 类型 | 内容 |
|:---|:---|:---:|:---|
| v0.1-alpha | 07-19 | ✅ | MVP：Flask + SQLite + 原生 HTML，7 种字段，基础 CRUD |
| v0.2-alpha | 07-20 | ✅ | 启动脚本自动检测 Python 环境 |
| v0.3-alpha | 07-20 | ✅ | 自定义颜色面板，localStorage 持久化 |
| v1.0-beta | 07-20 | ✅ | 权限系统：3 角色 + 登录/登出 |
| v1.1-beta | 07-20 | ✅ | 审核机制：pending_changes + 审批流程 |
| v1.2-beta | 07-21 | ✅ | 操作日志全量记录 + 导出 |
| v1.3-beta | 07-21 | 🐛 | 修复登录遮罩不显示 |
| v1.4-beta | 07-21 | ✅ | 桌面化封装：pywebview 独立窗口 |
| v2.0-rc | 07-21 | ✅ | 21 项细粒度权限 + 自定义角色 |
| v2.1-rc | 07-21 | ✅ | 用户管理：增删改 + 权限组合 |
| v2.2-rc | 07-21 | ✅ | ECharts 统计看板 |
| v2.3-rc | 07-22 | 🐛 | 修复字段删除/数据编辑 |
| v2.4-rc | 07-22 | ✅ | 数据库备份恢复 |
| v2.6-rc | 07-22 | ✅ | 用户协议 + 隐私政策 |
| v2.7-rc | 07-22 | ✅ | 全局审核开关（独立控制） |
| v2.8-rc | 07-22 | 🔧 | 字段管理改为表格列表 |
| v2.9-rc | 07-22 | 🔧 | 数据表格折叠 + 惯性滑动 |
| **v3.0** | **07-22** | 🚀 | **正式版：完整功能 + EXE 安装包交付** |
| **v4.0** | **07-27** | 🚀 | **架构重构 + 压测验证 + 开源发布** |
| **v4.1** | **07-27** | 🚀 | **AI 数据分析：多模型对话式智能分析** |
| **v5.0** | **07-28** | 🚀 | **用户体验大升级：侧边栏持久化、AI稳定性修复、安全增强** |

> 📊 **迭代统计**：23 个版本 · 16 项新增 · 2 项修复 · 2 项优化 · 5 天完成 MVP → v5.0

---

## 📢 v4.1 更新公告

> 发布日期：2026 年 7 月 27 日

### 🤖 AI 数据分析

| 功能 | 说明 |
|:---|:---|
| 多模型支持 | **DeepSeek V4** / OpenAI GPT-4o / 通义千问 一键切换 |
| 对话式分析 | 自然语言提问，AI 自动读取数据库并返回智能洞察 |
| 流式输出 | 实时显示 AI 分析过程，无需等待 |
| 连接测试 | 一键验证 API Key 和模型连接状态 |
| 数据安全 | API Key 本地存储，不上传服务器 |

### 🔧 优化

- 前端资源缓存策略优化，解决浏览器缓存导致的 405 报错
- `.gitignore` 排除 `__pycache__`、`*.pyc`、`*.db` 文件
- 后端模块化：新增 `backend/ai_client.py`、`backend/db_crypto.py`

---

## 📢 v5.0 更新公告

> 发布日期：2026 年 7 月 28 日

### 🎯 用户体验升级

| 功能 | 说明 |
|:---|:---|
| 侧边栏状态持久化 | 统计看板、审核中心子菜单默认收起，用户展开后记住状态，下次打开保持 |
| AI 分析结果持久化 | 切换到其他页面再回来，分析报告和对话历史不会丢失（localStorage 持久化） |
| 清除分析按钮 | 新增一键清除 AI 分析结果功能 |

### 🛡️ 安全性增强

| 修复 | 说明 |
|:---|:---|
| API Key 不落盘 | API Key 不再写入 sessionStorage，仅保存在 React 内存中，刷新页面自动清除 |
| 密码输入框保护 | 禁用密码可见性切换按钮 + `autoComplete="new-password"` 防止浏览器干扰 |
| 审计日志补全 | AI 连接测试、AI 分析、AI 对话操作全部写入 `operations_log` 审计表 |

### 🐛 稳定性修复

| 修复 | 说明 |
|:---|:---|
| **AI 分析超时** | 超时时间从 15 秒提升至 3 分钟（`aiClient` 独立 axios 实例），解决 DeepSeek 等模型响应慢导致的分析中断 |
| **AI 看不到字段** | Prompt 中新增字段列表表格（字段名/标签/类型），AI 现在能正确识别所有数据字段 |
| **index.html 缓存** | Flask 改为每次请求动态读取 `index.html`，重启后立即生效，不再需要手动清缓存 |
| **审计日志缺失** | 修复 `/api/ai/*` 三个路由缺少 `g.current_user_id` 导致日志写入静默失败的问题 |

---

## 📢 v4.0 更新公告

> 发布日期：2026 年 7 月 27 日

### 🏗 架构升级

| 项目 | v3.0 | v4.0 |
|:---|:---|:---|
| 前端 | 原生 HTML/CSS/JS | **React 18** + TypeScript |
| 后端架构 | 单体 app.py | **分层架构**（`backend/` 模块化） |
| 数据库 | 仅 SQLite | **双引擎**：SQLite + MySQL（db_adapter 抽象层） |
| 桌面端 | pywebview | **Electron 28**（原生体验 + Node.js 集成） |
| 打包部署 | PyInstaller EXE | **Docker Compose** + PyInstaller + Inno Setup |
| 架构图 | 无 | **7 张 Mermaid 图**（架构 / 时序 / ER / 权限 / 状态机 / 组件树 / 部署） |

### ⚡ 性能验证

- **170 并发用户**，Locust 全场景压测，**0% 失败率**
- 核心 API 平均响应 **< 50ms**，聚合 RPS **39.4**
- 详见 [性能测试](#-性能测试) 板块

### 🔧 工程化提升

- `.env` 环境变量配置管理
- `.gitignore` 版本控制规范
- `check_dbs.py` / `diagnose.py` 诊断工具
- `fix_columns.py` 数据修复脚本
- `locustfile.py` 压力测试脚本
- `Dockerfile` 独立容器化支持
- `docs/assets/` 文档资源目录

### 🌐 开源发布

- GitHub 仓库 `jincheng3870682453-hash/shujuku` 公开
- 专业 README（Mermaid 架构图 + 压测数据 + 完整文档）
- 完整版本历史追溯（v0.1-alpha → v4.0）

---

## 📜 完整版本历史

> 从 MVP 原型到正式开源发布的完整演进之路

### 第一阶段：MVP 探索（v0.1 ~ v0.3）

| 版本 | 日期 | 类型 | 内容 |
|:---|:---|:---:|:---|
| v0.1-alpha | 07-19 | ✅ | Flask 后端 + SQLite + 原生 HTML/CSS/JS，7 种字段类型，基础增删改查，Excel 导出 |
| v0.2-alpha | 07-20 | ✅ | `启动.bat` 自动检测 Python 环境与依赖，自动安装 Flask/openpyxl |
| v0.3-alpha | 07-20 | ✅ | 自定义颜色面板（5 项配色），保存到 localStorage |

### 第二阶段：权限与审核（v1.0 ~ v1.4）

| 版本 | 日期 | 类型 | 内容 |
|:---|:---|:---:|:---|
| v1.0-beta | 07-20 | ✅ | 权限系统：users 表 + 三角色（boss/hr/employee），登录/登出接口 |
| v1.1-beta | 07-20 | ✅ | 审核机制：pending_changes 表，hr 操作进入审核，boss 审核通过/驳回 |
| v1.2-beta | 07-21 | ✅ | 操作日志系统：operation_logs 表，所有操作全记录，支持导出 TXT |
| v1.3-beta | 07-21 | 🐛 | 修复登录遮罩不显示问题（新增 @after_request 强制禁用缓存） |
| v1.4-beta | 07-21 | ✅ | 桌面化封装：pywebview 独立窗口，desktop.py 启动 |

### 第三阶段：功能完善（v2.0 ~ v2.9）

| 版本 | 日期 | 类型 | 内容 |
|:---|:---|:---:|:---|
| v2.0-rc | 07-21 | ✅ | 细粒度权限管理：21 项功能点勾选，自动推荐角色（boss/hr/employee/自定义） |
| v2.1-rc | 07-21 | ✅ | 管理账户功能：增删改用户，自定义用户名/密码/角色/权限组合 |
| v2.2-rc | 07-21 | ✅ | 数据统计看板：ECharts 图表（饼图/柱状图/折线图），按字段统计 |
| v2.3-rc | 07-22 | 🐛 | 修复字段管理删除 404、数据编辑失效、表格单击无反应问题 |
| v2.4-rc | 07-22 | ✅ | 数据库备份恢复：一键导出 .db 文件，拖拽导入恢复 |
| v2.5-rc | 07-22 | ⚠️ | 编码格式报错，回滚至 v2.3-rc，保留所有功能并重新适配编码 |
| v2.6-rc | 07-22 | ✅ | 用户协议 + 隐私政策（2026 版），登录界面默认账户提示移除 |
| v2.7-rc | 07-22 | ✅ | 全局审核开关（每个用户独立），开启后所有操作需审核 |
| v2.8-rc | 07-22 | 🔧 | 字段管理从卡片网格改为表格列表（与数据表格风格统一） |
| v2.9-rc | 07-22 | 🔧 | 数据表格整体折叠功能 + 横向平滑滑动（鼠标拖拽 + 惯性） |

### 第四阶段：正式发布与开源（v3.0 ~ v4.0）

| 版本 | 日期 | 类型 | 内容 |
|:---|:---|:---:|:---|
| **v3.0** | **07-22** | 🚀 | **正式版**：功能全面、UI 统一、PyInstaller + Inno Setup 打包交付（EXE + 安装包） |
| **v4.0** | **07-27** | 🚀 | **架构重构**：React + Electron + 双数据库引擎 + Docker 部署 + 压测验证 + GitHub 开源 |
| **v4.1** | **07-27** | 🚀 | **AI 数据分析**：多模型对话式智能分析（DeepSeek/OpenAI/通义千问） |
| **v5.0** | **07-28** | 🚀 | **UX 大升级**：侧边栏持久化、AI 分析结果持久化、API Key 安全性、超时修复、审计日志补全 |

### ⚠️ v2.5-rc 回滚详情

| 项目 | 内容 |
|:---|:---|
| 回滚范围 | v2.3-rc → v2.5-rc（中间 v2.4-rc 被回滚） |
| 回滚原因 | 编码格式报错（GBK/UTF-8 冲突导致启动脚本无法正常运行） |
| 处理方式 | 全量回退至 v2.3-rc 稳定版本，统一编码为 UTF-8 |
| 回滚后保留 | 细粒度权限、用户管理、统计看板、用户协议、全局审核开关、字段管理表格化、数据表格折叠滑动、Excel/数据库导入导出 |

### 📊 版本迭代总览

```mermaid
timeline
    title 动态数据登记系统 · 版本演进
    07-19 : v0.1-alpha<br/>MVP 原型
    07-20 : v0.2~v0.3<br/>启动脚本 + 自定义配色
          : v1.0~v1.1<br/>权限系统 + 审核机制
    07-21 : v1.2~v1.4<br/>操作日志 + 桌面化
          : v2.0~v2.2<br/>细粒度权限 + 统计看板
    07-22 : v2.3~v2.9<br/>修复完善 + 功能优化
          : v3.0 正式版<br/>EXE + 安装包交付
    07-27 : v4.0 架构重构<br/>React + Electron + Docker + 开源
          : v4.1 AI 数据分析<br/>多模型对话式智能分析
    07-28 : v5.0 UX 大升级<br/>持久化 + 安全 + 稳定性修复
```

| 指标 | 数值 |
|:---|:---:|
| 总版本数 | **23** |
| 新增功能 | **16** |
| 修复问题 | **2** |
| 优化改进 | **2** |
| 回滚操作 | **1** |
| 开发周期 | 2026-07-19 ~ 2026-07-28（10 天） |
| 阶段跨度 | alpha → beta → rc → 正式版 → 架构重构 → AI 增强 → UX 升级 |

> 📅 **最后更新**：2026-07-28 &nbsp;&nbsp;|&nbsp;&nbsp; 🏷️ **当前版本**：v5.0

---

## 📄 用户协议

> 最后更新日期：2026 年 7 月 27 日

欢迎使用「动态数据登记系统」（以下简称"本软件"）。安装、复制或使用本软件即表示您同意接受本协议所有条款的约束。如不同意，请勿使用。

### 一、许可授权

授予您非独占、不可转让的免费使用许可。可用于个人或商业场景。本许可是使用权许可，而非所有权出售。

### 二、使用限制

禁止将本软件用于违法活动，包括但不限于：

- 存储、传播违法信息
- 侵犯他人知识产权或隐私权
- 实施欺诈、诈骗等犯罪行为
- 反向工程、反编译或提取源代码（公开的源码除外）
- 将本软件或修改版本作为独立产品再分发销售

### 三、知识产权

本软件全部知识产权归开发者所有，受《中华人民共和国著作权法》等法律保护。用户产生的业务数据归用户所有，开发者不主张任何权利。

### 四、数据安全

- 所有数据存储在用户本地设备中，开发者不收集、不上传、不存储
- 用户对数据的完整性、安全性和合规性承担全部责任
- 建议定期备份数据、设置设备密码、防范恶意软件

### 五、免责声明

本软件按"现状"提供，不提供任何明示或默示担保。开发者不对使用本软件产生的任何直接、间接、附带或后果性损失承担责任。用户使用本软件即视为接受本免责声明。

### 六、责任限制

在法律允许的最大范围内，开发者不对数据丢失、业务中断、利润损失等承担责任。

### 七、赔偿

您同意就因违反本协议导致第三方索赔而使我方遭受的损失进行赔偿。

### 八、软件更新

开发者保留随时更新或停止维护的权利，但不会主动删除用户已安装版本。本协议适用于所有版本，除非新版本附带单独协议。

### 九、协议终止

您可随时卸载并删除本软件以终止协议。违反协议时，开发者有权终止协议并要求您停止使用。

### 十、协议修改

开发者保留修改本协议的权利，修改后将在软件中公示。继续使用即视为接受修改后的协议。

### 十一、法律适用

本协议适用中华人民共和国法律。争议先通过友好协商解决，协商不成可向开发者所在地有管辖权的人民法院提起诉讼。

### 十二、联系方式

请通过 [GitHub Issues](https://github.com/jincheng3870682453-hash/shujuku/issues) 提交反馈，或在软件设置页面联系我们。

---

## 🔒 隐私政策

> 最后更新日期：2026 年 7 月 27 日

动态数据登记系统（以下简称"本软件"）由个人开发者开发并发布。我们深知个人信息对您的重要性，承诺严格遵守《中华人民共和国个人信息保护法》《中华人民共和国数据安全法》等相关法律法规。

### 一、我们不收集任何信息

本软件完全运行于您的本地设备，**不会主动收集、上传或存储您的任何个人数据**。您录入的全部数据仅存储在本地设备中，我们无法访问或获取。

### 二、Cookie 与本地存储

- 本软件为桌面应用，不使用浏览器 Cookie 追踪技术
- 如通过浏览器访问 Web 界面，localStorage 仅用于存储登录凭证和界面偏好，数据不会上传至远程服务器

### 三、数据存储与保护

| 措施 | 说明 |
|:---|:---|
| 存储位置 | 所有数据存储在本地 SQLite / MySQL 数据库文件中 |
| 密码保护 | 账户密码使用 **PBKDF2-SHA256** 加盐哈希算法处理 |
| 网络隔离 | 软件不设置任何远程访问通道或后门接口 |
| 设备安全 | 您应对自身设备安全负责（建议设置设备密码、启用防火墙、安装杀毒软件） |

### 四、网络通信

核心功能**无需联网**。仅在您主动点击"检查更新"或使用特定扩展功能时发起网络请求，且不传输任何个人数据。

### 五、第三方服务

本软件**不集成**任何第三方 SDK、追踪代码、广告组件或分析工具。我们不会将您的数据出售、出租或披露给任何第三方。

### 六、您的权利

您对数据拥有**完全控制权**：

- ✅ 随时查阅、修改、导出、备份或删除数据
- ✅ 一键导出 Excel 格式备份
- ✅ 完整数据库文件备份与恢复
- 💡 建议定期备份数据库文件，以防意外丢失

### 七、未成年人保护

本软件不专门面向未成年人。未成年人应在监护人陪同下使用。

### 八、政策更新

本隐私政策可能适时调整，更新内容将在软件中公示。继续使用即视为接受更新后的政策。

### 九、联系方式

请通过 [GitHub Issues](https://github.com/jincheng3870682453-hash/shujuku/issues) 提交隐私相关反馈，或在软件设置页面联系我们。

### 十、法律适用

本隐私政策适用中华人民共和国法律。如有争议，先友好协商，协商不成可向开发者所在地有管辖权的人民法院提起诉讼。

---

## ❓ 常见问题

<details>
<summary><b>Q: 启动报 ModuleNotFoundError</b></summary>

```bash
pip install -r requirements.txt && pip install -r backend/requirements.txt
```
</details>

<details>
<summary><b>Q: 前端页面白屏</b></summary>

检查浏览器控制台 CORS 错误，确认后端运行在 5001 端口。
</details>

<details>
<summary><b>Q: Electron 显示"后端无响应"</b></summary>

确认 Python 已安装并加入 PATH，5001 端口未被占用。
</details>

<details>
<summary><b>Q: MySQL 连接失败</b></summary>

确认 MySQL 服务运行中，用户密码正确，防火墙放行 3306。可在系统设置中点击"测试连接"。
</details>

<details>
<summary><b>Q: Docker 启动失败</b></summary>

检查 3306 / 5001 / 80 端口是否被占用，修改 `docker-compose.yml` 端口映射。
</details>

<details>
<summary><b>Q: Excel 导入字段不匹配</b></summary>

系统会自动检测表头并创建字段。确保 Excel 第一行为列名，系统会自动跳过标题行。
</details>

<details>
<summary><b>Q: macOS 运行 .app 被拦截</b></summary>

系统设置 → 隐私与安全 → 点击"仍要打开"。
</details>

---

## 📄 License

MIT License · Copyright (c) 2026 Jincheng3870682453-hash

---

<p align="center">
  <sub>Built with ❤️ using Flask + React + Electron</sub>
</p>
