import client from './client';
import type { FieldDefinition, FieldType } from '../types/data';

export const columnsApi = {
  /** 获取所有列定义（与 dataApi.getColumns 保持完全一致的映射逻辑） */
  getColumns: async (): Promise<FieldDefinition[]> => {
    const data = await client.get('/columns') as Array<Record<string, unknown>>;
    console.log('[columnsApi.getColumns] raw data:', data);
    return (data ?? []).map((row: Record<string, unknown>) => {
      // ===== 完整映射逻辑，与 dataApi.getColumns 保持一致 =====
      let parsedOptions: { label: string; value: string }[] | null = null;
      const rawOptions = row.options;
      if (typeof rawOptions === 'string' && rawOptions) {
        try {
          const parsed = JSON.parse(rawOptions);
          if (Array.isArray(parsed)) {
            parsedOptions = parsed;
          } else if (typeof parsed === 'string' && parsed) {
            parsedOptions = parsed.split(',').map((s: string) => s.trim()).filter(Boolean).map((s: string) => ({ label: s, value: s }));
          }
        } catch {
          parsedOptions = rawOptions.split(',').map((s: string) => s.trim()).filter(Boolean).map((s: string) => ({ label: s, value: s }));
        }
      } else if (Array.isArray(rawOptions)) {
        parsedOptions = rawOptions as { label: string; value: string }[];
      }
      const mappedType: FieldType = (row.field_type as FieldType) || 'text';
      console.log('[columnsApi.getColumns] row:', row.label, '→ type:', mappedType, 'options:', parsedOptions);
      return {
        key: row.name as string,
        label: row.label as string || '',
        type: mappedType,
        required: Boolean(row.required),
        options: parsedOptions,
        width: (row.width as number) || 150,
        editable: row.editable !== false,
        sortable: row.sortable !== false,
        options_text: (row.options_text as string) || (typeof rawOptions === 'string' ? rawOptions : ''),
      } as FieldDefinition;
    }) as FieldDefinition[];
  },

  /** 添加新列 */
  addColumn: (data: Omit<FieldDefinition, 'key'> & { key: string }): Promise<{ message: string; field: FieldDefinition }> =>
    client.post('/columns', data),

  /** 重命名列 */
  renameColumn: (oldKey: string, newLabel: string): Promise<{ message: string }> =>
    client.put(`/columns/${oldKey}/label`, { label: newLabel }),

  /** 删除列 */
  deleteColumn: (key: string): Promise<{ message: string }> =>
    client.delete(`/columns/${key}`),

  /** 一键清空所有列（仅 boss） */
  deleteAllColumns: (): Promise<{ message: string }> =>
    client.delete('/columns/all'),

  /** 更新列配置 */
  updateColumn: (key: string, data: Partial<FieldDefinition>): Promise<{ message: string; field: FieldDefinition }> =>
    client.put(`/columns/${key}/config`, data),

  /** 解析 Excel 表头（用于导入列） */
  parseExcelHeaders: (file: File): Promise<{
    headers: { index: number; header: string; status: string; detected_type: string }[];
    total_columns: number;
    unmatched_count: number;
  }> => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/import/preview', formData);
  },
};