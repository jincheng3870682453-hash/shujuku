# 动态数据登记系统

> 基于 Flask + React + Electron 的桌面/Web 一体化数据管理系统

## ✨ 功能特性

- 🔐 用户认证与权限管理（Boss / HR / Employee 三级角色 + 细粒度功能权限）
- 📊 动态数据表格（行内编辑、分页、搜索、排序、自定义字段）
- 🎨 紫色渐变毛玻璃主题（Ant Design + TailwindCSS）
- 🗄️ 双数据库引擎（SQLite / MySQL 无缝切换）
- 📈 统计看板（ECharts 数据可视化）
- ✅ 审核工作流（新增/修改/删除需 Boss 审批）
- 📝 操作日志审计
- 💾 数据备份与恢复（Excel 导入/导出）
- 🖥️ Electron 桌面应用（Windows / macOS / Linux）

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | React 18 + TypeScript |
| UI 组件库 | Ant Design 5.x |
| 样式方案 | TailwindCSS + CSS Modules |
| 状态管理 | Zustand |
| 数据请求 | TanStack Query (React Query) |
| 图表 | ECharts |
| 路由 | React Router v6 |
| 后端框架 | Python Flask |
| 数据库 | SQLite / MySQL（双引擎适配层） |
| 桌面壳 | Electron 28 |
| 打包工具 | electron-builder |
| 容器化 | Docker + docker-compose |

## 🚀 快速开始

### 方式一：脚本启动（推荐新手）

#### Windows
双击 `start.bat`，按提示操作。

#### macOS / Linux
```bash
chmod +x start.sh
./start.sh
```

### 方式二：Docker 启动（推荐生产环境）

```bash
# 1. 配置环境变量（可选）
cp .env.example .env
# 编辑 .env 修改数据库密码等

# 2. 一键启动
docker-compose up -d

# 3. 查看日志
docker-compose logs -f backend

# 4. 访问应用
# 浏览器打开 http://localhost
```

### 方式三：开发模式手动启动

#### 后端
```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
python app.py
# 后端运行在 http://localhost:5001
```

#### 前端
```bash
cd frontend
npm install
npm run dev
# 前端运行在 http://localhost:3000（自动代理 API 到 5001）
```

#### Electron 桌面版
```bash
# 先启动后端，再运行：
cd electron
npm install
npx tsc
npx electron dist/main.js
```

## 🗄️ 数据库切换

### SQLite（默认）
无需任何配置，启动即用。数据存储在项目根目录 `registry.db`。

### MySQL
1. 安装 MySQL 8.0+ 并启动服务
2. 创建数据库和用户：
```sql
CREATE DATABASE app_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'appuser'@'%' IDENTIFIED BY 'apppass123';
GRANT ALL ON app_db.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
```
3. 创建 `backend/.env`：
```
DB_ENGINE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=appuser
MYSQL_PASSWORD=apppass123
MYSQL_DATABASE=app_db
```
4. 重启应用，适配器会自动使用 MySQL。

## 👤 默认账户

| 用户名 | 密码 | 角色 | 权限说明 |
|--------|------|------|----------|
| boss | 123456 | Boss | 全部权限 |
| hr | 123456 | HR | 数据管理 + 审核 + 查看统计 |
| employee | 123456 | Employee | 只读查看 + 搜索 |

> ⚠️ 首次登录后建议立即修改密码。

## 📦 打包发布

### Windows 安装包
```bash
cd electron
npm run package:win
# 输出：electron/dist/动态数据登记系统 Setup.exe
```

### macOS DMG
```bash
cd electron
npm run package:mac
# 输出：electron/dist/动态数据登记系统.dmg
```

### Linux AppImage
```bash
cd electron
npm run package:linux
# 输出：electron/dist/动态数据登记系统.AppImage
```

## 🔧 常见问题排查

### Q: 启动时报 `ModuleNotFoundError: No module named 'flask'`
A: Python 依赖未安装，运行 `pip install -r requirements.txt && pip install -r backend/requirements.txt`

### Q: 前端页面白屏
A: 检查浏览器控制台是否有 CORS 错误，确认后端服务在 5001 端口运行

### Q: Electron 启动后显示"后端无响应"
A: 检查 Python 是否安装，运行 `python --version` 确认；检查 5001 端口是否被占用

### Q: MySQL 连接失败
A: 确认 MySQL 服务运行正常，用户名密码正确，防火墙放行 3306 端口

### Q: Docker 启动失败
A: 检查 3306/5001/80 端口是否被占用，修改 `docker-compose.yml` 中的端口映射

### Q: Windows 下 spawn python 报错
A: 确保 Python 已添加到系统 PATH 环境变量

### Q: macOS 首次运行 .app 被拦截
A: 系统设置 → 隐私与安全 → 允许运行

## 📁 项目结构

```
project/
├── app.py                    # Flask 后端主入口
├── run.py                    # 开发启动脚本
├── requirements.txt          # 根级 Python 依赖
├── backend/                  # Flask 后端模块
│   ├── __init__.py          # 包初始化 + sqlite3/pymysql 导入防护
│   ├── config.py            # 配置管理（.env 读取）
│   ├── db_adapter.py        # 数据库适配层（SQLite/MySQL 双引擎）
│   ├── test_adapter.py      # 适配器单元测试
│   ├── requirements.txt     # 后端 Python 依赖
│   └── .env.example         # 后端环境变量示例
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── api/             # API 客户端（支持 Electron 环境检测）
│   │   ├── components/      # 公共组件（AppLayout, EditableCell 等）
│   │   ├── pages/           # 页面组件（Login, DataTable, PlaceholderPage）
│   │   ├── stores/          # Zustand 状态管理
│   │   ├── styles/          # 主题配置
│   │   ├── types/           # TypeScript 类型定义
│   │   └── router/          # 路由配置
│   ├── package.json
│   ├── vite.config.ts       # Vite 构建配置
│   ├── nginx.conf           # Nginx 反向代理配置
│   ├── Dockerfile           # 前端 Docker 镜像
│   ├── .env.development     # 开发环境变量
│   └── .env.production      # 生产环境变量
├── electron/                 # Electron 桌面壳
│   ├── src/
│   │   ├── main.ts          # 主进程（管理 Flask 子进程 + BrowserWindow）
│   │   └── preload.ts       # 预加载脚本
│   ├── electron-builder.yml # 打包配置
│   └── package.json
├── templates/                # Flask Jinja2 模板
│   └── index.html
├── static/                   # 静态资源
│   └── style.css
├── docker-compose.yml        # Docker 编排
├── start.bat                 # Windows 启动脚本
├── start.sh                  # macOS/Linux 启动脚本
├── .env.example              # 环境变量示例
└── README.md
```

## 📄 License

MIT License