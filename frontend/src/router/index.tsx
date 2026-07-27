import { createBrowserRouter, Navigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import AuthGuard from '../components/AuthGuard';
import Login from '../pages/Login';
import DataTable from '../pages/DataTable';
import Columns from '../pages/Columns';
import Stats from '../pages/Stats';
import Charts from '../pages/Charts';
import Audit from '../pages/Audit';
import Logs from '../pages/Logs';
import Users from '../pages/Users';
import Backup from '../pages/Backup';
import Settings from '../pages/Settings';
import AIAnalysis from '../pages/AIAnalysis';
import PrivacyPolicy from '../pages/PrivacyPolicy';

// 【修复】/login 路由独立于受保护的主布局之外
// 【修复】用 AuthGuard 包裹需要登录才能访问的所有页面
const router = createBrowserRouter([
  // 登录页：独立路由，无需登录即可访问
  { path: '/login', element: <Login /> },
  // 主界面：全部受 AuthGuard 保护
  {
    path: '/',
    element: (
      <AuthGuard>
        <AppLayout />
      </AuthGuard>
    ),
    children: [
      { index: true, element: <Navigate to="/database" replace /> },
      { path: 'database', element: <DataTable /> },
      { path: 'columns', element: <Columns /> },
      { path: 'stats', element: <Stats /> },
      { path: 'stats/charts', element: <Charts /> },
      { path: 'audit', element: <Audit /> },
      { path: 'logs', element: <Logs /> },
      { path: 'users', element: <Users /> },
      { path: 'backup', element: <Backup /> },
      { path: 'settings', element: <Settings /> },
      { path: 'ai', element: <AIAnalysis /> },
      { path: 'privacy', element: <PrivacyPolicy /> },
    ],
  },
]);

export default router;
