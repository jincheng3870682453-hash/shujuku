import { useState } from 'react';
import {
  Card, Button, Upload, Table, Space, Typography, message, Spin, Popconfirm, Tag,
} from 'antd';
import {
  CloudDownloadOutlined, UploadOutlined, DeleteOutlined, ReloadOutlined, ExportOutlined, InboxOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import type { ColumnsType } from 'antd/es/table';
import type { UploadProps } from 'antd/es/upload';
import axios from 'axios';
import client from '../api/client';
import { backupApi } from '../api/backup';
import { saveFile, generateDefaultFileName } from '../utils/saveFile';
import type { BackupInfo } from '../types/data';

const { Title } = Typography;
const { Dragger } = Upload;

function Backup() {
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [restoreLoading, setRestoreLoading] = useState(false);

  const { data: backups, isLoading } = useQuery<BackupInfo[]>({
    queryKey: ['backups'], queryFn: backupApi.getBackups,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await backupApi.createBackup();
      // 使用 axios 获取备份文件的 blob 数据
      const token = localStorage.getItem('token');
      const url = `${client.defaults.baseURL}/backup/${encodeURIComponent(res.filename)}/download`;
      const response = await axios.get(url, {
        responseType: 'blob',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const result = await saveFile(response.data as Blob, {
        defaultPath: res.filename || generateDefaultFileName('backup', 'db'),
        filters: [{ name: '数据库文件', extensions: ['db'] }],
      });
      if (result.canceled) return { ...res, savedPath: null };
      if (!result.success) throw new Error(result.error || '保存失败');
      return { ...res, savedPath: result.path };
    },
    onSuccess: (res) => {
      messageApi.success(res.savedPath ? `文件已保存至：${res.savedPath}` : (res?.message || '备份创建成功'));
      queryClient.invalidateQueries({ queryKey: ['backups'] });
    },
    onError: (err: unknown) => {
      const msg = (err as any)?.response?.data?.error || (err as Error)?.message || '备份创建失败';
      messageApi.error(msg);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: backupApi.deleteBackup,
    onSuccess: () => { messageApi.success('备份已删除'); queryClient.invalidateQueries({ queryKey: ['backups'] }); },
    onError: () => messageApi.error('删除失败'),
  });

  const handleRestore = async (file: File): Promise<boolean> => {
    setRestoreLoading(true);
    try {
      await backupApi.restoreBackup(file);
      messageApi.success('数据库恢复成功，部分设置可能需要刷新页面生效');
      queryClient.invalidateQueries({ queryKey: ['backups'] });
      return true;
    } catch { messageApi.error('恢复失败，请确认上传的是有效的 .db 文件'); return false; }
    finally { setRestoreLoading(false); }
  };

  const uploadProps: UploadProps = {
    name: 'file', accept: '.db', showUploadList: false, multiple: false,
    beforeUpload: (file) => { handleRestore(file); return false; },
  };

  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const columns: ColumnsType<BackupInfo> = [
    { title: '文件名', dataIndex: 'filename', key: 'filename', ellipsis: true },
    { title: '大小', dataIndex: 'size_bytes', key: 'size_bytes', width: 120, align: 'right', render: (v: number) => formatSize(v) },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180, render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss') },
    { title: '操作', key: 'action', width: 160,
      render: (_: unknown, record: BackupInfo) => (
        <Space size="small">
          <Button type="link" size="small" icon={<CloudDownloadOutlined />} onClick={async () => {
            try {
              const token = localStorage.getItem('token');
              const url = `${client.defaults.baseURL}/backup/${encodeURIComponent(record.filename)}/download`;
              const response = await axios.get(url, {
                responseType: 'blob',
                headers: token ? { Authorization: `Bearer ${token}` } : {},
              });
              const result = await saveFile(response.data as Blob, {
                defaultPath: record.filename,
                filters: [{ name: '数据库文件', extensions: ['db'] }],
              });
              if (result.canceled) return;
              if (result.path) {
                messageApi.success(`文件已保存至：${result.path}`);
              } else {
                messageApi.success('下载成功');
              }
            } catch {
              messageApi.error('下载失败');
            }
          }}>下载</Button>
          <Popconfirm title="确认删除此备份？" onConfirm={() => deleteMutation.mutate(record.filename)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      {contextHolder}
      <Card className="glass-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <Title level={4} style={{ margin: 0 }}>备份恢复</Title>
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={() => queryClient.invalidateQueries({ queryKey: ['backups'] })}>刷新</Button>
            <Button type="primary" icon={<ExportOutlined />} onClick={() => createMutation.mutate()} loading={createMutation.isPending} className="gradient-bg" style={{ border: 'none' }}>立即备份</Button>
          </Space>
        </div>
      </Card>

      <Card className="glass-card" style={{ marginBottom: 16 }}>
        <Title level={5} style={{ marginBottom: 12 }}>恢复数据库</Title>
        <Spin spinning={restoreLoading} tip="正在恢复…">
          <Dragger {...uploadProps}>
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">点击或拖拽 .db 文件到此区域</p>
            <p className="ant-upload-hint">支持拖拽导入 .db 文件进行数据恢复</p>
          </Dragger>
        </Spin>
      </Card>

      <Card className="glass-card">
        <Title level={5} style={{ marginBottom: 12 }}>历史备份<Tag style={{ marginLeft: 8 }}>{backups?.length ?? 0} 个文件</Tag></Title>
        <Spin spinning={isLoading}>
          <Table<BackupInfo> columns={columns} dataSource={backups ?? []} rowKey="filename" size="middle" pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 个备份` }} locale={{ emptyText: '暂无备份文件，点击「立即备份」创建' }} />
        </Spin>
      </Card>
    </>
  );
}

export default Backup;