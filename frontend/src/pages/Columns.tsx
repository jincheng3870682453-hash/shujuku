import { useState, useRef, useCallback, useEffect } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select, Popconfirm, Tag, Space, Typography, message, Spin, Tooltip,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, ReloadOutlined, UnorderedListOutlined, UploadOutlined, ExclamationCircleOutlined, DownloadOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { ColumnsType } from 'antd/es/table';
import { Upload } from 'antd';
import { columnsApi } from '../api/columns';
import { saveFile, generateDefaultFileName } from '../utils/saveFile';
import { useColumnStore } from '../stores/columnStore';
import { useRole } from '../hooks/useRole';
import type { FieldDefinition, FieldType } from '../types/data';

const { Title } = Typography;

// ===================== 纯工具函数 =====================

const ESC_MARK = '\x1E';
const ESC_MARK_CN = '\x1F';

function parseOptions(input: unknown): { label: string; value: string }[] | null {
  if (typeof input !== 'string') return null;
  const trimmed = input.trim();
  if (!trimmed) return null;
  let work = trimmed.replace(/\\,/g, ESC_MARK);
  work = work.replace(/\\，/g, ESC_MARK_CN);
  const parts = work.split(/[,，]/);
  const result: { label: string; value: string }[] = [];
  for (const raw of parts) {
    const restored = raw.trim()
      .split(ESC_MARK).join(',')
      .split(ESC_MARK_CN).join('，');
    if (restored.length > 0) {
      result.push({ label: restored, value: restored });
    }
  }
  console.log('[parseOptions] input:', trimmed, '-> result:', result);
  return result.length > 0 ? result : null;
}

function optionsToString(options: string | { label: string; value: string }[] | null): string {
  if (!options) return '';
  if (typeof options === 'string') return options;
  if (!Array.isArray(options) || options.length === 0) return '';
  return options.map(o => o.label.replace(/,/g, '\\,').replace(/，/g, '\\，')).join(', ');
}

// ===================== 常量 =====================

const fieldTypeOptions: { label: string; value: FieldType }[] = [
  { label: '文本', value: 'text' }, { label: '数字', value: 'number' }, { label: '日期', value: 'date' },
  { label: '下拉选择', value: 'select' }, { label: '多行文本', value: 'textarea' },
  { label: '布尔/开关', value: 'boolean' }, { label: '文件上传', value: 'file' },
];

const typeColorMap: Record<FieldType, string> = {
  text: 'blue', number: 'green', date: 'orange', select: 'purple', textarea: 'cyan', boolean: 'geekblue', file: 'magenta',
};

const OPTIONS_TOOLTIP_TEXT = '用逗号分隔选项。如果选项本身含有逗号，在逗号前加 \\ 转义。示例：苹果\\, 香蕉, 橘子 -> 选项为「苹果, 香蕉」和「橘子」';

// ===================== 组件 =====================

function Columns() {
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const { canManage, isAdmin } = useRole();
  const columnStore = useColumnStore();

  const [modalVisible, setModalVisible] = useState(false);
  const [editingColumn, setEditingColumn] = useState<FieldDefinition | null>(null);
  const [modalConfirmLoading, setModalConfirmLoading] = useState(false);
  const [form] = Form.useForm();
  const [selectedType, setSelectedType] = useState<FieldType>('text');

  const [renameVisible, setRenameVisible] = useState(false);
  const [renameKey, setRenameKey] = useState('');
  const [renameForm] = Form.useForm<{ label: string }>();

  const [batchVisible, setBatchVisible] = useState(false);
  const [batchFields, setBatchFields] = useState<{ key: string; label: string; type: FieldType; required: boolean; options_text: string }[]>(
    [{ key: '', label: '', type: 'text', required: false, options_text: '' }]
  );
  const [batchLoading, setBatchLoading] = useState(false);

  const [clearConfirmVisible, setClearConfirmVisible] = useState(false);
  const [clearConfirmText, setClearConfirmText] = useState('');

  // ============ 数据查询 ============
  const { data: columns = [], isLoading } = useQuery<FieldDefinition[]>({
    queryKey: ['columns'],
    queryFn: columnsApi.getColumns,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
    refetchOnMount: true,
    retry: 2,
  });

  // ============ Mutations ============
  const addMutation = useMutation({
    mutationFn: columnsApi.addColumn,
    onSuccess: () => {
      messageApi.success('列添加成功');
      queryClient.invalidateQueries({ queryKey: ['columns'] });
      queryClient.invalidateQueries({ queryKey: ['rows'] });
      setModalVisible(false);
      form.resetFields();
      setSelectedType('text');
    },
    onError: () => messageApi.error('添加失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: columnsApi.deleteColumn,
    onSuccess: () => {
      messageApi.success('列已删除');
      queryClient.invalidateQueries({ queryKey: ['columns'] });
      queryClient.invalidateQueries({ queryKey: ['rows'] });
    },
    onError: () => messageApi.error('删除失败'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ key, data }: { key: string; data: Partial<FieldDefinition> }) =>
      columnsApi.updateColumn(key, data),
    onSuccess: () => {
      messageApi.success('更新成功');
      queryClient.invalidateQueries({ queryKey: ['columns'] });
      queryClient.invalidateQueries({ queryKey: ['rows'] });
      // 编辑自动保存时不移除 Modal，保持用户继续编辑
    },
    onError: () => messageApi.error('更新失败'),
  });

  const renameMutation = useMutation({
    mutationFn: ({ oldKey, newLabel }: { oldKey: string; newLabel: string }) =>
      columnsApi.renameColumn(oldKey, newLabel),
    onSuccess: () => { messageApi.success('重命名成功'); queryClient.invalidateQueries({ queryKey: ['columns'] }); setRenameVisible(false); },
    onError: () => messageApi.error('重命名失败'),
  });

  const clearAllMutation = useMutation({
    mutationFn: columnsApi.deleteAllColumns,
    onSuccess: () => { messageApi.success('所有列已清空'); queryClient.invalidateQueries({ queryKey: ['columns'] }); setClearConfirmVisible(false); setClearConfirmText(''); },
    onError: () => messageApi.error('清空失败'),
  });

  // ============ 新增字段提交 ============
  const handleCreateSubmit = async () => {
    try {
      const values = await form.validateFields();
      console.log('[handleCreateSubmit] values:', values);
      setModalConfirmLoading(true);
      let options: { label: string; value: string }[] | null = null;

      if (values.type === 'select') {
        const rawText = form.getFieldValue('options_text');
        if (typeof rawText !== 'string' || !rawText.trim()) {
          messageApi.warning('请至少输入一个选项');
          setModalConfirmLoading(false);
          return;
        }
        options = parseOptions(rawText);
        if (!options || options.length === 0) {
          messageApi.warning('请至少输入一个选项');
          setModalConfirmLoading(false);
          return;
        }
      }

      const finalOptionsText = typeof form.getFieldValue('options_text') === 'string'
        ? form.getFieldValue('options_text') as string
        : '';
      const optionsForBackend = options ? options.map(o => o.label).join(',') : null;

      await addMutation.mutateAsync({
        key: values.key, label: values.label, type: values.type,
        required: values.required || false,
        options: optionsForBackend as any,
        options_text: finalOptionsText,
        width: 150, editable: true, sortable: true,
      } as any);
    } catch (err) {
      console.log('[handleCreateSubmit] error:', err);
    } finally {
      setModalConfirmLoading(false);
    }
  };

  // ============ 编辑模式自动保存 ============
  const handleEditAutoSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleEditAutoSave = useCallback(async () => {
    if (!editingColumn) return; // 仅在编辑模式下触发
    // 防抖：300ms 内多次变动只保存一次
    if (handleEditAutoSaveRef.current) clearTimeout(handleEditAutoSaveRef.current);
    handleEditAutoSaveRef.current = setTimeout(async () => {
      try {
        const values = form.getFieldsValue();
        console.log('[autoSave] editingColumn:', editingColumn.key, 'values:', values);

        let options: { label: string; value: string }[] | null = null;
        if (values.type === 'select') {
          const rawText = values.options_text;
          if (typeof rawText === 'string' && rawText.trim()) {
            options = parseOptions(rawText);
          }
        }

        const finalOptionsText = (typeof values.options_text === 'string' ? values.options_text : '') || '';
        const optionsForBackend = options ? options.map(o => o.label).join(',') : null;

        await updateMutation.mutateAsync({
          key: editingColumn.key,
          data: {
            label: values.label,
            type: values.type || editingColumn.type,
            required: values.required !== undefined ? values.required : editingColumn.required,
            options: optionsForBackend as any,
            options_text: finalOptionsText,
          },
        });
        console.log('[autoSave] 编辑已保存');
      } catch (err) {
        console.log('[autoSave] error:', err);
      }
    }, 300);
  }, [editingColumn, updateMutation]);

  useEffect(() => {
    return () => {
      if (handleEditAutoSaveRef.current) clearTimeout(handleEditAutoSaveRef.current);
    };
  }, []);

  // ============ Modal 打开/关闭 ============
  const openCreateModal = () => {
    setEditingColumn(null);
    setSelectedType('text');
    form.resetFields();
    form.setFieldsValue({ type: 'text', required: false, options_text: '' });
    setModalVisible(true);
  };

  const openEditModal = (record: FieldDefinition) => {
    setEditingColumn(record);
    setSelectedType(record.type);
    const optsText = record.options_text || optionsToString(record.options);
    form.setFieldsValue({
      key: record.key, label: record.label, type: record.type,
      required: record.required, options_text: optsText,
    });
    setModalVisible(true);
  };

  const closeModal = () => {
    setModalVisible(false);
    form.resetFields();
    setSelectedType('text');
  };

  const openRenameModal = (record: FieldDefinition) => { setRenameKey(record.key); renameForm.setFieldsValue({ label: record.label }); setRenameVisible(true); };
  const handleRenameOk = async () => { try { const values = await renameForm.validateFields(); await renameMutation.mutateAsync({ oldKey: renameKey, newLabel: values.label }); } catch { /* */ } };
  const handleTypeChange = (val: FieldType) => { setSelectedType(val); form.setFieldsValue({ options_text: '' }); };

  // ============ 表格列 ============
  const tableColumns: ColumnsType<FieldDefinition> = [
    { title: '列标识', dataIndex: 'key', key: 'key', width: 160, ellipsis: true, render: (v: string) => <code style={{ fontSize: 13 }}>{v}</code> },
    { title: '列名称', dataIndex: 'label', key: 'label', width: 160 },
    { title: '数据格式', dataIndex: 'type', key: 'type', width: 120, render: (t: FieldType) => <Tag color={typeColorMap[t]}>{fieldTypeOptions.find(o => o.value === t)?.label ?? t}</Tag> },
    { title: '必填', dataIndex: 'required', key: 'required', width: 80, align: 'center', render: (v: boolean) => v ? <Tag color="red">是</Tag> : <Tag>否</Tag> },
    { title: '可编辑', dataIndex: 'editable', key: 'editable', width: 80, align: 'center', render: (v: boolean) => v ? <Tag color="green">是</Tag> : <Tag>否</Tag> },
    ...(canManage ? [{
      title: '操作', key: 'action', width: 220, fixed: 'right' as const,
      render: (_: unknown, record: FieldDefinition) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)}>编辑</Button>
          <Button type="link" size="small" onClick={() => openRenameModal(record)}>重命名</Button>
          <Popconfirm title={`确定要删除列「${record.label}」吗？该列下所有数据将一并删除！`} onConfirm={() => deleteMutation.mutate(record.key)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    }] : []),
  ] as ColumnsType<FieldDefinition>;

  // ============ 渲染 ============
  return (
    <>
      {contextHolder}
      <Card className="glass-card" style={{ overflow: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
          <Title level={4} style={{ margin: 0 }}>表格设置</Title>
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={() => queryClient.invalidateQueries({ queryKey: ['columns'] })}>刷新</Button>
            {canManage && (
              <>
                <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal} className="gradient-bg" style={{ border: 'none' }}>添加列</Button>
                <Button icon={<UnorderedListOutlined />} onClick={() => setBatchVisible(true)}>批量添加</Button>
                <Upload accept=".xlsx,.xls" showUploadList={false} beforeUpload={async (file) => {
                  const hide = messageApi.loading('正在解析 Excel 表头...');
                  try {
                    const res = await columnsApi.parseExcelHeaders(file);
                    const unmatched = (res?.headers ?? []).filter((h: any) => h.status === 'unmatched');
                    if (!unmatched.length) { hide(); messageApi.warning('没有找到新列'); return false; }
                    let created = 0;
                    for (const h of unmatched) {
                      const key = (h.header || 'col').replace(/[^a-zA-Z0-9_]/g, '_').toLowerCase().replace(/^(\d)/, '_$1');
                      try { await columnsApi.addColumn({ key, label: h.header, type: (h.detected_type as FieldType) || 'text', required: false, options: null, options_text: '', width: 150, editable: true, sortable: true } as any); created++; } catch { /* skip */ }
                    }
                    hide(); messageApi.success(`成功导入 ${created} 个列`); queryClient.invalidateQueries({ queryKey: ['columns'] });
                  } catch { hide(); messageApi.error('导入失败'); }
                  return false;
                }}>
                  <Button icon={<UploadOutlined />}>导入列</Button>
                </Upload>
                <Button icon={<DownloadOutlined />} onClick={async () => {
                  try {
                    const data = columns ?? [];
                    const exportData = data.map(({ key, label, type, required, editable, sortable, width, options_text }) => ({ key, label, type, required, editable, sortable, width, options_text }));
                    const jsonStr = JSON.stringify(exportData, null, 2);
                    const blob = new Blob([jsonStr], { type: 'application/json' });
                    const result = await saveFile(blob, { defaultPath: generateDefaultFileName('列定义', 'json'), filters: [{ name: 'JSON 文件', extensions: ['json'] }] });
                    if (result.canceled) return;
                    if (result.path) { messageApi.success(`文件已保存至：${result.path}`); } else { messageApi.success('导出成功'); }
                  } catch { messageApi.error('导出失败'); }
                }}>导出列</Button>
                {isAdmin && <Button danger icon={<DeleteOutlined />} onClick={() => setClearConfirmVisible(true)}>一键清空列</Button>}
              </>
            )}
          </Space>
        </div>
        <Spin spinning={isLoading}>
          <Table<FieldDefinition> columns={tableColumns} dataSource={columns} rowKey="key" scroll={{ x: 'max-content' }} size="middle" pagination={false}
            locale={{ emptyText: '暂无字段，请点击「添加列」或「批量添加」创建字段' }} />
        </Spin>
      </Card>

      {/* ========== 新增／编辑列 Modal ========== */}
      <Modal
        title={editingColumn ? '编辑列' : '添加列'}
        open={modalVisible}
        onOk={editingColumn ? undefined : handleCreateSubmit}
        onCancel={closeModal}
        confirmLoading={modalConfirmLoading}
        width={520}
        okText={editingColumn ? '关闭' : '确定'}
      >
        <Form
          form={form}
          layout="vertical"
          style={{ marginTop: 16 }}
          onValuesChange={editingColumn ? handleEditAutoSave : undefined}
        >
          <Form.Item name="key" label="列标识（英文）"
            rules={[{ required: true, message: '请输入列标识' }, { pattern: /^[a-zA-Z][a-zA-Z0-9_]*$/, message: '仅允许英文字母、数字和下划线' }]}>
            <Input placeholder="例如：email、phone" disabled={!!editingColumn} />
          </Form.Item>
          <Form.Item name="label" label="列名称" rules={[{ required: true, message: '请输入列名称' }]}>
            <Input placeholder="例如：邮箱、手机号" />
          </Form.Item>
          <Form.Item name="type" label="数据格式" rules={[{ required: true, message: '请选择数据格式' }]}>
            <Select options={fieldTypeOptions} placeholder="请选择数据格式" onChange={handleTypeChange} />
          </Form.Item>

          {/* ===== 关键修复：将 Tooltip 移到 Form.Item 外层 =====
               Form.Item 需要通过 cloneElement 向直接子元素（Input）注入 value/onChange。
               之前 Tooltip 包裹了 Input，导致 Form.Item 的直接子元素是 Tooltip 而不是 Input，
               value/onChange 注入到了 Tooltip 上（被忽略），Input 完全没有收到，
               所以 form.getFieldValue('options_text') 永远返回空字符串。 */}
          {selectedType === 'select' && (
            <Tooltip
              title={OPTIONS_TOOLTIP_TEXT}
              trigger="focus"
              placement="bottom"
              overlayStyle={{ maxWidth: 400 }}
            >
              {/* Tooltip 在外层，Form.Item 的直接子元素是 Input，value/onChange 正确注入 */}
              <Form.Item
                name="options_text"
                label="下拉选项"
                rules={[{ required: true, message: '请至少输入一个选项' }]}
              >
                <Input placeholder="苹果, 香蕉, 橘子" />
              </Form.Item>
            </Tooltip>
          )}

          <Form.Item name="required" label="是否必填">
            <Select options={[{ label: '是', value: true }, { label: '否', value: false }]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* ========== 批量添加 Modal ========== */}
      <Modal title="批量添加列" open={batchVisible} onCancel={() => setBatchVisible(false)} width={900}
        footer={[
          <Button key="cancel" onClick={() => setBatchVisible(false)}>取消</Button>,
          <Button key="submit" type="primary" loading={batchLoading} onClick={async () => {
            setBatchLoading(true);
            try {
              const valid = batchFields.filter(f => f.key.trim() && f.label.trim());
              if (!valid.length) { messageApi.warning('请至少填写一个完整的列'); setBatchLoading(false); return; }
              for (const f of valid) {
                try {
                  const options = f.type === 'select' ? parseOptions(f.options_text) : null;
                  await columnsApi.addColumn({ key: f.key.trim(), label: f.label.trim(), type: f.type, required: f.required, options, options_text: f.options_text || '', width: 150, editable: true, sortable: true } as any);
                } catch { /* skip */ }
              }
              messageApi.success(`成功添加 ${valid.length} 个列`);
              queryClient.invalidateQueries({ queryKey: ['columns'] });
              setBatchVisible(false);
              setBatchFields([{ key: '', label: '', type: 'text', required: false, options_text: '' }]);
            } finally { setBatchLoading(false); }
          }} className="gradient-bg" style={{ border: 'none' }}>批量提交</Button>,
        ]}
      >
        <Table dataSource={batchFields} rowKey={(_, i) => String(i)} pagination={false} size="small" style={{ marginTop: 8 }} scroll={{ x: 'max-content' }}
          columns={[
            { title: '列标识', dataIndex: 'key', width: 130, render: (_: string, __: unknown, i: number) => (
              <Input placeholder="英文名" value={batchFields[i]?.key ?? ''} onChange={e => { const c = [...batchFields]; c[i] = { ...c[i], key: e.target.value.replace(/[^a-zA-Z0-9_]/g, '') }; setBatchFields(c); }} />
            )},
            { title: '列名称', dataIndex: 'label', width: 130, render: (_: string, __: unknown, i: number) => (
              <Input placeholder="中文名" value={batchFields[i]?.label ?? ''} onChange={e => { const c = [...batchFields]; c[i] = { ...c[i], label: e.target.value }; setBatchFields(c); }} />
            )},
            { title: '数据格式', dataIndex: 'type', width: 110, render: (_: string, __: unknown, i: number) => (
              <Select style={{ width: '100%' }} value={batchFields[i]?.type ?? 'text'} onChange={v => { const c = [...batchFields]; c[i] = { ...c[i], type: v, options_text: '' }; setBatchFields(c); }} options={fieldTypeOptions} />
            )},
            { title: '下拉选项', dataIndex: 'options_text', width: 170, render: (_: string, __: unknown, i: number) => batchFields[i]?.type !== 'select'
              ? <span style={{ color: 'var(--text-secondary)' }}>—</span>
              : (
                // 批量添加表中也修复：Tooltip 不能包裹在受控 Input 外层（这里 Input 是手动控 value/onChange 的，没问题）
                // 但为了体验一致，同样将 Tooltip 只用于提示
                <Tooltip title="用逗号分隔选项。含逗号的选项前加 \ 转义。" trigger="focus" placement="bottom" overlayStyle={{ maxWidth: 300 }}>
                  <Input placeholder="苹果, 香蕉" value={batchFields[i]?.options_text ?? ''} onChange={e => { const c = [...batchFields]; c[i] = { ...c[i], options_text: e.target.value }; setBatchFields(c); }} />
                </Tooltip>
              )
            },
            { title: '必填', dataIndex: 'required', width: 60, render: (_: string, __: unknown, i: number) => (
              <Select style={{ width: '100%' }} value={batchFields[i]?.required ? 'yes' : 'no'} onChange={v => { const c = [...batchFields]; c[i] = { ...c[i], required: v === 'yes' }; setBatchFields(c); }} options={[{ label: '是', value: 'yes' }, { label: '否', value: 'no' }]} />
            )},
            { title: '操作', width: 80, fixed: 'right' as const, render: (_: unknown, __: unknown, i: number) => (
              <Space>
                <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => setBatchFields([...batchFields, { key: '', label: '', type: 'text', required: false, options_text: '' }])} />
                {batchFields.length > 1 && <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => setBatchFields(batchFields.filter((_, idx) => idx !== i))} />}
              </Space>
            )},
          ]} />
      </Modal>

      {/* 重命名 Modal */}
      <Modal title="重命名列" open={renameVisible} onOk={handleRenameOk} onCancel={() => setRenameVisible(false)} confirmLoading={renameMutation.isPending} destroyOnClose>
        <Form form={renameForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="label" label="新列名称" rules={[{ required: true, message: '请输入新名称' }]}>
            <Input placeholder="输入新的显示名称" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 一键清空确认 Modal */}
      <Modal
        title={<span><ExclamationCircleOutlined style={{ color: 'var(--danger)', marginRight: 8 }} />确认清空所有列</span>}
        open={clearConfirmVisible}
        onCancel={() => { setClearConfirmVisible(false); setClearConfirmText(''); }}
        footer={[
          <Button key="cancel" onClick={() => { setClearConfirmVisible(false); setClearConfirmText(''); }}>取消</Button>,
          <Button key="submit" danger type="primary" onClick={() => clearAllMutation.mutate()} loading={clearAllMutation.isPending} disabled={clearConfirmText !== '确认删除'}>确认清空</Button>,
        ]}
      >
        <p style={{ marginBottom: 12 }}>此操作将删除所有列定义及对应的所有数据，且不可恢复！确定要继续吗？</p>
        <p style={{ color: 'var(--danger)', fontWeight: 'bold' }}>请输入「确认删除」以确认操作：</p>
        <Input value={clearConfirmText} onChange={e => setClearConfirmText(e.target.value)} placeholder="确认删除" />
      </Modal>
    </>
  );
}

export default Columns;