import client from './client';
import type { AppSettings } from '../types/data';

export const settingsApi = {
  /** 获取当前设置 */
  getSettings: (): Promise<AppSettings> => client.get('/settings'),

  /** 更新数据库引擎设置 */
  updateSettings: (data: Partial<AppSettings>): Promise<{ message: string }> =>
    client.put('/settings', data),

  /** 测试 MySQL 连接 */
  testMysqlConnection: (data: {
    host: string;
    port: number;
    user: string;
    password: string;
    database: string;
  }): Promise<{ success: boolean; message: string }> =>
    client.post('/settings/test-mysql', data),
};