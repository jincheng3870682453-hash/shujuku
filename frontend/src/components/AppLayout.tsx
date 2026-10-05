import { useState, useEffect, useMemo } from 'react';
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom';
import { Layout, Menu, Dropdown, Avatar, Badge, App } from 'antd';
import {
  SearchOutlined,
  DatabaseOutlined,
  DownOutlined,
  TableOutlined,
  AppstoreOutlined,
  BarChartOutlined,
  AreaChartOutlined,
  RobotOutlined,
  AuditOutlined,
  FileTextOutlined,
  TeamOutlined,
  SaveOutlined,
  SettingOutlined,
  SafetyOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { authApi } from '../api/auth';
import type { UserThemePayload } from '../api/auth';
import { auditApi } from '../api/audit';
import type { MenuProps } from 'antd';

const { Content } = Layout;

/** 侧栏折叠态宽度（tokens.css 未定义折叠宽度，取 Airtable/Antd 默认 80px） */
const SIDEBAR_COLLAPSED_W = 80;

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

/** 读取分组项的子菜单（分组本身不参与权限判定，只由子项决定） */
/**
 * 菜单节点收窄形状。
 * AntD 的 MenuItem 是联合类型（含 MenuDividerType，它没有 key/label），
 * 直接取属性会报 TS2339，故在消费处用本类型收窄。
 */
type MenuNode = {
  key?: string | number | null;
  label?: React.ReactNode;
  children?: MenuNode[];
};

function groupChildren(item: MenuNode): MenuNode[] {
  const children = (item as { children?: MenuNode[] }).children;
  return Array.isArray(children) ? children.filter(Boolean) : [];
}

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

/**
 * 侧栏导航原始数据：Airtable 式两级结构
 * 一级 = 分组标题（数据 / 洞察 / 治理 / 系统），二级 = 具体页面
 */
const rawMenuItems: MenuProps['items'] = [
  {
    key: 'grp-data',
    type: 'group',
    label: '数据',
    children: [
      { key: '/database', icon: <TableOutlined />,    label: '数据管理' },
      { key: '/columns',  icon: <AppstoreOutlined />, label: '数据列表' },
    ],
  },
  {
    key: 'grp-insight',
    type: 'group',
    label: '洞察',
    children: [
      { key: '/stats',        icon: <BarChartOutlined />,   label: '数据总览' },
      { key: '/stats/charts', icon: <AreaChartOutlined />,  label: '图表分析' },
      { key: '/ai',           icon: <RobotOutlined />,      label: 'AI 分析' },
    ],
  },
  {
    key: 'grp-governance',
    type: 'group',
    label: '治理',
    children: [
      { key: '/audit',  icon: <AuditOutlined />,     label: '审核列表' },
      { key: '/logs',   icon: <FileTextOutlined />,  label: '审计日志' },
      { key: '/users',  icon: <TeamOutlined />,      label: '用户管理' },
      { key: '/backup', icon: <SaveOutlined />,      label: '备份管理' },
    ],
  },
  {
    key: 'grp-system',
    type: 'group',
    label: '系统',
    children: [
      { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
      { key: '/privacy',  icon: <SafetyOutlined />,  label: '隐私政策' },
    ],
  },
];

/** 路由 → 页面名，供顶栏面包屑使用（数据源仍是 rawMenuItems，避免重复维护） */
const PAGE_TITLES = ((rawMenuItems ?? []) as unknown as MenuNode[]).reduce<Record<string, string>>((acc, group) => {
  for (const leaf of groupChildren(group)) {
    if (!leaf || leaf.key === undefined || leaf.key === null) continue;
    acc[String(leaf.key)] = String(leaf.label ?? '');
  }
  return acc;
}, {});

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
  primaryColor: '#1b61c9', backgroundColor: '#f4f4f1', cardColor: '#ffffff', textColor: '#181d26', cardOpacity: 100,
};
/** 默认背景：跟随设计系统画布色（B 版为干净画布，不再叠加紫色光晕渐变） */
const DEFAULT_BG_GRADIENT = 'var(--surface-canvas)';

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

/** 角色中文名 */
function roleLabel(role?: string): string {
  return role === 'boss' ? '管理员' : role === 'hr' ? 'HR' : '普通用户';
}

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [openKeys, setOpenKeys] = useState<string[]>(loadSidebarOpenKeys);
  const [searchFocused, setSearchFocused] = useState(false);
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

  // 按权限过滤侧边栏菜单（子项全被过滤时整组隐藏）
  const menuGroups = useMemo(
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
          <div style={{ color: 'var(--ink-primary)', fontWeight: 500, fontSize: 'var(--fs-14)' }}>{user?.username || '用户'}</div>
          <div style={{ color: 'var(--ink-muted)', fontSize: 'var(--fs-12)', marginTop: 2 }}>
            {roleLabel(user?.role)}
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

  const handleOpenChange = (keys: string[]) => {
    setOpenKeys(keys);
    saveSidebarOpenKeys(keys);
  };

  const userName = user?.username || '用户';
  const userInitial = userName.charAt(0);
  const currentPageTitle = PAGE_TITLES[location.pathname] ?? '';

  const avatar = (
    <Avatar
      size={26}
      style={{
        background: 'var(--accent)',
        color: 'var(--ink-inverse)',
        fontSize: 'var(--fs-12)',
        fontWeight: 600,
        flex: 'none',
      }}
    >
      {userInitial}
    </Avatar>
  );

  const nameBlock = (
    <div style={{ minWidth: 0 }}>
      <div style={{
        color: 'var(--ink-primary)',
        fontSize: 'var(--fs-13)',
        fontWeight: 500,
        lineHeight: 1.15,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {userName}
      </div>
      <div style={{ color: 'var(--ink-muted)', fontSize: 'var(--fs-11)', lineHeight: 1.15 }}>
        {roleLabel(user?.role)}
      </div>
    </div>
  );

  return (
    <Layout
      style={{
        // 主区域 grid：顶栏整行 + （侧栏 | 内容），由内容区自身滚动，避免嵌套滚动条
        display: 'grid',
        gridTemplateColumns: collapsed ? `${SIDEBAR_COLLAPSED_W}px` : 'var(--sidebar-w)',
        gridTemplateRows: 'var(--topbar-h) 1fr',
        height: '100vh',
        overflow: 'hidden',
        transition: 'grid-template-columns 180ms var(--ease)',
      }}
    >
      {/* 顶栏 */}
      <header
        style={{
          gridColumn: '1 / -1',
          gridRow: '1',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-3)',
          height: 'var(--topbar-h)',
          padding: '0 var(--space-3)',
          background: 'var(--surface-base)',
          borderBottom: '1px solid var(--line-frame)',
        }}
      >
        <button
          type="button"
          aria-label={collapsed ? '展开侧栏' : '折叠侧栏'}
          onClick={() => setCollapsed(!collapsed)}
          style={{
            width: 28,
            height: 28,
            flex: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            background: 'transparent',
            color: 'var(--ink-muted)',
            cursor: 'pointer',
            transition: 'background var(--t-fast), color var(--t-fast)',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface-hover)'; e.currentTarget.style.color = 'var(--ink-primary)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--ink-muted)'; }}
        >
          {collapsed ? <MenuUnfoldOutlined style={{ fontSize: 15 }} /> : <MenuFoldOutlined style={{ fontSize: 15 }} />}
        </button>

        {/* 面包屑：工作区名 / 当前页面 */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-2)',
          minWidth: 0,
          fontSize: 'var(--fs-13)',
          color: 'var(--ink-muted)',
        }}>
          <span style={{ whiteSpace: 'nowrap' }}>动态数据登记系统</span>
          {currentPageTitle && (
            <>
              <span style={{ color: 'var(--line-frame)' }}>/</span>
              <b style={{
                color: 'var(--ink-primary)',
                fontSize: 'var(--fs-14)',
                fontWeight: 600,
                whiteSpace: 'nowrap',
              }}>
                {currentPageTitle}
              </b>
            </>
          )}
        </div>

        {/* 搜索框 */}
        <div
          style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
            width: 240,
            height: 28,
            flex: 'none',
            padding: '0 var(--space-2)',
            background: searchFocused ? 'var(--surface-base)' : 'var(--surface-sunken)',
            border: `1px solid ${searchFocused ? 'var(--accent)' : 'transparent'}`,
            borderRadius: 'var(--radius-md)',
            transition: 'background var(--t-fast), border-color var(--t-fast)',
          }}
        >
          <SearchOutlined style={{ fontSize: 13, color: 'var(--ink-muted)', flex: 'none' }} />
          <input
            placeholder="搜索记录、字段或申请人"
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setSearchFocused(false)}
            style={{
              flex: 1,
              minWidth: 0,
              border: 'none',
              outline: 'none',
              background: 'transparent',
              font: 'inherit',
              fontSize: 'var(--fs-13)',
              color: 'var(--ink-default)',
            }}
          />
        </div>

        {/* 待审核 */}
        {pendingCount > 0 && (
          <Badge count={pendingCount} size="small" offset={[-2, 2]}>
            <Link
              to="/audit"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                height: 28,
                padding: '0 var(--space-2)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--ink-default)',
                fontSize: 'var(--fs-13)',
                whiteSpace: 'nowrap',
              }}
            >
              <AuditOutlined style={{ fontSize: 15 }} />
              <span>待审核</span>
            </Link>
          </Badge>
        )}

        {/* 当前用户 */}
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={['click']}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              paddingLeft: 'var(--space-2)',
              borderLeft: '1px solid var(--line-soft)',
              cursor: 'pointer',
            }}
          >
            {avatar}
            {nameBlock}
          </div>
        </Dropdown>
      </header>

      {/* 侧边栏：Base 标识块 / 分组导航 / 用户区，三段纵向 flex */}
      <aside style={{
        gridColumn: '1',
        gridRow: '2',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        overflow: 'hidden',
        background: 'var(--surface-sunken)',
        borderRight: '1px solid var(--line-frame)',
      }}>
        {/* 工作区 / Base 标识块 */}
        <div style={{
          flex: 'none',
          padding: 'var(--space-3)',
          borderBottom: '1px solid var(--line-soft)',
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
            padding: 'var(--space-1) var(--space-2)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--surface-base)',
            border: '1px solid var(--line-soft)',
            cursor: 'default',
            justifyContent: collapsed ? 'center' : 'flex-start',
          }}>
            <span style={{
              width: 16,
              height: 16,
              flex: 'none',
              borderRadius: 'var(--radius-xs)',
              background: 'var(--accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--ink-inverse)',
            }}>
              {collapsed && <DatabaseOutlined style={{ fontSize: 10 }} />}
            </span>
            {!collapsed && (
              <>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{
                    display: 'block',
                    fontSize: 'var(--fs-13)',
                    fontWeight: 600,
                    color: 'var(--ink-primary)',
                    lineHeight: 1.3,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    动态数据登记系统
                  </span>
                  <span style={{
                    display: 'block',
                    fontSize: 'var(--fs-11)',
                    color: 'var(--ink-muted)',
                    lineHeight: 1.3,
                  }}>
                    登记库 · 动态字段
                  </span>
                </span>
                <DownOutlined style={{ fontSize: 10, color: 'var(--ink-muted)', flex: 'none' }} />
              </>
            )}
          </div>
        </div>

        {/* 分组导航：菜单自身滚动，不与底部用户区重叠 */}
        <div style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          overflowX: 'hidden',
          padding: 'var(--space-1) 0 var(--space-3)',
        }}>
          {menuGroups.map((group, gi) => {
            const g = group as unknown as MenuNode;
            return (
              <div key={String(g?.key ?? gi)}>
                {!collapsed && (
                  <div style={{
                    padding: 'var(--space-3) var(--space-3) var(--space-1)',
                    fontSize: 'var(--fs-11)',
                    fontWeight: 500,
                    color: 'var(--ink-muted)',
                    letterSpacing: '0.04em',
                  }}>
                    {g?.label}
                  </div>
                )}
                <Menu
                  mode="inline"
                  theme="light"
                  inlineCollapsed={collapsed}
                  selectedKeys={selectedKeys}
                  openKeys={openKeys}
                  onOpenChange={handleOpenChange}
                  items={groupChildren(g) as MenuProps['items']}
                  onClick={({ key }) => navigate(key)}
                  style={{
                    width: '100%',
                    minWidth: 0,
                    background: 'transparent',
                    borderInlineEnd: 'none',
                  }}
                />
              </div>
            );
          })}
        </div>

        {/* 底部用户区 */}
        <div style={{
          flex: 'none',
          padding: 'var(--space-2) var(--space-3)',
          borderTop: '1px solid var(--line-soft)',
        }}>
          <Dropdown menu={{ items: userMenuItems }} placement="topLeft" trigger={['click']}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              padding: 'var(--space-1)',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              justifyContent: collapsed ? 'center' : 'flex-start',
              transition: 'background var(--t-fast)',
            }}
              onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface-hover)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              {avatar}
              {!collapsed && nameBlock}
            </div>
          </Dropdown>
        </div>
      </aside>

      {/* 内容区：全幅贴边，自身滚动 */}
      <Content style={{
        gridColumn: '2',
        gridRow: '2',
        minHeight: 0,
        overflow: 'auto',
        padding: 'var(--space-4) var(--space-5)',
        background: 'var(--surface-base)',
        animation: 'fadeIn 200ms ease-out',
      }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
