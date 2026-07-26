# 动态数据登记系统 - 项目记忆

## 技术栈
- 后端：Flask + Waitress，app.py（~1550 行）
- 前端：React (Vite)，frontend/ 目录
- 数据库抽象：backend/db_adapter.py，同时支持 SQLite 和 MySQL
- 桌面端：PyInstaller / Electron / pywebview
- 部署：Docker Compose

## 已完成的优化（2025-07-25）
1. 密码哈希：从 SHA-256 无盐升级为 PBKDF2-SHA256（werkzeug），向后兼容旧密码，登录时自动升级
2. 抽取 `convert_field_value()` 共享函数 + `FIELD_TYPE_MAP` 常量，消除 4 处重复类型转换代码
3. 修复 Excel 导入的深层嵌套三元表达式，改为调用 convert_field_value
4. 审核列表 API 自动过滤 add_user/update_user 密码明文（已增强：同时过滤 old_value/new_value，覆盖 password/password_hash/new_password/old_password/confirm_password 等敏感键）
5. 备份功能修复：POST /api/backup 实际复制数据库文件到 backups/db_backups/，下载和删除也同步操作文件
6. 数据权限过滤：新增 `_created_by` 系统列，非 boss 角色只能查看/编辑/删除自己创建的数据行，boss 不受限制

## 登录修复（2025-07-25）
- `main.tsx`：添加 `<App>` 包裹 `<RouterProvider>`，修复 Ant Design 5 中 `App.useApp()` 需要上层 `<App>` 提供 context
- `api/client.ts`：移除 `if (isElectron)` 条件，浏览器和 Electron 环境都发送 `Authorization: Bearer` header，确保 Flask `before_request` 能恢复 session（之前浏览器模式下不发送 token header，session cookie 经过 Vite proxy 丢失后无法恢复）
- `api/auth.ts`：新建文件，包含 login/me/logout 三个 API 方法
- `api/audit.ts`：新增 `getCount()` 方法
- `Login.tsx`：修复 `res.data.token` → `res.token`（axios 拦截器已解包 `response.data`）
- `AppLayout.tsx`：修复 `setUser(res.data)` → 正确映射 `res.user_id/username/role`；修复菜单 key `/data` → `/database`
- `router/index.tsx`：新建路由文件（Login / AuthGuard 包裹 AppLayout 子路由）

## UI 视觉重构（2025-07-25）
对标 Linear「午夜精密仪器」暗色设计系统，全局视觉重构：
- `tokens.css`：74 个设计 token（表面层级 void→carbon→obsidian→graphite→smoke，品牌色 #5e6ad2，4px 栅格）
- `theme.ts`：Ant Design 5 暗色主题完整覆盖 30+ 组件（Layout/Menu/Table/Card/Button/Input/Modal 等）
- `index.css`：全局样式 + Ant Design 组件表层覆写 + 工具类（card-surface/panel-inset/stats-grid/stat-card/page-wrapper）
- `Login.tsx`：极简暗色认证页，居中卡片 + 径向渐变背景 + 品牌色 Logo
- `AppLayout.tsx`：侧边导航 + 顶栏 + 用户 Dropdown，折叠/展开切换
- `DataTable.tsx`：暗色表格（去边框/悬停行/深色 footer）+ 顶部统计卡片
- `Stats.tsx`：从全屏 Modal 改为正常路由页面，自绘柱状图（列填充率 + 分类分布），4 个指标卡片

## 注意事项
- 项目自带了 `backend/__init__.py` 的 import hook 机制，禁止直接 import sqlite3/pymysql
- `启动.bat` 为 Windows 专用启动脚本
- 默认账户见 `默认账户说明.txt`
