import dayjs from 'dayjs';

/**
 * 检测当前是否运行在 Electron 环境中
 */
const isElectron =
  typeof window !== 'undefined' &&
  typeof (window as unknown as Record<string, unknown>).electronAPI === 'object';

/**
 * 将 Blob 转换为 base64 字符串
 */
function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      // 去掉 data:...;base64, 前缀
      const base64 = result.split(',')[1] || result;
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

/**
 * 生成带时间戳的默认文件名
 * @param prefix 文件名前缀
 * @param ext 文件扩展名
 * @returns 格式为 `${prefix}_YYYYMMDD_HHmmss.${ext}` 的文件名
 */
export function generateDefaultFileName(prefix: string, ext: string): string {
  return `${prefix}_${dayjs().format('YYYYMMDD_HHmmss')}.${ext}`;
}

/**
 * 统一的保存文件方法
 * - Electron 环境：通过 IPC 调用主进程的 dialog.showSaveDialog
 * - 浏览器环境：优先使用 showSaveFilePicker API，不支持则回退到 <a> 下载
 *
 * @param blob 要保存的 Blob 数据
 * @param options.defaultPath 默认文件名（例如 '数据登记表_20260723_170000.xlsx'）
 * @param options.filters 文件过滤器（例如 [{ name: 'Excel', extensions: ['xlsx', 'xls'] }]）
 * @returns { success: boolean; path?: string; canceled?: boolean; error?: string }
 */
export async function saveFile(
  blob: Blob,
  options: {
    defaultPath: string;
    filters: { name: string; extensions: string[] }[];
  }
): Promise<{ success: boolean; path?: string; canceled?: boolean; error?: string }> {
  // ─── Electron 环境 ───
  if (isElectron) {
    try {
      const base64Data = await blobToBase64(blob);
      const result = await window.electronAPI.saveFile({
        defaultPath: options.defaultPath,
        filters: options.filters,
        data: base64Data,
      });
      return result;
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      return { success: false, error: message };
    }
  }

  // ─── 浏览器环境 ───
  // 方案 A：showSaveFilePicker（现代浏览器）
  if (typeof window !== 'undefined' && 'showSaveFilePicker' in window) {
    try {
      const ext = options.defaultPath.split('.').pop() || '';
      const mimeTypes: Record<string, string> = {
        xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        xls: 'application/vnd.ms-excel',
        png: 'image/png',
        txt: 'text/plain',
        db: 'application/octet-stream',
        json: 'application/json',
      };

      const handle = await (window as unknown as {
        showSaveFilePicker: (opts: {
          suggestedName: string;
          types?: { description: string; accept: Record<string, string[]> }[];
        }) => Promise<{
          createWritable: () => Promise<{
            write: (data: Blob) => Promise<void>;
            close: () => Promise<void>;
          }>;
        }>;
      }).showSaveFilePicker({
        suggestedName: options.defaultPath,
        types: options.filters.map((f) => ({
          description: f.name,
          accept: {
            [mimeTypes[f.extensions[0]] || 'application/octet-stream']: [
              `.${f.extensions.join(', .')}`,
            ],
          },
        })),
      });

      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return { success: true, path: '' };
    } catch (error: unknown) {
      const err = error as { name?: string };
      if (err?.name === 'AbortError') {
        return { success: false, canceled: true };
      }
      // 回退到方案 B
    }
  }

  // 方案 B：回退到 <a> 标签下载
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = options.defaultPath;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);

  return { success: true, path: '' };
}