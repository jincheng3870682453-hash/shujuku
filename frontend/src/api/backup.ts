import client from './client';
import type { BackupInfo } from '../types/data';

export const backupApi = {
  /** 获取备份文件列表 */
  getBackups: (): Promise<BackupInfo[]> => client.get('/backup'),

  /** 创建数据库备份 */
  createBackup: (): Promise<{ message: string; filename: string; size_bytes: number }> =>
    client.post('/backup'),

  /** 下载指定备份文件 */
  downloadBackup: (filename: string): Promise<Blob> => {
    // 直接使用 <a> 下载方式，避免 blob 大小限制
    const token = localStorage.getItem('token');
    const baseURL = client.defaults.baseURL || '/api';
    const url = `${baseURL}/backup/${encodeURIComponent(filename)}/download`;
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    return Promise.resolve(new Blob());
  },

  /** 上传 .db 文件恢复数据库 */
  restoreBackup: (file: File): Promise<{ message: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/backup/restore', formData);
  },

  /** 删除指定备份 */
  deleteBackup: (filename: string): Promise<{ message: string }> =>
    client.delete(`/backup/${filename}`),
};