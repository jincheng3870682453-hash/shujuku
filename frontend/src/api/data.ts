import client from './client';
import type { FieldDefinition, RowData, PaginatedResponse } from '../types/data';

export const dataApi = {
  /** 获取所有列定义（后端返回 name/field_type/options，前端映射为 key/type/options 并解析 JSON） */
  getColumns: async (): Promise<FieldDefinition[]> => {
    const data = await client.get('/columns') as Array<Record<string, unknown>>;
    console.log('[dataApi.getColumns] raw data:', data);
    return (data ?? []).map((row: Record<string, unknown>) => {
      let parsedOptions: { label: string; value: string }[] | null = null;
      const rawOptions = row.options;
      if (typeof rawOptions === 'string' && rawOptions) {
        try {
          const parsed = JSON.parse(rawOptions);
          if (Array.isArray(parsed)) {
            // JSON 数组格式：[{"label":"苹果","value":"苹果"},...]
            parsedOptions = parsed;
          } else if (typeof parsed === 'string' && parsed) {
            // JSON 字符串格式："苹果,香蕉" → split 为数组
            parsedOptions = parsed.split(',').map((s: string) => s.trim()).filter(Boolean).map((s: string) => ({ label: s, value: s }));
          }
        } catch {
          // 纯逗号分隔的字符串
          parsedOptions = rawOptions.split(',').map((s: string) => s.trim()).filter(Boolean).map((s: string) => ({ label: s, value: s }));
        }
      } else if (Array.isArray(rawOptions)) {
        parsedOptions = rawOptions as { label: string; value: string }[];
      }
      console.log('[dataApi.getColumns] row:', row.label, '→ options:', parsedOptions);
      return {
        key: row.name as string,
        label: row.label as string || '',
        type: (row.field_type as FieldDefinition['type']) || 'text',
        required: Boolean(row.required),
        options: parsedOptions,
        width: (row.width as number) || 150,
        editable: row.editable !== false,
        sortable: row.sortable !== false,
        options_text: (row.options_text as string) || (typeof rawOptions === 'string' ? rawOptions : ''),
      } as FieldDefinition;
    }) as FieldDefinition[];
  },

  getRows: (params: {
    page: number;
    pageSize: number;
    keyword?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }) =>
    client.get('/rows', { params }) as Promise<PaginatedResponse<RowData>>,

  createRow: (data: Partial<RowData>) =>
    client.post('/rows', data) as Promise<{ id: number; message: string }>,

  updateRow: (id: number, data: Partial<RowData>) =>
    client.put(`/rows/${id}`, data) as Promise<{ message: string }>,

  deleteRow: (id: number) =>
    client.delete(`/rows/${id}`) as Promise<{ message: string }>,

  batchDelete: (ids: number[]) =>
    client.post('/rows/batch-delete', { ids }) as Promise<{ message: string }>,

  // 导出 Excel
  exportExcel: (): Promise<Blob> =>
    client.get('/export', { responseType: 'blob' }),

  // 导入 Excel
  importExcel: (file: File): Promise<{ message: string; count: number; fail_count?: number; new_fields?: string[] }> => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/import', formData);
  },
};