import { useState } from 'react';
import {
  Card,
  Table,
  Button,
  Input,
  Tag,
  Space,
  Typography,
  message,
  Spin,
  Popconfirm,
} from 'antd';
import {
  SearchOutlined,
  DownloadOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import type { ColumnsType } from 'antd/es/table';
import { logsApi } from '../api/logs';
import { saveFile, generateDefaultFileName } from '../utils/saveFile';
import { useRole } from '../hooks/useRole';
import type { LogItem } from '../types/data';

const { Title } = Typography;

function Logs() {
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const { isAdmin } = useRole();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [keyword, setKeyword] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['logs', page, pageSize, keyword],
    queryFn: () => logsApi.getLogs({ page, pageSize, keyword: keyword || undefined }),
    placeholderData: (prev) => prev,
  });

  const exportMutation = useMutation({
    mutationFn: async () => {
      const blob = await logsApi.exportLogs();
      const result = await saveFile(blob, {
        defaultPath: generateDefaultFileName('操作日志', 'txt'),
        filters: [{ name: '文本文件', extensions: ['txt'] }],
      });
      if (!result.success && !result.canceled) {
        throw new Error(result.error || '导出失败');
      }
      return result;
    },
    onSuccess: (result) => {
      if (result.canceled) return;
      if (result.path) {
        messageApi.success(`文件已保存至：${result.path}`);
      } else {
        messageApi.success('导出成功');
      }
    },
    onError: (err: Error) => messageApi.error(err.message || '导出失败'),
  });

  const clearMutation = useMutation({
    mutationFn: logsApi.clearLogs,
    onSuccess: () => {
      messageApi.success('所有日志已清空');
      queryClient.invalidateQueries({ queryKey: ['logs'] });
    },
    onError: () => messageApi.error('清空失败'),
  });

  const columns: ColumnsType<LogItem> = [
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160, render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-' },
    { title: '用户', dataIndex: 'username', key: 'username', width: 100 },
    { title: '角色', dataIndex: 'role', key: 'role', width: 80, render: (r: string) => <Tag color={r === 'boss' ? 'red' : r === 'hr' ? 'blue' : 'green'}>{r === 'boss' ? '管理员' : r === 'hr' ? 'HR' : '员工'}</Tag> },
    { title: '操作', dataIndex: 'action', key: 'action', width: 120, render: (a: string) => <Tag>{a}</Tag> },
    { title: '目标', dataIndex: 'target_type', key: 'target_type', width: 100, ellipsis: true },
    { title: '详情', dataIndex: 'detail', key: 'detail', ellipsis: true },
  ];

  return (
    <>
      {contextHolder}
      <Card className="glass-card">
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16, flexWrap:'wrap', gap:12}}>
          <Title level={4} style={{margin:0}}>操作日志</Title>
          <Space wrap>
            <Input placeholder="搜索用户、操作、详情…" prefix={<SearchOutlined/>} value={keyword}
              onChange={(e)=>{setKeyword(e.target.value);setPage(1);}} allowClear style={{width:260}}/>
            <Button icon={<ReloadOutlined/>} onClick={()=>queryClient.invalidateQueries({queryKey:['logs']})}>刷新</Button>
            <Button icon={<DownloadOutlined/>} onClick={()=>exportMutation.mutate()} loading={exportMutation.isPending}>导出 TXT</Button>
            {isAdmin && (
              <Popconfirm title="确定要清空所有操作日志吗？此操作不可恢复！" onConfirm={()=>clearMutation.mutate()}>
                <Button danger icon={<DeleteOutlined/>} loading={clearMutation.isPending}>清空日志</Button>
              </Popconfirm>
            )}
          </Space>
        </div>
        <Spin spinning={isLoading}>
          <div style={{overflowX:'auto'}}>
            <Table<LogItem> columns={columns} dataSource={data?.data??[]} rowKey="id" scroll={{x:'max-content'}} size="middle"
              pagination={{current:page, pageSize, total:data?.total??0, showSizeChanger:true, showTotal:(t)=>`共 ${t} 条`, onChange:(p,ps)=>{setPage(p);setPageSize(ps);}}} />
          </div>
        </Spin>
      </Card>
    </>
  );
}

export default Logs;