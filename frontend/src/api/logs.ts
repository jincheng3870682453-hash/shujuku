import client from './client';
import type { LogItem, PaginatedResponse } from '../types/data';

export const logsApi = {
  /** 获取操作日志（分页 + 搜索） */
  getLogs: (params: {
    page: number;
    pageSize: number;
    keyword?: string;
    username?: string;
    action?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<PaginatedResponse<LogItem>> =>
    client.get('/logs', { params }),

  /** 导出日志为 TXT 文本 */
  exportLogs: (params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<Blob> =>
    client.get('/logs/export', { params, responseType: 'blob' }),

  /** 清空全部日志 */
  clearLogs: (): Promise<{ message: string }> =>
    client.delete('/logs/all'),
};