import { useState, useMemo, useCallback } from 'react';
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Checkbox,
  Tag,
  Space,
  Typography,
  message,
  Spin,
  Popconfirm,
  Switch,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import type { ColumnsType } from 'antd/es/table';
import { usersApi } from '../api/users';
import { useRole } from '../hooks/useRole';
import type { User, UserFormValues, UserRole } from '../types/data';

const { Title } = Typography;

// ─── 角色选项 ───
const roleOptions: { label: string; value: UserRole | 'custom' }[] = [
  { label: '管理员', value: 'boss' },
  { label: 'HR', value: 'hr' },
  { label: '员工', value: 'employee' },
  { label: '自定义', value: 'custom' },
];

const roleLabelMap: Record<UserRole, string> = {
  boss: '管理员',
  hr: 'HR',
  employee: '员工',
  custom: '自定义',
};

const roleColorMap: Record<UserRole, string> = {
  boss: 'red',
  hr: 'blue',
  employee: 'green',
  custom: 'orange',
};

// ─── 与后端 ALL_PERMISSIONS 一致的 20 个权限项 ───
const allPermissions = [
  'view_data', 'search_data', 'add_data', 'edit_data', 'delete_data',
  'add_field', 'edit_field', 'delete_field', 'batch_add_field',
  'import_excel', 'export_excel',
  'view_logs', 'export_logs', 'clear_logs',
  'audit_center', 'approve_reject',
  'manage_users', 'reset_database',
  'customize_theme', 'view_structure', 'view_stats',
];

const permissionLabels: Record<string, string> = {
  view_data: '查看数据',
  search_data: '搜索数据',
  add_data: '新增数据',
  edit_data: '编辑数据',
  delete_data: '删除数据',
  add_field: '添加字段',
  edit_field: '编辑字段配置',
  delete_field: '删除字段',
  batch_add_field: '批量添加字段',
  import_excel: '导入Excel',
  export_excel: '导出Excel',
  view_logs: '查看日志',
  export_logs: '导出日志',
  clear_logs: '清空日志',
  audit_center: '审核中心',
  approve_reject: '审核通过/驳回',
  manage_users: '管理用户',
  reset_database: '重置数据库',
  customize_theme: '自定义主题',
  view_structure: '查看数据结构',
  view_stats: '查看统计',
};

// ─── 各角色默认权限 ───
const bossPermissions = allPermissions;
const hrPermissions: string[] = [
  'view_data', 'search_data', 'add_data', 'edit_data',
  'add_field', 'batch_add_field', 'import_excel', 'export_excel',
  'view_logs', 'export_logs',
  'audit_center', 'approve_reject',
  'customize_theme', 'view_structure', 'view_stats',
];
const employeePermissions: string[] = [
  'view_data', 'search_data', 'view_logs', 'view_structure', 'customize_theme',
];

// ─── 根据权限集推断角色 ───
function inferRole(perms: string[]): UserRole {
  const set = new Set(perms);
  if (set.size === allPermissions.length && allPermissions.every(p => set.has(p))) return 'boss';
  if (employeePermissions.every(p => set.has(p)) &&
      set.size === employeePermissions.length) return 'employee';
  if (hrPermissions.every(p => set.has(p)) && !set.has('manage_users') && !set.has('reset_database') && !set.has('clear_logs')
      && !set.has('delete_field') && !set.has('delete_data')) {
    // HR 特征：有 audit_center、approve_reject，有 import/export/view_logs
    if (set.has('audit_center') && set.has('import_excel')) return 'hr';
  }
  // 更精确的 HR 判断
  const hrLike = hrPermissions.every(p => set.has(p));
  if (hrLike) return 'hr';
  return 'custom';
}

function Users() {
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const { isAdmin } = useRole();

  // Modal
  const [modalVisible, setModalVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [modalConfirmLoading, setModalConfirmLoading] = useState(false);
  const [form] = Form.useForm<UserFormValues>();

  // 当前选择的角色（用于联动权限）
  const [selectedRole, setSelectedRole] = useState<UserRole>('employee');

  // 查询用户列表
  const { data: users, isLoading } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: usersApi.getUsers,
  });

  // 显示所有用户（包括 boss）
  const filteredUsers = useMemo(() => {
    if (!users) return [];
    return users;
  }, [users]);

  // Mutations
  const createMutation = useMutation({
    mutationFn: usersApi.createUser,
    onSuccess: () => {
      messageApi.success('用户创建成功');
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setModalVisible(false);
      form.resetFields();
    },
    onError: () => messageApi.error('创建失败'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data: payload }: { id: number; data: Partial<UserFormValues> }) =>
      usersApi.updateUser(id, payload),
    onSuccess: () => {
      messageApi.success('用户更新成功');
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setModalVisible(false);
      form.resetFields();
    },
    onError: () => messageApi.error('更新失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: usersApi.deleteUser,
    onSuccess: () => {
      messageApi.success('用户已删除');
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: () => messageApi.error('删除失败'),
  });

  // ─── 角色切换：自动填充权限 ───
  const handleRoleChange = useCallback((role: string) => {
    setSelectedRole(role as UserRole);
    const perms =
      role === 'boss' ? bossPermissions :
      role === 'hr' ? hrPermissions :
      role === 'employee' ? employeePermissions :
      form.getFieldValue('permissions') || []; // 自定义保留当前
    form.setFieldsValue({ permissions: perms });
  }, [form]);

  // ─── 权限变更：自动推断角色 ───
  const handlePermissionsChange = useCallback((checkedValues: string[]) => {
    const inferred = inferRole(checkedValues);
    setSelectedRole(inferred);
    form.setFieldsValue({ role: inferred as any });
  }, [form]);

  // 打开新建 / 编辑
  const openCreateModal = () => {
    setEditingUser(null);
    form.resetFields();
    form.setFieldsValue({
      role: 'employee',
      permissions: employeePermissions,
      audit_enabled: false,
    });
    setSelectedRole('employee');
    setModalVisible(true);
  };

  const openEditModal = (user: User) => {
    setEditingUser(user);
    const perms = user.permissions ?? [];
    const role = inferRole(perms);
    setSelectedRole(role);
    form.setFieldsValue({
      username: user.username,
      role: role as UserRole,
      permissions: perms,
      audit_enabled: user.audit_enabled ?? false,
      password: undefined,
    });
    setModalVisible(true);
  };

  const handleModalOk = async () => {
    try {
      const values = await form.validateFields();
      setModalConfirmLoading(true);

      const payload: UserFormValues = {
        username: values.username,
        role: values.role,
        permissions: values.permissions ?? [],
        audit_enabled: values.audit_enabled ?? false,
      };
      if (values.password) {
        payload.password = values.password;
      }

      if (editingUser) {
        await updateMutation.mutateAsync({ id: editingUser.id, data: payload });
      } else {
        await createMutation.mutateAsync(payload);
      }
    } catch {
      // 校验失败
    } finally {
      setModalConfirmLoading(false);
    }
  };

  const handleModalCancel = () => {
    setModalVisible(false);
    form.resetFields();
  };

  // 表格列
  const columns: ColumnsType<User> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      width: 140,
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 100,
      render: (r: UserRole) => (
      <Tag color={roleColorMap[r] || 'default'}>{roleLabelMap[r] || r}</Tag>
      ),
    },
    {
      title: '权限',
      dataIndex: 'permissions',
      key: 'permissions',
      render: (perms: string[]) =>
        perms?.length
          ? perms.map((p) => (
              <Tag key={p} style={{ marginBottom: 4 }}>
                {permissionLabels[p] ?? p}
              </Tag>
            ))
          : '-',
    },
    {
      title: '审核开关',
      dataIndex: 'audit_enabled',
      key: 'audit_enabled',
      width: 90,
      align: 'center',
      render: (v: boolean) => (v ? <Tag color="green">开启</Tag> : <Tag>关闭</Tag>),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    ...(isAdmin
      ? [
          {
            title: '操作',
            key: 'action',
            width: 160,
            fixed: 'right' as const,
            render: (_: unknown, record: User) => (
              <Space size="small">
                <Button
                  type="link"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => openEditModal(record)}
                >
                  编辑
                </Button>
                <Popconfirm
                  title={`确定要删除用户「${record.username}」吗？`}
                  onConfirm={() => deleteMutation.mutate(record.id)}
                >
                  <Button
                    type="link"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                  >
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]
      : []),
  ] as ColumnsType<User>;

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
            用户管理
          </Title>
          <Space wrap>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => queryClient.invalidateQueries({ queryKey: ['users'] })}
            >
              刷新
            </Button>
            {isAdmin && (
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={openCreateModal}
                className="gradient-bg"
                style={{ border: 'none' }}
              >
                添加用户
              </Button>
            )}
          </Space>
        </div>

        <Spin spinning={isLoading}>
          <Table<User>
            columns={columns}
            dataSource={filteredUsers}
            rowKey="id"
            scroll={{ x: 900 }}
            size="middle"
            pagination={false}
          />
        </Spin>
      </Card>

      {/* 新增 / 编辑用户 */}
      <Modal
        title={editingUser ? '编辑用户' : '添加用户'}
        open={modalVisible}
        onOk={handleModalOk}
        onCancel={handleModalCancel}
        confirmLoading={modalConfirmLoading}
        destroyOnClose
        width={700}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 2, max: 32, message: '2-32 个字符' },
            ]}
          >
            <Input placeholder="用户名" disabled={!!editingUser} />
          </Form.Item>

          <Form.Item
            name="password"
            label={editingUser ? '新密码（留空不修改）' : '密码'}
            rules={
              editingUser
                ? undefined
                : [
                    { required: true, message: '请输入密码' },
                    { min: 6, message: '至少 6 个字符' },
                  ]
            }
          >
            <Input.Password placeholder="密码" />
          </Form.Item>

          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select options={roleOptions} onChange={handleRoleChange} />
          </Form.Item>

          <Form.Item
            name="permissions"
            label="权限（网格选择）"
            rules={[{ required: true, message: '请选择至少一项权限' }]}
          >
            <Checkbox.Group
              onChange={(vals) => handlePermissionsChange(vals as string[])}
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
                gap: '4px 8px',
              }}
            >
              {allPermissions.map((p) => (
                <Checkbox key={p} value={p}>
                  {permissionLabels[p] ?? p}
                </Checkbox>
              ))}
            </Checkbox.Group>
          </Form.Item>

          <Form.Item
            name="audit_enabled"
            label="全局审核（此用户所有操作需审核）"
            valuePropName="checked"
          >
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

export default Users;