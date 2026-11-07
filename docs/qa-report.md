# QA 报告 — macOS 适配 · UI 偏移 · 前后端接口对照

日期：2026-11-07 · 范围：electron/src/main.ts、frontend/src、docs/（本文件）
验证：`cd frontend && npx tsc --noEmit` ✅ 干净；`cd electron && npx tsc -p tsconfig.json --noEmit` ✅ 干净。
铁律遵守：未触碰 backend/**、app.py、.github/**、electron-builder.yml、README*、requirements.txt。

## 一、已修复

### Electron（electron/src/main.ts）
- E1 `[P0]` main.ts:27-33（原 14-15）开发模式 app_py 路径多一层 `..`。
  `dist/main.js → electron/ → 项目根` 只需两级，原 `../../..` 解析到磁盘根，
  开发模式必报「未找到后端入口文件」。改为 `'..', '..'`。
- E2 `[P0]` main.ts:101-140（新增 getBackendEnv）macOS 启动 Flask 子进程 PATH 缺失。
  从 Finder/Dock 启动的 GUI 应用 PATH 仅 `/usr/bin:/bin:...`，Homebrew python3
  （/opt/homebrew/bin · Apple Silicon / /usr/local/bin · Intel）不在其中，
  `spawn('python3')` 直接 ENOENT。启动前把 4 个常见目录追加到 PATH（去重，非覆盖）；
  Windows 分支原样返回，无行为变化。
- E3 `[P0]` main.ts:143-165、175-186（新增 prepareMacRuntimeDir + startBackend 钉库路径）
  mac 打包后 resourcesPath 位于 /Applications 下，普通用户只读且升级整体替换。app.py 以
  app.py 所在目录为根做三类写操作：
  ① import 期无条件 `makedirs(<目录>/backups/db_backups)`（app.py:58）→ 只读直接崩；
  ② SQLite 实际落点由 backend/config.py `SQLITE_PATH="./data/app.db"` 按 cwd 相对解析
     （backend/db_adapter.py:956 `get_adapter()` 用的是它，不吃 REGISTRY_DB_PATH）；
  ③ 语义索引 `_VS_INDEX_PATH=<base>/data/vecsearch_index.json`（app.py:1775）、
     同步包（app.py:1884，可用 REGISTRY_SYNC_DIR 环境变量兜底）、备份（app.py:57-58）。
  修复（main.ts 单侧最小可行）：
  - 打包+darwin 时把 app.py / backend / static / requirements.txt 镜像到
    `app.getPath('userData')/runtime/`（每次启动重建，保证与安装版本一致；data/ 仅首次
    播种，不覆盖用户已有 app.db），Flask cwd 指向该镜像目录；
  - 打包模式下给子进程显式设置 `SQLITE_PATH` 与 `REGISTRY_DB_PATH` →
    `userData/data/app.db`（可写、升级保留）。两者都要设：前者管真实落库，
    后者管 app.py 的备份/恢复路径（app.py:36-66）。
- E4 `[P1]` main.ts:222-234 window-all-closed 在 darwin 分支误杀后端。
  原代码无条件 `backendProcess.kill()`——mac 惯例关窗不退出，用户点 Dock 图标走
  `activate` 重建窗口（main.ts:236-238）时后端已死，页面必然白屏。改为仅非 darwin
  清理并退出；后端生命周期收敛到「app 启动 / before-quit」两处。
- E5 `[P2]`（确认，无需改）resourcesPath 布局正确：extraResources 平铺
  （electron-builder.yml:12-32），`resourcesPath/app.py`、`icon.icns`、`data/`、`static/`
  均对得上；E3 的镜像源路径据此书写。
- E6 `[P2]`（确认，无遗漏）Cmd+Q：应用菜单 `role: 'quit'`（main.ts:189）→ before-quit
  kill 后端（main.ts:241-247），闭环正确。菜单含关于/服务/隐藏/编辑/视图/窗口，符合 HIG。

### 前端（frontend/src）
- F1 `[P3]` AppLayout.tsx:398-412（现 397-419）顶栏面包屑无 flex 收缩能力：3 个
  `whiteSpace: nowrap` 子元素 + 固定 240px 搜索框，窗宽 <~1000px（即设计最小宽 1024 的
  折叠态附近）时面包屑把「待审核/用户区」挤出视口。给面包屑容器加
  `flex: 1 1 auto; overflow: hidden`，两段文本加 ellipsis；搜索框/待审核/用户区加
  `flexShrink: 0`，窄窗由面包屑单点收缩。纯布局修复，无行为改动。

## 二、风险待确认（不臆改，需 Lead/后端决策）

- R1 `[P0·后端]` app.py:58 `os.makedirs(BACKUP_DIR, ...)` 在 import 期无条件执行，
  BACKUP_DIR 固定在 `<app.py 目录>/backups/db_backups`，且无环境变量出口（SQLITE_PATH/
  REGISTRY_DB_PATH/REGISTRY_SYNC_DIR 均管不到它）。E3 的镜像方案已绕开（镜像目录可写），
  但更根本的修法是后端把 BACKUP_DIR 也改成环境变量可配（如 REGISTRY_BACKUP_DIR），
  避免「把整个 backend+app.py 拷进 userData」的镜像开销。**本次未动 app.py（铁律），仅记录。**
- R2 `[P1·数据迁移]` mac dmg 是首版：`userData/data/app.db` 从零开始，无历史用户数据
  迁移问题。但 Windows NSIS 版目前仍走 cwd/data（安装目录可写），两平台数据库文件位置
  不一致；若后续 Windows 也收紧到 Program Files 只读安装，需要同样的环境变量方案。
- R3 `[P1·签名]` electron-builder.yml:64 `identity: null` 跳过签名。macOS Gatekeeper 对
  未签名 + 未公证的 dmg：用户需右键打开或 `xattr -cr`，且 Arm64 macOS 对未签名二进制
  **直接拒绝运行**（Electron 二进制本身有adhoc签名可运行，但 python3 子进程若来自
  Homebrew 属于用户已装软件，不受影响）。建议出 dmg 前确认分发策略（adhoc 签名 +
  README 指导，或上 Apple Developer 证书）。
- R4 `[P2·权限]` app.py:1605 备份创建要求 `export_excel` 权限，而非独立 backup 权限；
  员工角色默认无此权限，备份管理页对员工不可用——若产品预期「员工可备份」需后端确认
  权限点是否故意复用。
- R5 `[P2·壳]` main.ts:109 加载 `http://127.0.0.1:5001/`，后端实际监听 `0.0.0.0:5001`
  （app.py:2519 waitress）。本机回环可达，功能无碍；但 0.0.0.0 意味着局域网内其他设备
  可直接访问该数据系统（无防火墙时）。若非产品预期，建议后端改绑 127.0.0.1。
- R6 `[P3·视觉]` 「暗色质感下白底弹层」为已知遗留：textures.css 仅覆写 L1 变量，
  AntD 弹层（Modal/Select 下拉/Tooltip）挂在 body 下、取 token 默认白底（theme.ts:61
  colorBgBase: white），data-texture 切换不会跟随。涉及 theme 体系调整，超出「明显 UI
  偏移」范围，待设计决策。
- R7 `[P3·API]` `/api/logs` 仅消费 `keyword`，前端 logs.ts:6-14 还传 username/action/
  start_date/end_date（后端 app.py:1324-1337 未实现，静默忽略=筛选不生效）。
  属功能缺口非偏移，待后端确认是否补齐。
- R8 `[P3·API]` `/api/users` PUT 的 username 后端不消费（app.py:1709 读取但更新不含改名），
  前端编辑弹窗用户名输入框 disabled，行为一致无 bug；仅提示后端该变量为死代码。

## 三、不修（理由）

- N1 `frontend/src/api/columns.ts` 与 `data.ts` 的 getColumns 映射逻辑完全重复（71 行 vs
  73 行同一段代码）——重构属于风格改动，超出本次授权范围。
- N2 `frontend/src/pages/Audit.tsx:139-157` 用 `client.get('/me')` 再查一次角色，与
  AppLayout 的 useRole 并行——行为正确，仅多余请求，不做行为改动。
- N3 DataTable.tsx:547-558 主表「操作」列 width 80，footer 新增行表「操作」列 width 120
  且两表独立渲染（主表 scroll.x=max-content / 新增行表无 scroll）——列对齐在窄列多时
  可能错位。但「修对齐」需要把新增行并入主表 dataSource 或同步列宽状态，属行为改动，
  待确认后再做（当前列少时表现正常）。
- N4 `.gradient-bg` 类 6 处引用（Users.tsx:375、Settings.tsx:654/1135、Backup.tsx:131、
  Columns.tsx:295/412）但全项目无定义——按钮实际呈 AntD primary 默认样式，无视觉破损
  （border:none 行内样式已覆盖）。死类清理属风格重构，不修。
- N5 滚动条样式（index.css:33-41）已用 -webkit-scrollbar 自定义，macOS overlay 滚动条
  场景下兼容；无需追加 NSDefaultControlAttrs 处理。
- N6 `-webkit-app-region`：mac 用系统标题栏（main.ts 未设 frame:false、titleBarStyle 默认），
  无拖拽区冲突；前端亦无 app-region 代码。无需处理。
- N7 中文字体栈已含 PingFang SC / Hiragino Sans GB / -apple-system
  （tokens.css:133-135、theme.ts:64-66），mac 渲染无缺字风险。无需处理。

## 四、接口对照结论（任务 C）

前端 api/*.ts + 页面内直连调用（共 39+8 处）与 app.py 路由 method+path 逐一比对：
全部命中，无 404 路由。参数级核对（重点近期改动项）：
- `/api/rows` GET：page/pageSize ✅（app.py:879-880）；响应带 updated_at ✅（app.py:892）
- `/api/rows/<id>` PUT：`base_updated_at` 透传 ✅（DataTable.tsx:371-372 → app.py:989）；
  409 冲突处理 ✅（DataTable.tsx:339-343）
- `/api/audit` GET status(page/pageSize) ✅（app.py:1111-1113，pending→待审核映射 ✅）
- `/api/audit/<id>/approve|reject`：body `comment` ✅（app.py:1319 reject 用 comment；
  approve 忽略 comment，无害）
- `/api/users/<uid>` PUT：username/role/permissions/audit_enabled/password ✅（app.py:1708-1733）
- `/api/search/semantic`、`/api/sync/*`：前端暂无调用（grep 证实），无错配面；参数级差异见 R7、R8，均不致错。

## 五、修改文件清单

| 文件 | 改动 |
| --- | --- |
| electron/src/main.ts | E1-E4（净 +56 行） |
| frontend/src/components/AppLayout.tsx | F1（面包屑 flex + 3 处 flexShrink） |
| docs/qa-report.md | 本报告（新建） |

## 安全加固 — 备份链路（2026-11-07 第二轮）

范围：app.py 备份三端点、backend/db_adapter.py 新增校验器。回归：pytest 223 passed / 7 skipped。

### 修复项

| 级别 | 问题 | 修复 |
|---|---|---|
| P0 | `/api/backup/restore` 无校验直接覆盖生产库，传坏文件即毁库 | 三道防线：SQLite magic 头校验 → `validate_sqlite_file()`（integrity_check + users 表存在性）→ 同目录暂存 + `os.replace` 原子替换；替换前自动快照现库可回滚；任何校验失败不触碰现库 |
| P1 | download/delete 的 `filename` 直接拼路径，`../../` 可穿越读/删任意文件 | `_safe_backup_path()`：拒绝分隔符/`..`/basename 不符，`commonpath` 兜底，非法一律 404 |
| P1 | 下载/删除不记审计日志 | 两端点补 `operations_log` 记录（动作/目标/操作者） |
| P2 | Windows 下载后立即删除撞 WinError 32 | download 改 BytesIO（读完即释句柄）+ delete 端 `PermissionError` 重试 3 次 |
| P2 | 前端 hrPermissions 缺 `backup_data`，编辑保存会抹掉 hr 的备份权限 | `Users.tsx` hr 默认权限补齐 |

### 架构合规

SQLite 校验器放 `db_adapter.validate_sqlite_file()`（backend 白名单层），业务层 app.py 不直连 sqlite3，遵守 backend/__init__.py 的导入护栏。

### 验证证据（Flask test client 实测）

1. 坏文件（非 SQLite）恢复 → 400「不是有效的 SQLite 数据库文件」，现库字节级未变
2. 合法 SQLite 但缺 users 表 → 400「不是本系统的数据库」，现库未变
3. 完整库恢复 → 200，operations_log 出现「恢复数据库备份 / boss」
4. `..%2F..%2Fwin.ini` 等穿越下载 → 404
5. 下载→删除闭环 → 均记「下载备份」「删除备份」日志
