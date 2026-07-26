import client from './client';
import type { AuditItem, PaginatedResponse } from '../types/data';

export const auditApi = {
  /** 获取审核列表（分页） */
  getAuditList: (params: {
    page: number;
    pageSize: number;
    status?: string;
  }): Promise<PaginatedResponse<AuditItem>> =>
    client.get('/audit', { params }),

  /** 审核通过 */
  approve: (id: number, comment?: string): Promise<{ message: string }> =>
    client.post(`/audit/${id}/approve`, { comment }),

  /** 审核驳回 */
  reject: (id: number, comment: string): Promise<{ message: string }> =>
    client.post(`/audit/${id}/reject`, { comment }),

  /** 获取待审核数量 */
  getCount: (): Promise<{ pending: number }> =>
    client.get('/audit/count'),
};