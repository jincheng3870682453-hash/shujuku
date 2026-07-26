import { useState, useEffect } from 'react';
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
  Empty,
  Popconfirm,
  Modal,
} from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import type { ColumnsType } from 'antd/es/table';
import { auditApi } from '../api/audit';
import { useRole } from '../hooks/useRole';
import client from '../api/client';
import type { AuditItem, AuditStatus, AuditType } from '../types/data';

const { Title, Text } = Typography;

const auditTypeLabels: Record<AuditType, string> = {
  create: '新增',
  update: '修改',
  delete: '删除',
  import: '导入',
  insert: '新增数据',
  delete_column: '删除字段',
  add_column: '添加字段',
  update_column: '修改字段配置',
  update_column_config: '修改字段配置',
  rename_column: '重命名字段',
  clear_columns: '清空所有字段',
  clear_rows: '清空所有数据',
  clear_logs: '清空日志',
  add_user: '添加用户',
  update_user: '修改用户',
  delete_user: '删除用户',
  reset_database: '重置数据库',
  restore_backup: '恢复备份',
};

const auditTypeColors: Record<AuditType, string> = {
  create: 'green',
  update: 'blue',
  delete: 'red',
  import: 'orange',
  insert: 'green',
  delete_column: 'red',
  add_column: 'green',
  update_column: 'purple',
  update_column_config: 'purple',
  rename_column: 'cyan',
  clear_columns: 'red',
  clear_rows: 'red',
  clear_logs: 'red',
  add_user: 'green',
  update_user: 'purple',
  delete_user: 'red',
  reset_database: 'magenta',
  restore_backup: 'magenta',
};

const statusLabels: Record<AuditStatus, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
};

const statusColors: Record<AuditStatus, string> = {
  pending: 'orange',
  approved: 'green',
  rejected: 'red',
};

/**
 * 后端返回的 status 是中文（'待审核'/'已通过'/'已驳回'），
 * 需要映射为英文 key（pending/approved/rejected）与前端状态常量对齐。
 */
const STATUS_MAP_REVERSE: Record<string, AuditStatus> = {
  '待审核': 'pending',
  '已通过': 'approved',
  '已驳回': 'rejected',
};

/** 将后端中文状态转为前端英文 key */
function normalizeStatus(raw: string | null | undefined): AuditStatus {
  if (!raw) return 'pending';
  return STATUS_MAP_REVERSE[raw] || 'pending';
}

/**
 * 将后端返回的审核记录中的 status 字段从中文映射为英文，
 * 同时补充 detail 字段（从 new_value 中提取可读摘要），
 * 确保前端渲染逻辑一致。
 */
function normalizeAuditItem(item: AuditItem): AuditItem {
  const normalized = { ...item };
  normalized.status = normalizeStatus(item.status);
  // 补充 detail 字段（后端未返回 detail，从 new_value 提取可读信息）
  if (!normalized.detail) {
    try {
      const nv = typeof item.new_value === 'string'
        ? JSON.parse(item.new_value)
        : item.new_value;
      if (nv && typeof nv === 'object' && !Array.isArray(nv)) {
        const labels = Object.keys(nv).slice(0, 3).join('、');
        normalized.detail = labels ? `修改: ${labels}` : '-';
      } else if (typeof nv === 'string') {
        normalized.detail = nv.slice(0, 80);
      }
    } catch {
      // ignore parse errors
    }
  }
  return normalized;
}

function Audit() {
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const { isAdmin: isAdminFromLocal } = useRole();

  // 【修复】仅 Boss 可见操作按钮，HR 只读审核列表
  const [canApprove, setCanApprove] = useState(false);
  useEffect(() => {
    const fetchRole = async () => {
      try {
        const me = await client.get('/me') as { role?: string; permissions?: string[] };
        console.log('[Audit] /api/me 返回:', me);
        // 只有 boss 角色才能看到操作按钮（通过/驳回）
        setCanApprove(me?.role === 'boss');
      } catch (e) {
        console.error('[Audit] /api/me 调用失败:', e);
        // 兜底：使用 localStorage 中角色判断
        try {
          const stored = JSON.parse(localStorage.getItem('user') || '{}');
          setCanApprove(stored?.role === 'boss');
        } catch {
          setCanApprove(false);
        }
      }
    };
    fetchRole();
  }, []);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string | undefined>('pending');

  // 查询审核列表
  const { data: rawData, isLoading } = useQuery({
    queryKey: ['audit', page, pageSize, statusFilter],
    queryFn: () => auditApi.getAuditList({ page, pageSize, status: statusFilter }),
    placeholderData: (prev) => prev,
  });

  // 【修复】对后端返回的数据做 status 映射 + detail 补充
  const data = rawData
    ? {
        ...rawData,
        data: (rawData.data || []).map(normalizeAuditItem),
      }
    : rawData;

  // 通过
  const approveMutation = useMutation({
    mutationFn: (id: number) => {
      console.log('[Audit] 调用 approve, id=', id);
      return auditApi.approve(id);
    },
    onSuccess: (res) => {
      console.log('[Audit] approve 成功:', res);
      messageApi.success('审核通过');
      queryClient.invalidateQueries({ queryKey: ['audit'] });
    },
    onError: (err) => {
      console.error('[Audit] approve 失败:', err);
      messageApi.error('操作失败，请查看控制台日志');
    },
  });

  // 驳回 — 使用独立 Modal + state，避免 Modal.confirm 闭包问题
  const [rejectModalVisible, setRejectModalVisible] = useState(false);
  const [rejectTargetId, setRejectTargetId] = useState<number | null>(null);
  const [rejectComment, setRejectComment] = useState('');

  const rejectMutation = useMutation({
    mutationFn: ({ id, comment }: { id: number; comment: string }) => {
      console.log('[Audit] 调用 reject, id=', id, 'comment=', comment);
      return auditApi.reject(id, comment);
    },
    onSuccess: (res) => {
      console.log('[Audit] reject 成功:', res);
      messageApi.success('已驳回');
      setRejectModalVisible(false);
      setRejectTargetId(null);
      setRejectComment('');
      queryClient.invalidateQueries({ queryKey: ['audit'] });
    },
    onError: (err) => {
      console.error('[Audit] reject 失败:', err);
      messageApi.error('操作失败，请查看控制台日志');
    },
  });

  const handleOpenReject = (id: number) => {
    setRejectTargetId(id);
    setRejectComment('');
    setRejectModalVisible(true);
  };

  const handleConfirmReject = () => {
    if (!rejectComment.trim()) {
      messageApi.warning('请输入驳回原因');
      return;
    }
    if (rejectTargetId === null) return;
    rejectMutation.mutate({ id: rejectTargetId, comment: rejectComment.trim() });
  };

  // 表格列
  const columns: ColumnsType<AuditItem> = [
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 80,
      render: (t: AuditType | string) => (
        <Tag color={auditTypeColors[t as AuditType] ?? 'default'}>
          {auditTypeLabels[t as AuditType] ?? t}
        </Tag>
      ),
    },
    {
      title: '申请人',
      dataIndex: 'applicant',
      key: 'applicant',
      width: 120,
    },
    {
      title: '申请角色',
      dataIndex: 'applicant_role',
      key: 'applicant_role',
      width: 100,
    },
    {
      title: '详情',
      dataIndex: 'detail',  // 【修复】已通过 normalizeAuditItem 补充
      key: 'detail',
      ellipsis: true,
      render: (v: string | null | undefined) => {
        if (!v || v === '-') {
          // 尝试从 new_value 展示
          return <Text type="secondary" ellipsis>-</Text>;
        }
        return <Text ellipsis>{v}</Text>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => {
        const typed = s as AuditStatus;
        const color = statusColors[typed] ?? 'default';
        const label = statusLabels[typed] ?? s;
        return <Tag color={color}>{label}</Tag>;
      },
    },
    {
      title: '审核人',
      dataIndex: 'reviewer',
      key: 'reviewer',
      width: 100,
      render: (v: string | null) => v || '-',
    },
    {
      title: '审核意见',
      dataIndex: 'review_comment',
      key: 'review_comment',
      width: 150,
      ellipsis: true,
      render: (v: string | null) => v || '-',
    },
    {
      title: '提交时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
    },
    // 【修复】操作列：canApprove + 状态为 pending（英文）时显示按钮
    ...(canApprove
      ? [
          {
            title: '操作',
            key: 'action',
            width: 200,
            fixed: 'right' as const,
            render: (_: unknown, record: AuditItem) => {
              // 【关键修复】status 已被 normalizeAuditItem 转为英文 pending/approved/rejected
              if (record.status !== 'pending') return null;
              return (
                <Space size="small">
                  <Popconfirm
                    title="确认通过此申请？"
                    okText="确认通过"
                    cancelText="取消"
                    onConfirm={() => {
                      console.log('[Audit] Popconfirm onConfirm, id=', record.id);
                      approveMutation.mutate(record.id);
                    }}
                  >
                    <Button
                      type="primary"
                      size="small"
                      icon={<CheckOutlined />}
                      style={{ backgroundColor: 'var(--success)', borderColor: 'var(--success)' }}
                    >
                      通过
                    </Button>
                  </Popconfirm>
                  <Button
                    type="primary"
                    size="small"
                    danger
                    icon={<CloseOutlined />}
                    onClick={() => handleOpenReject(record.id)}
                  >
                    驳回
                  </Button>
                </Space>
              );
            },
          },
        ]
      : []),
  ] as ColumnsType<AuditItem>;

  return (
    <>
      {contextHolder}
      <Card className="glass-card">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 16,
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <Title level={4} style={{ margin: 0 }}>
            审核中心
          </Title>
          <Space wrap>
            <Input
              placeholder="搜索申请人…"
              allowClear
              style={{ width: 180 }}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={() => queryClient.invalidateQueries({ queryKey: ['audit'] })}
            >
              刷新
            </Button>
          </Space>
        </div>

        {/* 状态筛选 */}
        <div style={{ marginBottom: 12 }}>
          <Space>
            <Tag
              color={statusFilter === undefined ? 'blue' : 'default'}
              style={{ cursor: 'pointer' }}
              onClick={() => {
                setStatusFilter(undefined);
                setPage(1);
              }}
            >
              全部
            </Tag>
            <Tag
              color={statusFilter === 'pending' ? 'orange' : 'default'}
              style={{ cursor: 'pointer' }}
              onClick={() => {
                setStatusFilter('pending');
                setPage(1);
              }}
            >
              待审核
            </Tag>
            <Tag
              color={statusFilter === 'approved' ? 'green' : 'default'}
              style={{ cursor: 'pointer' }}
              onClick={() => {
                setStatusFilter('approved');
                setPage(1);
              }}
            >
              已通过
            </Tag>
            <Tag
              color={statusFilter === 'rejected' ? 'red' : 'default'}
              style={{ cursor: 'pointer' }}
              onClick={() => {
                setStatusFilter('rejected');
                setPage(1);
              }}
            >
              已驳回
            </Tag>
          </Space>
        </div>

        <Spin spinning={isLoading}>
          {!isLoading && (!data || data.data.length === 0) ? (
            <Empty description="暂无待审核记录" />
          ) : (
            <Table<AuditItem>
              columns={columns}
              dataSource={data?.data ?? []}
              rowKey="id"
              scroll={{ x: 1100 }}
              size="middle"
              pagination={{
                current: page,
                pageSize,
                total: data?.total ?? 0,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 条`,
                onChange: (p, ps) => {
                  setPage(p);
                  setPageSize(ps);
                },
              }}
            />
          )}
        </Spin>
      </Card>

      {/* 驳回弹窗 — 独立 Modal，解决 Modal.confirm 闭包问题 */}
      <Modal
        title="驳回申请"
        open={rejectModalVisible}
        onOk={handleConfirmReject}
        onCancel={() => {
          setRejectModalVisible(false);
          setRejectTargetId(null);
          setRejectComment('');
        }}
        okText="确认驳回"
        cancelText="取消"
        okButtonProps={{ danger: true, loading: rejectMutation.isPending }}
        confirmLoading={rejectMutation.isPending}
        destroyOnClose
      >
        <div style={{ marginTop: 8 }}>
          <Text type="secondary">
            请输入驳回原因（必填）：
          </Text>
          <Input.TextArea
            rows={4}
            placeholder="请详细说明驳回原因…"
            value={rejectComment}
            onChange={(e) => setRejectComment(e.target.value)}
            style={{ marginTop: 8 }}
            autoFocus
          />
        </div>
      </Modal>
    </>
  );
}

export default Audit;