import client from './client';
import type { FieldStats } from '../types/data';

export const statsApi = {
  /** 获取指定字段的统计分布 */
  getFieldStats: (fieldKey: string): Promise<FieldStats> =>
    client.get('/stats', { params: { field: fieldKey } }),

  /** 获取所有可统计的字段列表 */
  getStatFields: (): Promise<{ key: string; label: string; type: string }[]> =>
    client.get('/stats/fields'),
};