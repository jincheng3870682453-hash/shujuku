import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import type { ReactNode } from 'react';
import {
  Table, Button, Input, Modal, Select, DatePicker, InputNumber, Popconfirm, Tag, Space, message, Typography, Spin, Empty, Upload, Descriptions, Divider, Tooltip, Dropdown,
} from 'antd';
import type { MenuProps } from 'antd';
import {
  PlusOutlined, DeleteOutlined, ReloadOutlined, SearchOutlined, DownloadOutlined, UploadOutlined, DashboardOutlined, ClearOutlined, ExclamationCircleOutlined, DatabaseOutlined, CheckOutlined, CloseOutlined, PaperClipOutlined, FileOutlined, EyeOutlined, MoreOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import type { ColumnsType } from 'antd/es/table';
import { dataApi } from '../api/data';
import client from '../api/client';
import { saveFile, generateDefaultFileName } from '../utils/saveFile';
import { useRole } from '../hooks/useRole';
import type { FieldType, RowData } from '../types/data';

const { Title, Text } = Typography;

const FIELD_TYPE_LABELS: Record<FieldType, string> = {
  text: '单行文本',
  textarea: '长文本',
  number: '数字',
  date: '日期',
  select: '下拉',
  boolean: '布尔',
  file: '文件',
};

// ===================== 文件序列化 =====================
interface FileRecord { name: string; type: string; size: number; content: string; }

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => { const r = reader.result as string; resolve(r.split(',')[1] || r); };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function serializeFileRecord(file: File, base64: string): string {
  return JSON.stringify({ name: file.name, type: file.type, size: file.size, content: base64 });
}

function parseFileRecord(value: unknown): FileRecord | null {
  if (typeof value !== 'string' || !value) return null;
  try {
    const obj = JSON.parse(value);
    if (obj && typeof obj.name === 'string' && typeof obj.content === 'string') return obj as FileRecord;
  } catch { /* not JSON */ }
  if (value.startsWith('/static/uploads/') || value.startsWith('http')) {
    return { name: value.split('/').pop() || 'file', type: '', size: 0, content: '' };
  }
  if (value.includes('.') && value.length < 200) {
    return { name: value, type: '', size: 0, content: '' };
  }
  return null;
}

function fileRecordToBlob(record: FileRecord): Blob {
  const bytes = atob(record.content);
  const arr = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  return new Blob([arr], { type: record.type || 'application/octet-stream' });
}

async function downloadFileRecord(value: unknown) {
  const record = parseFileRecord(value);
  if (!record) { message.error('文件数据无效'); return; }
  if (record.content) {
    const blob = fileRecordToBlob(record);
    const ext = record.name.split('.').pop() || 'bin';
    const result = await saveFile(blob, { defaultPath: record.name, filters: [{ name: `文件 (.${ext})`, extensions: [ext] }] });
    if (result.canceled) return;
    if (!result.success) message.error(result.error || '下载失败');
  } else {
    window.open(value as string, '_blank');
  }
}

// ===================== 文件字段显示组件 =====================
function FileFieldDisplay({ value }: { value: unknown }) {
  const record = parseFileRecord(value);
  if (!record) return <Text type="secondary" style={{ fontSize: 'var(--fs-12)' }}>未上传文件</Text>;
  return (
    <Space size={2}>
      <FileOutlined style={{ fontSize: 'var(--fs-12)', color: 'var(--info)' }} />
      <a onClick={(e) => { e.stopPropagation(); downloadFileRecord(value); }} style={{ fontSize: 'var(--fs-12)' }}>
        {record.name}
      </a>
    </Space>
  );
}

// ===================== FileUpload 组件 =====================
function FileUpload({ value, onChange }: { value: unknown; onChange: (value: string) => void }) {
  const [uploading, setUploading] = useState(false);
  const handleBeforeUpload = async (file: File) => {
    setUploading(true);
    try { const b64 = await fileToBase64(file); onChange(serializeFileRecord(file, b64)); }
    catch { message.error('文件读取失败'); }
    finally { setUploading(false); }
    return false;
  };
  const current = parseFileRecord(value);
  return (
    <div style={{ minWidth: 140 }}>
      {current ? (
        <Space size={4}>
          <Tooltip title={`${current.name} (${(current.size / 1024).toFixed(1)} KB)`}>
            <Text style={{ fontSize: 'var(--fs-12)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', display: 'inline-block' }}>
              <PaperClipOutlined style={{ marginRight: 'var(--space-1)' }} />{current.name}
            </Text>
          </Tooltip>
          <Tooltip title="下载"><Button type="text" size="small" icon={<DownloadOutlined />} onClick={() => downloadFileRecord(value)} /></Tooltip>
          <Tooltip title="移除"><Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => onChange('')} /></Tooltip>
        </Space>
      ) : (
        <Upload beforeUpload={handleBeforeUpload} showUploadList={false} accept="*">
          <Button icon={<UploadOutlined />} size="small" loading={uploading}>{uploading ? '处理中…' : '选择文件'}</Button>
        </Upload>
      )}
    </div>
  );
}

// ===================== 内联编辑单元格（展示模式） =====================
function InlineEditCell({
  value, fieldType, fieldOptions, onSave, rowId, fieldKey, readonly,
}: {
  value: unknown; rowId: number; fieldKey: string;
  fieldType: FieldType; fieldOptions: { label: string; value: string }[] | null;
  onSave: (rowId: number, fieldKey: string, value: unknown) => void;
  readonly?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState<unknown>(value);
  const inputRef = useRef<any>(null);
  const editCompletedRef = useRef(false);

  useEffect(() => {
    if (editing) {
      editCompletedRef.current = false;
      setEditValue(value);
      setTimeout(() => inputRef.current?.focus?.(), 50);
    }
  }, [editing, value]);

  // 安全获取字段类型，兜底为 text
  const safeType: FieldType = fieldType || 'text';

  // 获取安全的选项数组
  const safeOptions = useMemo(() => {
    if (Array.isArray(fieldOptions) && fieldOptions.length > 0) return fieldOptions;
    return [];
  }, [fieldOptions]);

  // 自动保存：退出编辑时始终提交（后端幂等，无需前端判断是否变更）
  const handleConfirm = useCallback(() => {
    if (editCompletedRef.current) return;
    editCompletedRef.current = true;
    setEditing(false);
    onSave(rowId, fieldKey, editValue);
  }, [editValue, rowId, fieldKey, onSave]);

  const handleCancel = useCallback(() => {
    editCompletedRef.current = true;
    setEditValue(value);
    setEditing(false);
  }, [value]);

  const numericClassName = safeType === 'number' || safeType === 'date' ? 'tnum' : '';
  const wrapEditor = (editor: ReactNode) => (
    <div className={['cell-editable', 'is-editing', numericClassName].filter(Boolean).join(' ')}>
      {editor}
    </div>
  );

  if (editing && !readonly) {
    switch (safeType) {
      case 'text': case 'textarea':
        return wrapEditor(<Input ref={inputRef} value={(editValue as string) ?? ''} onChange={e => setEditValue(e.target.value)} onPressEnter={handleConfirm} onBlur={handleConfirm} onKeyDown={e => { if (e.key === 'Escape') handleCancel(); }} size="small" style={{ width: '100%' }} suffix={<CheckOutlined style={{ color: 'var(--success)' }} />} />);
      case 'number':
        return wrapEditor(<InputNumber ref={inputRef} value={editValue as number} onChange={v => setEditValue(v)} onPressEnter={handleConfirm} onBlur={handleConfirm} onKeyDown={e => { if (e.key === 'Escape') handleCancel(); }} size="small" style={{ width: '100%' }} />);
      case 'date':
        return wrapEditor(<DatePicker ref={inputRef} value={editValue ? dayjs(editValue as string) : null} onChange={v => setEditValue(v?.format('YYYY-MM-DD HH:mm:ss') ?? null)} onOpenChange={open => { if (!open) handleConfirm(); }} showTime size="small" style={{ width: '100%' }} />);
      case 'select':
        return wrapEditor(
          <Select
            ref={inputRef}
            value={editValue as string}
            onChange={v => { setEditValue(v); setEditing(false); onSave(rowId, fieldKey, v); }}
            options={safeOptions}
            size="small"
            style={{ width: '100%' }}
            defaultOpen
          />,
        );
      case 'boolean':
        return wrapEditor(
          <Select
            ref={inputRef}
            value={editValue as boolean}
            onChange={v => { setEditValue(v); setEditing(false); onSave(rowId, fieldKey, v); }}
            options={[{ label: '是', value: true }, { label: '否', value: false }]}
            size="small"
            style={{ width: '100%' }}
            defaultOpen
          />,
        );
      case 'file':
        return wrapEditor(<FileUpload value={editValue} onChange={v => { setEditValue(v); setEditing(false); onSave(rowId, fieldKey, v); }} />);
      default:
        return wrapEditor(<Input ref={inputRef} value={(editValue as string) ?? ''} onChange={e => setEditValue(e.target.value)} onPressEnter={handleConfirm} onBlur={handleConfirm} onKeyDown={e => { if (e.key === 'Escape') handleCancel(); }} size="small" style={{ width: '100%' }} />);
    }
  }

  const isEmpty = value === null || value === undefined || value === '';
  const displayClassName = [
    readonly ? 'cell-readonly' : 'cell-editable',
    !readonly && isEmpty ? 'cell-editable--empty' : '',
    numericClassName,
  ].filter(Boolean).join(' ');
  const wrapDisplay = (content: ReactNode) => (
    <div className={displayClassName} onDoubleClick={readonly ? undefined : () => setEditing(true)}>
      {content}
      {!readonly && <span className="cell-editable__hint">双击编辑</span>}
    </div>
  );

  // 展示模式（只读模式下不可双击编辑）
  if (isEmpty) return wrapDisplay(<span>—</span>);
  switch (safeType) {
    case 'date': return wrapDisplay(dayjs(value as string).format('YYYY-MM-DD HH:mm'));
    case 'boolean': return wrapDisplay(<span className={value ? 'pill pill--on' : 'pill pill--off'}>{value ? '是' : '否'}</span>);
    case 'select': {
      // 查找 value 对应的 label 显示
      const matched = safeOptions.find(o => o.value === value);
      const displayText = matched ? matched.label : (value ?? '');
      return wrapDisplay(displayText ? String(displayText) : <span>—</span>);
    }
    case 'file': return wrapDisplay(<FileFieldDisplay value={value} />);
    default: return wrapDisplay(String(value));
  }
}

// ===================== 新增行输入控件 =====================
function NewRowCell({ fieldType, fieldOptions, value, onChange }: {
  fieldType: FieldType; fieldOptions: { label: string; value: string }[] | null;
  value: unknown; onChange: (value: unknown) => void;
}) {
  // 安全获取字段类型，兜底为 text
  const safeType: FieldType = fieldType || 'text';

  // 获取安全的选项数组
  const safeOptions = useMemo(() => {
    if (Array.isArray(fieldOptions) && fieldOptions.length > 0) return fieldOptions;
    return [];
  }, [fieldOptions]);

  switch (safeType) {
    case 'text': return <Input value={(value as string) ?? ''} onChange={e => onChange(e.target.value)} size="small" placeholder="输入…" style={{ width: '100%' }} />;
    case 'textarea': return <Input.TextArea value={(value as string) ?? ''} onChange={e => onChange(e.target.value)} size="small" rows={2} placeholder="输入…" style={{ width: '100%' }} />;
    case 'number': return <InputNumber value={value as number} onChange={v => onChange(v)} size="small" style={{ width: '100%' }} />;
    case 'date': return <DatePicker value={value ? dayjs(value as string) : null} onChange={v => onChange(v?.format('YYYY-MM-DD HH:mm:ss') ?? null)} showTime size="small" style={{ width: '100%' }} />;
    case 'select': return <Select value={value as string} onChange={v => onChange(v)} options={safeOptions} size="small" style={{ width: '100%' }} placeholder="选择…" />;
    case 'boolean': return <Select value={value as boolean} onChange={v => onChange(v)} options={[{ label: '是', value: true }, { label: '否', value: false }]} size="small" style={{ width: '100%' }} placeholder="选择…" />;
    case 'file': return <FileUpload value={value} onChange={v => onChange(v)} />;
    default: return <Input value={(value as string) ?? ''} onChange={e => onChange(e.target.value)} size="small" placeholder="输入…" style={{ width: '100%' }} />;
  }
}

// ===================== 主组件 =====================
function DataTable() {
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [modalApi, modalContextHolder] = Modal.useModal();
  const { isAdmin, isEmployee } = useRole();

  const [page, setPage] = useState(1); const [pageSize, setPageSize] = useState(20);
  const [keyword, setKeyword] = useState(''); const [searchInput, setSearchInput] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 新增行状态
  const [isAdding, setIsAdding] = useState(false);
  const newRowDataRef = useRef<Record<string, unknown>>({});
  const [, forceUpdate] = useState(0); // 强制重渲染新增行

  const [resetDbVisible, setResetDbVisible] = useState(false); const [resetDbText, setResetDbText] = useState('');

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value; setSearchInput(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { setKeyword(val); setPage(1); }, 500);
  }, []);

  const [overviewVisible, setOverviewVisible] = useState(false);

  // ========== 组件挂载时强制刷新 columns 缓存，防止 Columns 页面写入的错误缓存污染 DataTable ==========
  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ['columns'] });
  }, [queryClient]);

  const { data: columns = [], isLoading: columnsLoading } = useQuery({
    queryKey: ['columns'], queryFn: dataApi.getColumns, staleTime: 30 * 1000, refetchOnMount: true, retry: 2,
  });
  const { data: rowsData, isLoading: rowsLoading } = useQuery({
    queryKey: ['rows', page, pageSize], queryFn: () => dataApi.getRows({ page, pageSize }), placeholderData: (prev) => prev,
  });

  const allRows: RowData[] = rowsData?.data ?? []; const totalAll = rowsData?.total ?? 0;
  const { filteredRows, filteredTotal } = useMemo(() => {
    try {
      if (!keyword.trim()) return { filteredRows: allRows, filteredTotal: totalAll };
      const kw = keyword.trim().toLowerCase();
      const m = allRows.filter(r => r && typeof r === 'object' && Object.entries(r).some(([k, v]) => k !== 'id' && v !== null && v !== undefined && String(v).toLowerCase().includes(kw)));
      return { filteredRows: m, filteredTotal: m.length };
    } catch {
      return { filteredRows: allRows, filteredTotal: totalAll };
    }
  }, [allRows, keyword, totalAll]);

  const addRowMutation = useMutation({
    mutationFn: async (d: Record<string, unknown>) => dataApi.createRow(d as Partial<RowData>),
    onSuccess: (res) => { messageApi.success(res?.message || '新增成功'); queryClient.invalidateQueries({ queryKey: ['rows'] }); queryClient.refetchQueries({ queryKey: ['rows'], type: 'active' }); setIsAdding(false); newRowDataRef.current = {}; },
    onSettled: () => { queryClient.invalidateQueries({ queryKey: ['rows'] }); queryClient.refetchQueries({ queryKey: ['rows'], type: 'active' }); },
    onError: (err: any) => {
      const errorMsg = err?.response?.data?.error || err?.response?.data?.message || err?.message || '新增失败';
      messageApi.error(errorMsg);
    },
  });
  const updateRowMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Record<string, unknown> }) => dataApi.updateRow(id, data),
    onSuccess: (res) => { messageApi.success(res?.message || '保存成功'); queryClient.invalidateQueries({ queryKey: ['rows'] }); },
    onError: (err: any) => messageApi.error(err?.response?.data?.error || err?.message || '保存失败'),
  });
  const deleteRowMutation = useMutation({
    mutationFn: (id: number) => dataApi.deleteRow(id),
    onSuccess: () => { messageApi.success('删除成功'); queryClient.invalidateQueries({ queryKey: ['rows'] }); },
    onError: () => messageApi.error('删除失败'),
  });
  const clearAllRowsMutation = useMutation({
    mutationFn: async () => client.delete('/rows/all') as Promise<{ message: string }>,
    onSuccess: (res) => { messageApi.success(res?.message || '已清空'); queryClient.invalidateQueries({ queryKey: ['rows'] }); },
    onError: (err: any) => messageApi.error(err?.response?.data?.error || '清空失败'),
  });
  const resetDbMutation = useMutation({
    mutationFn: async () => client.delete('/columns/all') as Promise<{ message: string }>,
    onSuccess: (res) => { messageApi.success(res?.message || '已重置'); queryClient.invalidateQueries({ queryKey: ['columns'] }); queryClient.invalidateQueries({ queryKey: ['rows'] }); setResetDbVisible(false); setResetDbText(''); },
    onError: (err: any) => messageApi.error(err?.response?.data?.error || '重置失败'),
  });

  // ============ 行内编辑（每行独立状态，通过 rowId 区分） ============
  const handleSaveEdit = useCallback((rowId: number, fieldKey: string, value: unknown) => {
    if (rowId === -1) {
      messageApi.warning('无法编辑新增行，请先提交');
      return;
    }
    updateRowMutation.mutate({ id: rowId, data: { [fieldKey]: value } });
  }, [updateRowMutation, messageApi]);

  // ============ 新增行处理 ============
  const startAdd = useCallback(() => {
    const initial: Record<string, unknown> = {};
    for (const col of columns) initial[col.key] = undefined;
    newRowDataRef.current = initial;
    setIsAdding(true);
    forceUpdate(n => n + 1);
  }, [columns]);

  const cancelAdd = useCallback(() => { setIsAdding(false); newRowDataRef.current = {}; }, []);

  const updateNewRowField = useCallback((fieldKey: string, value: unknown) => {
    newRowDataRef.current = { ...newRowDataRef.current, [fieldKey]: value };
    forceUpdate(n => n + 1);
  }, []);

  const submitNewRow = useCallback(() => {
    const rawData = newRowDataRef.current;

    // 构建清理后的 payload，按列定义校验数据类型
    const payload: Record<string, unknown> = {};
    let hasValue = false;

    for (const col of columns) {
      let val = rawData[col.key];
      const safeType: FieldType = col.type || 'text';

      // 空字符串转 null
      if (val === '' || val === undefined) {
        val = null;
      }

      if (val === null || val === undefined) {
        payload[col.key] = null;
        continue;
      }

      hasValue = true;

      switch (safeType) {
        case 'text':
        case 'textarea':
          payload[col.key] = typeof val === 'string' ? val : String(val);
          break;
        case 'number':
          if (typeof val === 'number') {
            payload[col.key] = val;
          } else if (typeof val === 'string' && val.trim() !== '') {
            const num = Number(val);
            payload[col.key] = isNaN(num) ? null : num;
          } else {
            payload[col.key] = null;
          }
          break;
        case 'date':
          // 日期格式应为 YYYY-MM-DD HH:mm:ss 或 YYYY-MM-DD
          payload[col.key] = typeof val === 'string' && val ? val : null;
          break;
        case 'select':
          // 下拉字段传字符串
          if (typeof val === 'string') {
            payload[col.key] = val;
          } else if (typeof val === 'object' && val !== null && 'value' in (val as Record<string, unknown>)) {
            payload[col.key] = String((val as Record<string, unknown>).value);
          } else {
            payload[col.key] = val !== null && val !== undefined ? String(val) : null;
          }
          break;
        case 'boolean':
          if (typeof val === 'boolean') {
            payload[col.key] = val;
          } else if (typeof val === 'string') {
            payload[col.key] = val === 'true' || val === '是' ? true : val === 'false' || val === '否' ? false : null;
          } else {
            payload[col.key] = null;
          }
          break;
        case 'file':
          // 文件字段传 JSON 字符串或 null
          if (typeof val === 'string' && val) {
            // 验证是否为有效的 JSON 文件记录
            try {
              const parsed = JSON.parse(val);
              if (parsed && typeof parsed.name === 'string' && typeof parsed.content === 'string') {
                payload[col.key] = val; // 有效的文件 JSON 字符串
              } else {
                payload[col.key] = null;
              }
            } catch {
              payload[col.key] = null;
            }
          } else if (typeof val === 'object' && val !== null) {
            payload[col.key] = JSON.stringify(val);
          } else {
            payload[col.key] = null;
          }
          break;
        default:
          payload[col.key] = val;
      }
    }

    if (!hasValue) { messageApi.warning('请至少填写一个字段'); return; }
    addRowMutation.mutate(payload);
  }, [addRowMutation, messageApi, columns]);

  const exportMutation = useMutation({
    mutationFn: async () => { const blob = await dataApi.exportExcel(); return saveFile(blob, { defaultPath: generateDefaultFileName('数据登记表', 'xlsx'), filters: [{ name: 'Excel 文件', extensions: ['xlsx', 'xls'] }] }); },
    onSuccess: (r) => { if (r.canceled) return; if (r.success) messageApi.success(r.path ? `已保存至：${r.path}` : '导出成功'); else messageApi.error(r.error || '导出失败'); },
    onError: (err: Error) => messageApi.error(err.message || '导出失败'),
  });

  const [importModalVisible, setImportModalVisible] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importPreviewRows, setImportPreviewRows] = useState<{ row: number; cells: string[]; non_empty: number }[]>([]);
  const [selectedHeaderRow, setSelectedHeaderRow] = useState<number>(1);
  const [importLoading, setImportLoading] = useState(false);
  const handleFileSelected = async (file: File) => { setImportFile(file); setImportLoading(true); try { const fd = new FormData(); fd.append('file', file); const res = await client.post('/import/preview', fd) as any; setImportPreviewRows(res?.preview_rows ?? []); setSelectedHeaderRow(res?.detected_header_row ?? 1); setImportModalVisible(true); } catch { messageApi.error('读取文件失败'); } finally { setImportLoading(false); } };
  const doImport = async () => { if (!importFile) return; setImportLoading(true); try { const fd = new FormData(); fd.append('file', importFile); fd.append('header_row', String(selectedHeaderRow)); const res = await client.post('/import', fd) as any; messageApi.success(res?.message || '导入成功'); queryClient.invalidateQueries({ queryKey: ['rows'] }); queryClient.invalidateQueries({ queryKey: ['columns'] }); setImportModalVisible(false); setImportFile(null); setImportPreviewRows([]); } catch (err: unknown) { messageApi.error((err as any)?.response?.data?.error || '导入失败'); } finally { setImportLoading(false); } };

  // ============ 表格列生成 — 每行独立状态 ============
  const tableColumns: ColumnsType<RowData> = useMemo(() => {
    if (!columns || !Array.isArray(columns) || !columns.length) {
      return [] as ColumnsType<RowData>;
    }
    const cols = columns.map((col, index) => {
      // 安全获取类型，兜底为 'text'
      const safeType: FieldType = col.type || 'text';
      // 安全获取选项
      const safeOptions = Array.isArray(col.options) ? col.options : null;

      return {
        title: (
          <Tooltip title={`${col.key} · ${safeType}`}>
            <div>
              <span style={{ color: 'var(--ink-primary)', fontSize: 'var(--fs-13)' }}>
                {col.label}{col.required ? <span style={{ color: 'var(--danger)', marginLeft: 2 }}>*</span> : null}
              </span>
              <span style={{ display: 'block', color: 'var(--ink-muted)', fontSize: 'var(--fs-11)', fontWeight: 400 }}>
                {FIELD_TYPE_LABELS[safeType]}
              </span>
            </div>
          </Tooltip>
        ),
        dataIndex: col.key,
        key: col.key,
        width: col.width || 150,
        fixed: index === 0 ? 'left' as const : undefined,
        className: safeType === 'number' ? 'tnum' : undefined,
        onHeaderCell: () => ({ style: { height: 'var(--col-head-h)' } }),
        sorter: col.sortable ? (a: RowData, b: RowData) => {
          const va = a[col.key], vb = b[col.key];
          if (va === vb) return 0;
          if (va === null || va === undefined) return -1;
          if (vb === null || vb === undefined) return 1;
          return String(va).localeCompare(String(vb));
        } : undefined,
        render: (v: unknown, rec: RowData) => (
          <InlineEditCell
            key={`${rec.id}-${col.key}`}
            value={v}
            rowId={rec.id}
            fieldKey={col.key}
            fieldType={safeType}
            fieldOptions={safeOptions}
            onSave={handleSaveEdit}
            readonly={isEmployee}
          />
        ),
      };
    });
    if (!isEmployee) {
      cols.push({
        title: <span style={{ color: 'var(--ink-primary)', fontSize: 'var(--fs-13)' }}>操作</span>,
        key: 'action',
        width: 80,
        fixed: 'right' as const,
        onHeaderCell: () => ({ style: { height: 'var(--col-head-h)' } }),
        render: (_: unknown, rec: RowData) => (
          <Popconfirm title={<span>确定要删除这条记录吗？</span>} onConfirm={() => deleteRowMutation.mutate(rec.id)} okText="删除" cancelText="取消">
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        ),
      } as any);
    }
    return cols as ColumnsType<RowData>;
  }, [columns, deleteRowMutation, handleSaveEdit, isEmployee]);

  const isLoading = columnsLoading || rowsLoading;
  const dataStatus = rowsData?.data?.[0]?.id ? '运行中' : '暂无数据';
  const moreMenuItems: NonNullable<MenuProps['items']> = [];

  if (!isEmployee && isAdmin) {
    if (totalAll > 0) {
      moreMenuItems.push({
        key: 'clear-data',
        danger: true,
        icon: <ClearOutlined />,
        disabled: clearAllRowsMutation.isPending,
        label: (
          <span style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-4)', minWidth: 180 }}>
            <span>清空数据</span>
            <span style={{ color: 'var(--danger)', fontSize: 'var(--fs-11)' }}>需二次确认</span>
          </span>
        ),
        onClick: () => {
          modalApi.confirm({
            title: '确定要清空所有数据吗？',
            icon: <ExclamationCircleOutlined style={{ color: 'var(--danger)' }} />,
            content: '此操作将删除所有数据，且不可恢复。',
            okText: '清空数据',
            okButtonProps: { danger: true },
            cancelText: '取消',
            onOk: () => clearAllRowsMutation.mutateAsync(),
          });
        },
      });
    }
    moreMenuItems.push({
      key: 'reset-database',
      danger: true,
      icon: <DatabaseOutlined />,
      label: (
        <span style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-4)', minWidth: 180 }}>
          <span>重置数据库</span>
          <span style={{ color: 'var(--danger)', fontSize: 'var(--fs-11)' }}>需二次确认</span>
        </span>
      ),
      onClick: () => setResetDbVisible(true),
    });
  }

  return (
    <>
      {contextHolder}
      {modalContextHolder}
      <div className="animate-fade-in">
        <div className="viewbar">
          <span className="viewbar__title">数据管理</span>
          <span className="viewbar__stats">
            <span><b className="tnum">{totalAll.toLocaleString('zh-CN')}</b> 条记录</span>
            <span>·</span>
            <span><b className="tnum">{columns.length}</b> 个字段</span>
            <span>·</span>
            <span><b>{dataStatus}</b></span>
          </span>
          <span className="viewbar__spacer" />
          <div className="viewbar__tools">
            <Input
              size="small"
              placeholder="搜索…"
              prefix={<SearchOutlined />}
              value={searchInput}
              onChange={handleSearchChange}
              allowClear
              style={{ width: 200 }}
            />
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => { queryClient.invalidateQueries({ queryKey: ['rows'] }); queryClient.invalidateQueries({ queryKey: ['columns'] }); }}
            >
              刷新
            </Button>
            {!isEmployee && (
              <Upload accept=".xlsx,.xls" showUploadList={false} beforeUpload={(file) => { handleFileSelected(file); return false; }}>
                <Button size="small" icon={<UploadOutlined />} loading={importLoading}>导入</Button>
              </Upload>
            )}
            <Button size="small" icon={<DownloadOutlined />} onClick={() => exportMutation.mutate()} loading={exportMutation.isPending}>导出</Button>
            <Button size="small" icon={<DashboardOutlined />} onClick={() => setOverviewVisible(true)}>总览</Button>
            {!isEmployee && isAdmin && (
              <Dropdown menu={{ items: moreMenuItems }} trigger={['click']} placement="bottomRight">
                <Button size="small" type="text" icon={<MoreOutlined />} aria-label="更多操作" />
              </Dropdown>
            )}
          </div>
        </div>

        {!isEmployee && columns.length > 0 && (
          <div style={{ padding: 'var(--space-2) var(--space-3)', background: 'var(--surface-base)', borderLeft: '1px solid var(--line-frame)', borderRight: '1px solid var(--line-frame)' }}>
            <Upload
              accept=".xlsx,.xls"
              showUploadList={false}
              beforeUpload={(file) => { handleFileSelected(file); return false; }}
              style={{ display: 'block', width: '100%' }}
            >
              <div
                className="dropstrip"
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  const file = event.dataTransfer.files?.[0];
                  if (file) handleFileSelected(file);
                }}
              >
                <UploadOutlined />
                <span>{importLoading ? '正在读取 Excel 文件…' : '拖拽 Excel 文件至此处或点击导入'}</span>
              </div>
            </Upload>
          </div>
        )}

        <Spin spinning={isLoading}>
          {columns.length === 0 ? (
            <div style={{ background: 'var(--surface-base)', border: '1px solid var(--line-frame)', padding: 'var(--space-8)' }}>
              <Empty description={<span>暂无字段定义，请先<Button type="link" onClick={() => window.location.href = '/columns'}>添加字段</Button></span>} />
            </div>
          ) : (
            <>
              <Table<RowData>
                columns={tableColumns}
                dataSource={filteredRows}
                rowKey="id"
                scroll={{ x: 'max-content' }}
                size="small"
                onRow={() => ({ style: { height: 'var(--row-h)' } })}
                locale={{
                  emptyText: keyword.trim()
                    ? <span>无匹配数据</span>
                    : (<div style={{ padding: 'var(--space-4)' }}><Text type="secondary">暂无数据</Text></div>),
                }}
                pagination={{
                  current: page, pageSize, total: filteredTotal,
                  showSizeChanger: true, showQuickJumper: true,
                  pageSizeOptions: ['10', '20', '50', '100'],
                  showTotal: t => `共 ${t} 条`,
                  onChange: (p, ps) => { setPage(p); setPageSize(ps); },
                }}
                footer={!isEmployee ? () => (
                  isAdding ? (
                    <Table
                      dataSource={[{ id: -1, ...newRowDataRef.current }]}
                      rowKey={() => 'new-row'}
                      pagination={false}
                      size="small"
                      showHeader={false}
                      onRow={() => ({ style: { height: 'var(--row-h)' } })}
                      columns={[
                        ...columns.map((col, index) => {
                          const safeType: FieldType = col.type || 'text';
                          const safeOptions = Array.isArray(col.options) ? col.options : null;
                          return {
                            title: '',
                            dataIndex: col.key,
                            key: col.key,
                            width: col.width || 150,
                            fixed: index === 0 ? 'left' as const : undefined,
                            className: safeType === 'number' ? 'tnum' : undefined,
                            render: () => (
                              <NewRowCell
                                fieldType={safeType}
                                fieldOptions={safeOptions}
                                value={newRowDataRef.current[col.key]}
                                onChange={(v) => updateNewRowField(col.key, v)}
                              />
                            ),
                          };
                        }),
                        {
                          title: '', key: 'action', width: 120, fixed: 'right' as const,
                          render: () => (
                            <Space size={4}>
                              <Tooltip title="确认新增"><Button type="text" size="small" icon={<CheckOutlined />} style={{ color: 'var(--success)' }} loading={addRowMutation.isPending} onClick={submitNewRow} /></Tooltip>
                              <Tooltip title="取消"><Button type="text" size="small" icon={<CloseOutlined />} style={{ color: 'var(--danger)' }} onClick={cancelAdd} disabled={addRowMutation.isPending} /></Tooltip>
                            </Space>
                          ),
                        } as any,
                      ]}
                    />
                  ) : (
                    <Button type="text" icon={<PlusOutlined />} onClick={startAdd}>
                      点击新增一行数据
                    </Button>
                  )
                ) : undefined}
              />
              <div className="thin-note">
                {isEmployee ? (
                  <><EyeOutlined />当前账号为只读权限，仅可查看数据</>
                ) : (
                  <>双击单元格编辑 · Enter 保存 · Esc 取消</>
                )}
              </div>
            </>
          )}
        </Spin>
      </div>
      <Modal
        title="数据总览"
        open={overviewVisible}
        onCancel={() => setOverviewVisible(false)}
        footer={<Button onClick={() => setOverviewVisible(false)}>关闭</Button>}
        width={700}
      >
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label="总列数">{columns.length}</Descriptions.Item>
          <Descriptions.Item label="总记录数">{totalAll}</Descriptions.Item>
          <Descriptions.Item label="当前页">{page}</Descriptions.Item>
          <Descriptions.Item label="每页条数">{pageSize}</Descriptions.Item>
        </Descriptions>
        <Divider />
        <Title level={5} style={{ fontSize: 'var(--fs-14)' }}>列列表</Title>
        {columns.map(col => (
          <Tag key={col.key} style={{ marginBottom: 'var(--space-2)' }}>
            {col.label}<Text type="secondary" style={{ fontSize: 'var(--fs-11)' }}>({col.key}: {col.type})</Text>
          </Tag>
        ))}
      </Modal>
      <Modal
        title="选择表头行"
        open={importModalVisible}
        onCancel={() => { setImportModalVisible(false); setImportFile(null); setImportPreviewRows([]); }}
        width={800}
        footer={[
          <Button key="cancel" onClick={() => { setImportModalVisible(false); setImportFile(null); setImportPreviewRows([]); }}>取消</Button>,
          <Button key="submit" type="primary" loading={importLoading} onClick={doImport}>确认导入</Button>,
        ]}
      >
        <div style={{ maxHeight: 420, overflowY: 'auto' }}>
          <Table
            dataSource={importPreviewRows}
            rowKey="row"
            pagination={false}
            size="small"
            columns={[
              {
                title: '',
                width: 50,
                render: (_: unknown, rec: { row: number }) => <input type="radio" checked={selectedHeaderRow === rec.row} onChange={() => setSelectedHeaderRow(rec.row)} />,
              },
              {
                title: '行号',
                dataIndex: 'row',
                width: 60,
                render: (value: number) => (
                  <Tag
                    className="tnum"
                    style={{
                      background: selectedHeaderRow === value ? 'var(--status-info-bg)' : 'var(--surface-sunken)',
                      color: selectedHeaderRow === value ? 'var(--status-info-fg)' : 'var(--ink-default)',
                    }}
                  >
                    {value}
                  </Tag>
                ),
              },
              ...(importPreviewRows[0] ? importPreviewRows[0].cells.map((_: string, columnIndex: number) => ({
                title: `列${columnIndex + 1}`,
                dataIndex: 'cells',
                width: 120,
                ellipsis: true,
                render: (cells: string[]) => cells?.[columnIndex] || <span style={{ color: 'var(--ink-muted)' }}>—</span>,
              })) : []),
            ]}
          />
        </div>
        <div style={{ marginTop: 'var(--space-3)' }}>
          <Text type="secondary">手动输入表头行号：</Text>
          <InputNumber min={1} max={importPreviewRows.length || 99} value={selectedHeaderRow} onChange={value => value && setSelectedHeaderRow(value)} style={{ width: 80, marginLeft: 'var(--space-2)' }} />
        </div>
      </Modal>
      <Modal
        title={<span><ExclamationCircleOutlined style={{ color: 'var(--danger)', marginRight: 'var(--space-2)' }} />确认重置数据库</span>}
        open={resetDbVisible}
        onCancel={() => { setResetDbVisible(false); setResetDbText(''); }}
        footer={[
          <Button key="cancel" onClick={() => { setResetDbVisible(false); setResetDbText(''); }}>取消</Button>,
          <Button key="submit" danger type="primary" onClick={() => resetDbMutation.mutate()} loading={resetDbMutation.isPending} disabled={resetDbText !== '确认重置'}>确认重置</Button>,
        ]}
      >
        <p style={{ marginBottom: 'var(--space-3)' }}>此操作将删除所有字段定义及所有数据，且不可恢复！</p>
        <p style={{ color: 'var(--danger)', fontWeight: 'bold' }}>请输入「确认重置」以确认：</p>
        <Input value={resetDbText} onChange={event => setResetDbText(event.target.value)} placeholder="确认重置" />
      </Modal>
    </>
  );
}

export default DataTable;