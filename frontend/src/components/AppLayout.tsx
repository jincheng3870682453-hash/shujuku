import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom';
import { Layout, Menu, Button, Typography, Dropdown, Avatar, Badge, App } from 'antd';
import {
  DatabaseOutlined,
  BarChartOutlined,
  AuditOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  AppstoreOutlined,
  TableOutlined,
  TeamOutlined,
  SaveOutlined,
  RobotOutlined,
  SafetyOutlined,
} from '@ant-design/icons';
import { authApi } from '../api/auth';
import { auditApi } from '../api/audit';
import type { MenuProps } from 'antd';

const { Sider, Content } = Layout;
const { Text } = Typography;

interface UserInfo {
  id?: number;
  username?: string;
  role?: string;
}

const menuItems: MenuProps['items'] = [
  {
    key: 'stats-group',
    icon: <BarChartOutlined />,
    label: '统计看板',
    children: [
      { key: '/stats',        label: '数据总览' },
      { key: '/stats/charts', label: '图表分析' },
    ],
  },
  { key: '/database', icon: <TableOutlined />,      label: '数据管理' },
  { key: '/columns',  icon: <AppstoreOutlined />,   label: '数据列表' },
  {
    key: 'audit-group',
    icon: <AuditOutlined />,
    label: '审核中心',
    children: [
      { key: '/audit',     label: '审核列表' },
      { key: '/logs',       label: '审计日志' },
    ],
  },
  { key: '/users',    icon: <TeamOutlined />,    label: '用户管理' },
  { key: '/backup',   icon: <SaveOutlined />,    label: '备份管理' },
  { key: '/ai',       icon: <RobotOutlined />,   label: 'AI 分析' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
  { key: '/privacy',  icon: <SafetyOutlined />,  label: '隐私政策' },
];

// 从 localStorage 读取侧边栏子菜单展开状态
function loadSidebarOpenKeys(): string[] {
  try {
    const raw = localStorage.getItem('sidebar_open_keys');
    if (raw) return JSON.parse(raw) as string[];
  } catch {}
  return []; // 默认全部收起
}

function saveSidebarOpenKeys(keys: string[]) {
  try {
    localStorage.setItem('sidebar_open_keys', JSON.stringify(keys));
  } catch {}
}

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [openKeys, setOpenKeys] = useState<string[]>(loadSidebarOpenKeys);
  const navigate = useNavigate();
  const location = useLocation();
  const { message } = App.useApp();

  // 获取用户信息
  useEffect(() => {
    authApi.me().then(res => {
      setUser({ id: res.user_id, username: res.username, role: res.role });
    }).catch(() => navigate('/login'));
  }, [navigate]);

  // 获取待审核数量
  useEffect(() => {
    if (!user) return;
    auditApi.getCount().then(res => {
      if (res?.pending) setPendingCount(res.pending);
    }).catch(() => {});
  }, [user]);

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch { /* ignore */ }
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    message.success('已退出登录');
    navigate('/login', { replace: true });
  };

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'info',
      label: (
        <div style={{ padding: '4px 0' }}>
          <div style={{ color: 'var(--text-primary)', fontWeight: 500, fontSize: 14 }}>{user?.username || '用户'}</div>
          <div style={{ color: 'var(--text-tertiary)', fontSize: 12, marginTop: 2 }}>
            {user?.role === 'boss' ? '管理员' : '普通用户'}
          </div>
        </div>
      ),
      disabled: true,
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
      onClick: handleLogout,
    },
  ];

  // 计算选中菜单
  const selectedKeys = [location.pathname];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 侧边栏 */}
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={220}
        style={{
          background: 'var(--surface-carbon)',
          borderRight: 'var(--border-subtle)',
          overflow: 'hidden',
        }}
      >
        {/* Logo 区域 */}
        <div style={{
          height: 52,
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          borderBottom: 'var(--border-subtle)',
          gap: 10,
        }}>
          <div style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            background: 'rgba(94,106,210,0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            <DatabaseOutlined style={{ fontSize: 15, color: 'var(--brand-accent)' }} />
          </div>
          {!collapsed && (
            <Text strong style={{ color: 'var(--text-primary)', fontSize: 15, letterSpacing: '-0.01em' }}>
              数据登记系统
            </Text>
          )}
        </div>

        {/* 导航菜单 */}
        <Menu
          mode="inline"
          selectedKeys={selectedKeys}
          openKeys={openKeys}
          onOpenChange={(keys) => {
            setOpenKeys(keys);
            saveSidebarOpenKeys(keys);
          }}
          inlineCollapsed={collapsed}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            background: 'transparent',
            border: 'none',
            paddingTop: 8,
            paddingBottom: 8,
          }}
          theme="dark"
        />

        {/* 底部用户区 */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          padding: '12px 16px',
          borderTop: 'var(--border-subtle)',
          background: 'var(--surface-carbon)',
        }}>
          {collapsed ? (
            <Dropdown menu={{ items: userMenuItems }} placement="topRight" trigger={['click']}>
              <div style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: 'rgba(94,106,210,0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                margin: '0 auto',
              }}>
                <UserOutlined style={{ color: 'var(--brand-accent)', fontSize: 16 }} />
              </div>
            </Dropdown>
          ) : (
            <Dropdown menu={{ items: userMenuItems }} placement="topRight" trigger={['click']}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '6px 10px',
                borderRadius: 8,
                cursor: 'pointer',
                transition: 'background 120ms ease',
              }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(94,106,210,0.06)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <Avatar size={32} icon={<UserOutlined />} style={{ background: 'rgba(94,106,210,0.15)', flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {user?.username || '用户'}
                  </div>
                  <div style={{ color: 'var(--text-tertiary)', fontSize: 11 }}>
                    {user?.role === 'boss' ? '管理员' : '普通用户'}
                  </div>
                </div>
              </div>
            </Dropdown>
          )}
        </div>
      </Sider>

      {/* 主内容区 */}
      <Layout>
        {/* 顶栏 */}
        <div style={{
          height: 48,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          background: 'var(--surface-void)',
          borderBottom: 'var(--border-subtle)',
          flexShrink: 0,
        }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{
              color: 'var(--text-secondary)',
              width: 34,
              height: 34,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {pendingCount > 0 && (
              <Link to="/audit">
                <Badge count={pendingCount} size="small" offset={[-2, 4]}>
                  <Button type="text" icon={<AuditOutlined />} style={{ color: 'var(--text-secondary)' }}>
                    待审核
                  </Button>
                </Badge>
              </Link>
            )}
          </div>
        </div>

        {/* 内容 */}
        <Content style={{
          padding: 24,
          overflow: 'auto',
          height: 'calc(100vh - 48px)',
          animation: 'fadeIn 200ms ease-out',
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
