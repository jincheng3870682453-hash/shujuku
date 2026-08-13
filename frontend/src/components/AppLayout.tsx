import { useState, useEffect, useMemo } from 'react';
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
import type { UserThemePayload } from '../api/auth';
import { auditApi } from '../api/audit';
import type { MenuProps } from 'antd';

const { Sider, Content } = Layout;
const { Text } = Typography;

interface UserInfo {
  id?: number;
  username?: string;
  role?: string;
  permissions?: string[];
}

/** 每个菜单项所需权限；未列出的菜单项视为所有登录用户可见 */
const MENU_PERMISSION: Record<string, string> = {
  '/stats':        'view_stats',
  '/stats/charts': 'view_stats',
  '/database':     'view_data',
  '/columns':      'view_structure',
  '/audit':        'audit_center',
  '/logs':         'view_logs',
  '/users':        'manage_users',
  '/backup':       'reset_database',
  '/ai':           'view_data',
  '/settings':     'customize_theme',
};

type MenuItem = NonNullable<MenuProps['items']>[number];

/** 根据权限过滤菜单项（子菜单全被过滤时整组隐藏） */
function filterMenuByPermissions(
  items: MenuItem[] | undefined,
  permissions: string[],
): MenuItem[] {
  if (!items) return [];
  const result: MenuItem[] = [];
  for (const item of items) {
    if (!item) continue;
    // 仅对带 children 的普通菜单项递归过滤，divider 等特殊类型直接跳过
    if ('children' in item && Array.isArray(item.children)) {
      const filteredChildren = filterMenuByPermissions(
        item.children as MenuItem[],
        permissions,
      );
      if (filteredChildren.length > 0) {
        result.push({ ...item, children: filteredChildren } as MenuItem);
      }
    } else if (item.key !== undefined && item.key !== null) {
      const required = MENU_PERMISSION[String(item.key)];
      if (!required || permissions.includes(required)) {
        result.push(item);
      }
    }
  }
  return result;
}

const rawMenuItems: MenuProps['items'] = [
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

const DEFAULT_THEME_COLORS = {
  primaryColor: '#5e6ad2', backgroundColor: '#08090a', cardColor: '#0f1011', textColor: '#e5e5e6', cardOpacity: 80,
};
const DEFAULT_BG_GRADIENT = [
  'radial-gradient(ellipse 80% 50% at 20% 0%, rgba(124,58,237,0.12), transparent)',
  'radial-gradient(ellipse 60% 40% at 80% 100%, rgba(59,130,246,0.08), transparent)',
  '#0A0A0F',
].join(',');

/**
 * 登录后应用该用户在后端保存的自定义背景/主题。
 * 切换用户时会整体覆盖为当前用户自己的背景；无自定义时重置为系统默认。
 */
function applySavedUserTheme(saved: UserThemePayload | null | undefined) {
  const root = document.documentElement;
  // 配色
  const theme = { ...DEFAULT_THEME_COLORS, ...(saved?.theme || {}) } as Record<string, string | number>;
  root.style.setProperty('--accent-default', String(theme.primaryColor));
  root.style.setProperty('--surface-root', String(theme.backgroundColor));
  root.style.setProperty('--surface-card', String(theme.cardColor));
  root.style.setProperty('--text-primary', String(theme.textColor));
  localStorage.setItem('theme', JSON.stringify(theme));
  localStorage.setItem('ui_colors', JSON.stringify(theme));
  // 玻璃透明度
  const alpha = saved?.glass_alpha ?? Number(theme.cardOpacity) / 100;
  root.style.setProperty('--tx-glass-alpha', String(alpha));
  localStorage.setItem('glass_alpha', String(alpha));
  // 背景质感
  const texture = saved?.texture || 'glass';
  root.setAttribute('data-texture', texture);
  root.setAttribute('data-theme', texture);
  localStorage.setItem('dashboard_texture', texture);
  // 背景图（玻璃/透明质感下展示）
  const bg = saved?.bg_image || null;
  if (bg) {
    localStorage.setItem('bg_image', bg);
  } else {
    localStorage.removeItem('bg_image');
  }
  document.body.style.background = '';
  if (texture === 'glass' || texture === 'transparent') {
    document.body.style.background = bg ? `url(${bg}) center / cover no-repeat fixed` : DEFAULT_BG_GRADIENT;
  }
  // 霓虹品牌色
  const neon = saved?.neon_accent || 'purple';
  if (neon === 'cyan') {
    root.setAttribute('data-neon-accent', 'cyan');
  } else {
    root.removeAttribute('data-neon-accent');
  }
  localStorage.setItem('neon_accent', neon);
  // 淡入过渡
  root.classList.add('texture-transitioning');
  setTimeout(() => root.classList.remove('texture-transitioning'), 150);
}

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [openKeys, setOpenKeys] = useState<string[]>(loadSidebarOpenKeys);
  const navigate = useNavigate();
  const location = useLocation();
  const { message } = App.useApp();

  // 获取用户信息（含权限列表与自定义背景）
  useEffect(() => {
    authApi.me().then(res => {
      setUser({
        id: res.user_id,
        username: res.username,
        role: res.role,
        permissions: Array.isArray(res.permissions) ? res.permissions : [],
      });
      // 应用该用户自己的背景/主题（切换用户即切换背景）
      applySavedUserTheme(res.theme);
    }).catch(() => navigate('/login'));
  }, [navigate]);

  // 按权限过滤侧边栏菜单
  const menuItems = useMemo(
    () => filterMenuByPermissions(rawMenuItems, user?.permissions ?? []),
    [user?.permissions],
  );

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
            {user?.role === 'boss' ? '管理员' : user?.role === 'hr' ? 'HR' : '普通用户'}
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
                    {user?.role === 'boss' ? '管理员' : user?.role === 'hr' ? 'HR' : '普通用户'}
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
