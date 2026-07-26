import { useState, useEffect } from 'react';
import type { UserRole } from '../types/data';

interface UserInfo {
  username: string;
  role: UserRole;
}

/** 从 localStorage 解析当前用户信息 */
function parseUser(): UserInfo | null {
  try {
    const stored = localStorage.getItem('user');
    if (!stored) return null;
    return JSON.parse(stored) as UserInfo;
  } catch {
    return null;
  }
}

/**
 * 角色 & 权限 Hook
 * 注意：Login 成功后应同时写入 localStorage
 *   localStorage.setItem('user', JSON.stringify({ username, role }))
 */
export function useRole() {
  const [user, setUser] = useState<UserInfo | null>(null);

  useEffect(() => {
    setUser(parseUser());
  }, []);

  const isBoss = user?.role === 'boss';
  const isHr = user?.role === 'hr' || isBoss;
  const isEmployee = user?.role === 'employee';

  return {
    user,
    isBoss,
    isHr,
    isEmployee,
    /** boss 或 hr 可见 */
    canManage: isHr,
    /** 仅 boss 可见 */
    isAdmin: isBoss,
  };
}