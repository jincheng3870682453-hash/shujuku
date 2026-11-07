import { app, BrowserWindow, ipcMain, shell, dialog, Menu } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import fs from 'fs';
import http from 'http';

let backendProcess: ChildProcess | null = null;

/** 获取 app.py 的绝对路径（开发模式 vs 打包模式） */
function getAppPyPath(): string {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'app.py');
  }
  // 开发模式：electron/dist/main.js -> electron/ -> 项目根（此前多写一层 '..'，
  // 会把项目根错误解析到磁盘根目录，导致开发模式启动即报「未找到后端入口文件」）
  return path.join(__dirname, '..', '..', 'app.py');
}

/**
 * macOS 从 Finder/Dock 启动的 GUI 应用 PATH 极简（通常只有 /usr/bin:/bin:/usr/sbin:/sbin），
 * 而 Homebrew 的 python3 在 /opt/homebrew/bin（Apple Silicon）或 /usr/local/bin（Intel），
 * 不在其中，spawn('python3') 会直接 ENOENT。启动后端前把常见安装目录补进 PATH。
 * Windows 的 GUI 进程继承资源管理器/安装器的完整 PATH，无需处理。
 */
function getBackendEnv(): NodeJS.ProcessEnv {
  if (process.platform !== 'darwin') {
    return { ...process.env };
  }
  const extra = ['/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin'];
  const current = process.env.PATH || '';
  const missing = extra.filter((p) => !current.split(':').includes(p));
  return { ...process.env, PATH: [...missing, current].filter(Boolean).join(':') };
}

/**
 * macOS 打包后 resourcesPath 位于 /Applications 下，对普通用户只读，且升级会被整体替换。
 * 而 app.py 以自身目录为根做三类写操作：
 *   1) import 期无条件 makedirs(<app.py 目录>/backups/db_backups)（app.py:58）——只读直接崩；
 *   2) SQLite 落点按 cwd 相对解析 ./data/app.db（backend/config.py 默认值）；
 *   3) 语义索引 / 同步包 / 备份也写到 <app.py 目录>/data 与 backups。
 * 因此在打包+macOS 时，把运行所需文件镜像到 userData/runtime（可写、升级保留）再启动。
 * 镜像每次启动重建以保证与安装版本一致；data/ 仅首次播种（app.db 不存在时），
 * 避免覆盖用户已有数据库。
 */
function prepareMacRuntimeDir(): string {
  const userData = app.getPath('userData');
  const runtimeDir = path.join(userData, 'runtime');
  fs.mkdirSync(runtimeDir, { recursive: true });

  const resources = process.resourcesPath;
  const seedSrc = path.join(resources, 'data');
  const seedDst = path.join(runtimeDir, 'data');
  if (fs.existsSync(seedSrc) && !fs.existsSync(path.join(seedDst, 'app.db'))) {
    fs.cpSync(seedSrc, seedDst, { recursive: true });
  }

  for (const name of ['app.py', 'backend', 'static', 'requirements.txt']) {
    const src = path.join(resources, name);
    if (!fs.existsSync(src)) continue;
    const dst = path.join(runtimeDir, name);
    fs.rmSync(dst, { recursive: true, force: true });
    fs.cpSync(src, dst, { recursive: true });
  }
  return runtimeDir;
}

/** 获取 Python 解释器命令（源码回退模式用） */
function getPythonCommand(): string {
  if (process.platform === 'win32') {
    return 'python';
  }
  return 'python3';
}

/**
 * 解析后端运行时：零依赖 exe 优先，系统 Python 回退。
 *  - exe   ：PyInstaller onedir 产物（resources/backend_server/backend_server[.exe]），
 *           由 CI 打进安装包——用户机器无需任何 Python 环境；
 *  - python：源码回退（开发模式 / 未打包 exe 的旧安装包），
 *           走 app.py + 系统 python3，mac 需 prepareMacRuntimeDir 镜像。
 */
function getBackendRuntime(): { kind: 'exe'; exePath: string } | { kind: 'python'; appPyPath: string | null } {
  const exeName = process.platform === 'win32' ? 'backend_server.exe' : 'backend_server';
  const exePath = path.join(process.resourcesPath, 'backend_server', exeName);
  if (app.isPackaged && fs.existsSync(exePath)) {
    return { kind: 'exe', exePath };
  }
  // 回退：定位源码 app.py（打包态 darwin 用 userData/runtime 镜像，见 prepareMacRuntimeDir）
  const runtimeDir = app.isPackaged && process.platform === 'darwin'
    ? prepareMacRuntimeDir()
    : null;
  const appPyPath = runtimeDir
    ? path.join(runtimeDir, 'app.py')
    : getAppPyPath();
  return { kind: 'python', appPyPath: fs.existsSync(appPyPath) ? appPyPath : null };
}

/** 启动 Flask 后端并等待其就绪 */
function startBackend(): Promise<void> {
  return new Promise((resolve, reject) => {

    // SQLITE_PATH：backend/db_adapter 实际落库依据（相对路径按 cwd 解析到 cwd/data/app.db）；
    // REGISTRY_DB_PATH：app.py 的 DATABASE_PATH / _get_real_db_path 依据（备份、恢复用它）。
    // 两者都显式钉到 userData，彻底避免只读目录与版本升级丢数据。
    const dbPath = app.isPackaged
      ? path.join(app.getPath('userData'), 'data', 'app.db')
      : null;
    if (dbPath) {
      fs.mkdirSync(path.dirname(dbPath), { recursive: true });
    }
    // 可写数据根：备份/上传/检索索引/同步包/崩溃日志统一锚定（app.py frozen 态读 REGISTRY_DATA_DIR）
    const dataRoot = app.isPackaged ? app.getPath('userData') : null;

    const runtime = getBackendRuntime();
    let spawnCmd: string;
    let spawnArgs: string[];
    let cwd: string;
    if (runtime.kind === 'exe') {
      // 零依赖模式：PyInstaller onedir，用户机器无需 Python
      spawnCmd = runtime.exePath;
      spawnArgs = [];
      cwd = path.dirname(runtime.exePath);
      console.log('[Electron] 后端运行时: 零依赖 exe (PyInstaller)');
    } else {
      if (!runtime.appPyPath) {
        reject(new Error('未找到后端入口: 既无零依赖 backend_server，也无源码 app.py。\n请重新安装或检查安装完整性。'));
        return;
      }
      spawnCmd = getPythonCommand();
      spawnArgs = [runtime.appPyPath];
      cwd = path.dirname(runtime.appPyPath);
      console.log(`[Electron] 后端运行时: 系统 Python (${spawnCmd})，源码回退模式`);
    }

    const env: NodeJS.ProcessEnv = {
      ...getBackendEnv(),
      ...(dbPath ? { SQLITE_PATH: dbPath, REGISTRY_DB_PATH: dbPath } : {}),
      ...(dataRoot ? { REGISTRY_DATA_DIR: dataRoot } : {}),
      // 桌面模式：app.py 据此只绑 127.0.0.1（不暴露局域网）
      REGISTRY_RUN_MODE: 'desktop',
    };

    console.log(`[Electron] 启动后端: ${spawnCmd} ${spawnArgs.join(' ')}`);
    console.log(`[Electron] 工作目录: ${cwd}`);

    backendProcess = spawn(spawnCmd, spawnArgs, {
      cwd,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      detached: false,
    });

    backendProcess.stdout?.on('data', (data) => {
      console.log(`[Flask] ${data.toString().trim()}`);
    });

    backendProcess.stderr?.on('data', (data) => {
      console.error(`[Flask] ${data.toString().trim()}`);
    });

    backendProcess.on('error', (err) => {
      reject(new Error(`启动 Flask 失败: ${err.message}\n请确认系统已安装 Python 及依赖 (pip install -r requirements.txt)。`));
    });

    backendProcess.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        console.error(`[Electron] Flask 进程退出，退出码: ${code}`);
      }
    });

    // 轮询等待后端就绪
    let attempts = 0;
    const maxAttempts = 60; // 最多 60 秒
    const checkReady = () => {
      attempts += 1;
      const req = http.get('http://127.0.0.1:5001/', (res) => {
        if (res.statusCode && res.statusCode < 500) {
          console.log('[Electron] Flask 后端已就绪');
          resolve();
        } else {
          retry();
        }
      });
      req.on('error', () => retry());
      req.setTimeout(1000, () => req.destroy());

      function retry() {
        if (attempts >= maxAttempts) {
          reject(new Error('Flask 后端启动超时，请检查后端日志。'));
          return;
        }
        setTimeout(checkReady, 1000);
      }
    };

    setTimeout(checkReady, 1000);
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 640,
    title: '动态数据登记系统',
    // macOS 用 icns，其余平台用 ico（托盘/任务栏图标）
    icon: process.platform === 'darwin'
      ? path.join(process.resourcesPath, 'icon.icns')
      : path.join(process.resourcesPath, 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // macOS：窗口标题栏保持系统样式，但应用菜单需要显式设置才能显示应用名/快捷键
  if (process.platform === 'darwin') {
    Menu.setApplicationMenu(Menu.buildFromTemplate([
      {
        label: app.name,
        submenu: [
          { role: 'about' },
          { type: 'separator' },
          { role: 'services' },
          { type: 'separator' },
          { role: 'hide' },
          { role: 'hideOthers' },
          { role: 'unhide' },
          { type: 'separator' },
          { role: 'quit' },
        ],
      },
      { label: '编辑', submenu: [
        { role: 'undo' }, { role: 'redo' }, { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' },
      ]},
      { label: '视图', submenu: [
        { role: 'reload' }, { role: 'forceReload' }, { role: 'toggleDevTools' },
        { type: 'separator' }, { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' },
        { type: 'separator' }, { role: 'togglefullscreen' },
      ]},
      { label: '窗口', submenu: [{ role: 'minimize' }, { role: 'zoom' }, { role: 'close' }] },
    ]));
  }

  // 加载 Flask 服务的前端页面
  win.loadURL('http://127.0.0.1:5001/');

  // 拦截所有 target="_blank" 或 window.open，用系统浏览器打开
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

app.whenReady().then(async () => {
  try {
    await startBackend();
    createWindow();
  } catch (err) {
    console.error('[Electron] 启动失败:', err);
    const message = err instanceof Error ? err.message : String(err);
    dialog.showErrorBox('启动失败', message);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  // macOS 惯例：关窗不退出、不杀后端，点 Dock 图标 / Cmd+Q 才退出。
  // 此前这里无条件 kill 后端——mac 上关窗后 activate 重建窗口时后端已死，
  // 页面必然白屏（后端只在 app 启动/退出时各启停一次）。
  if (process.platform !== 'darwin') {
    if (backendProcess) {
      backendProcess.kill();
      backendProcess = null;
    }
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});

// IPC：保存文件对话框（供前端导出文件使用）
ipcMain.handle('save-file', async (_event, options: {
  defaultPath: string;
  filters: { name: string; extensions: string[] }[];
  data: string;
}) => {
  const result = await dialog.showSaveDialog({
    defaultPath: options.defaultPath,
    filters: options.filters,
  });

  if (result.canceled || !result.filePath) {
    return { success: false, canceled: true };
  }

  try {
    fs.writeFileSync(result.filePath, Buffer.from(options.data, 'base64'));
    return { success: true, path: result.filePath };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { success: false, error: message };
  }
});
