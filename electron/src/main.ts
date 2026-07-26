import { app, BrowserWindow, ipcMain, shell, dialog } from 'electron';
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
  // 开发模式：electron/dist/main.js -> project root
  return path.join(__dirname, '..', '..', '..', 'app.py');
}

/** 获取 Python 解释器命令 */
function getPythonCommand(): string {
  if (process.platform === 'win32') {
    return 'python';
  }
  return 'python3';
}

/** 启动 Flask 后端并等待其就绪 */
function startBackend(): Promise<void> {
  return new Promise((resolve, reject) => {
    const appPyPath = getAppPyPath();
    if (!fs.existsSync(appPyPath)) {
      reject(new Error(`未找到后端入口文件: ${appPyPath}\n请确保已打包 app.py 到 resources 目录。`));
      return;
    }

    const cwd = path.dirname(appPyPath);
    const python = getPythonCommand();

    console.log(`[Electron] 启动后端: ${python} ${appPyPath}`);
    console.log(`[Electron] 工作目录: ${cwd}`);

    backendProcess = spawn(python, [appPyPath], {
      cwd,
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
    icon: path.join(process.resourcesPath, 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

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
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
  if (process.platform !== 'darwin') app.quit();
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
