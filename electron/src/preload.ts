import { contextBridge, ipcRenderer } from 'electron';

/**
 * 向渲染进程暴露安全的 Electron API。
 * 遵循 contextIsolation: true + nodeIntegration: false 的安全规范。
 */
contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * 获取当前数据库引擎类型
   * @returns 'sqlite' 或 'mysql'
   */
  getDbEngine: () => 'sqlite',

  /**
   * 获取应用版本号
   * @returns 版本字符串
   */
  getVersion: () => '6.0.0',

  /**
   * 打开外部链接（使用系统默认浏览器）
   * 通过 IPC 通知主进程打开（实际由 setWindowOpenHandler 处理）
   * @param url 要打开的 URL
   */
  openExternal: (url: string) => {
    // 渲染进程中直接使用 window.open 即可，
    // 主进程的 setWindowOpenHandler 会拦截并用 shell.openExternal 处理
    window.open(url, '_blank');
  },

  /**
   * 弹出系统保存对话框，让用户选择保存位置和文件名
   * 主进程处理 dialog.showSaveDialog，写入文件并返回结果
   * @param options.defaultPath - 默认文件名
   * @param options.filters - 文件过滤器
   * @param options.data - 文件的 base64 编码内容
   * @returns { success: boolean, path?: string, canceled?: boolean, error?: string }
   */
  saveFile: (options: {
    defaultPath: string;
    filters: { name: string; extensions: string[] }[];
    data: string;
  }) => ipcRenderer.invoke('save-file', options),
});

// ──────── 类型声明 ────────

declare global {
  interface Window {
    electronAPI: {
      getDbEngine: () => string;
      getVersion: () => string;
      openExternal: (url: string) => void;
      saveFile: (options: {
        defaultPath: string;
        filters: { name: string; extensions: string[] }[];
        data: string;
      }) => Promise<{ success: boolean; path?: string; canceled?: boolean; error?: string }>;
    };
  }
}

export {};
