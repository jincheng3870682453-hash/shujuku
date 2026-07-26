import { Navigate, useLocation } from 'react-router-dom';

/**
 * 路由守卫组件
 * - 检查 localStorage 中是否存在 token
 * - 未登录 → 重定向到 /login
 * - 已登录 → 正常渲染子组件
 */
function AuthGuard({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const token = localStorage.getItem('token');

  if (!token) {
    // 将当前访问的路径作为 redirect 参数传递，登录后可回跳
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}

export default AuthGuard;