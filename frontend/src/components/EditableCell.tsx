import { useState, useRef, useEffect } from 'react';
import {
  Input,
  InputNumber,
  DatePicker,
  Select,
  Space,
  Typography,
  message,
  Switch,
  Upload,
  Button,
} from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  EditOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import type { FieldType } from '../types/data';

const { Text } = Typography;

interface EditableCellProps {
  value: unknown;
  fieldKey: string;
  fieldType: FieldType;
  fieldOptions?: { label: string; value: string }[] | null;
  onSave: (key: string, value: unknown) => Promise<void>;
}

function EditableCell({
  value,
  fieldKey,
  fieldType,
  fieldOptions,
  onSave,
}: EditableCellProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState<unknown>(value);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setEditValue(value);
  }, [value]);

  // 失焦保存
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        inputRef.current &&
        !inputRef.current.contains(event.target as Node)
      ) {
        setEditing(false);
      }
    }
    if (editing) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [editing]);

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      await onSave(fieldKey, editValue);
      setEditing(false);
    } catch {
      message.error('保存失败');
      setEditValue(value); // 回滚
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setEditValue(value);
    setEditing(false);
  };

  // ---- 渲染模式 ----
  const renderDisplay = () => {
    if (value === null || value === undefined || value === '') {
      return (
        <Text type="secondary" style={{ fontStyle: 'italic', fontSize: 13 }}>
          点击编辑
        </Text>
      );
    }
    if (fieldType === 'date') {
      return dayjs(value as string).format('YYYY-MM-DD HH:mm');
    }
    if (fieldType === 'select' && fieldOptions) {
      const opt = fieldOptions.find((o) => o.value === String(value));
      return opt?.label ?? String(value);
    }
    if (fieldType === 'boolean') {
      return value ? '是' : '否';
    }
    if (fieldType === 'file') {
      return value ? '📎 已上传' : '未上传';
    }
    return String(value);
  };

  // ---- 编辑控件 ----
  const renderEditor = () => {
    switch (fieldType) {
      case 'number':
        return (
          <InputNumber
            style={{ width: '100%' }}
            value={editValue as number}
            onChange={(v) => setEditValue(v)}
            onPressEnter={handleSave}
            autoFocus
          />
        );
      case 'date':
        return (
          <DatePicker
            showTime
            style={{ width: '100%' }}
            value={editValue ? dayjs(editValue as string) : null}
            onChange={(_, dateStr) => setEditValue(dateStr)}
            autoFocus
            open
          />
        );
      case 'textarea':
        return (
          <Input.TextArea
            rows={3}
            value={editValue as string}
            onChange={(e) => setEditValue(e.target.value)}
            autoFocus
          />
        );
      case 'select':
        return (
          <Select
            style={{ width: '100%' }}
            value={editValue as string}
            onChange={(v) => setEditValue(v)}
            options={fieldOptions ?? []}
            autoFocus
            open
          />
        );
      case 'boolean':
        return (
          <Switch
            checked={!!editValue}
            onChange={(v) => setEditValue(v)}
            autoFocus
          />
        );
      case 'file':
        return (
          <Upload maxCount={1} beforeUpload={() => false}>
            <Button icon={<UploadOutlined />} size="small">选择文件</Button>
          </Upload>
        );
      default: // text
        return (
          <Input
            value={editValue as string}
            onChange={(e) => setEditValue(e.target.value)}
            onPressEnter={handleSave}
            autoFocus
          />
        );
    }
  };

  return (
    <div
      ref={inputRef}
      style={{ minHeight: 28, cursor: editing ? 'default' : 'pointer' }}
      onDoubleClick={() => setEditing(true)}
      title="双击编辑"
    >
      {editing ? (
        <Space.Compact style={{ width: '100%' }}>
          <div style={{ flex: 1 }}>{renderEditor()}</div>
          <CheckOutlined
            style={{ color: 'var(--success)', fontSize: 14, cursor: 'pointer', padding: '0 4px' }}
            onClick={handleSave}
          />
          <CloseOutlined
            style={{ color: 'var(--danger)', fontSize: 14, cursor: 'pointer', padding: '0 4px' }}
            onClick={handleCancel}
          />
        </Space.Compact>
      ) : (
        <div
          onClick={() => setEditing(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            minHeight: 28,
          }}
        >
          <span style={{ flex: 1 }}>{renderDisplay()}</span>
          <EditOutlined
            style={{ color: 'var(--text-secondary)', fontSize: 12, opacity: 0.6 }}
          />
        </div>
      )}
    </div>
  );
}

export default EditableCell;