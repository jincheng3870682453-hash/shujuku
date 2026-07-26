import client from './client';

export const authApi = {
  /** 登录 — 响应拦截器已解包，直接返回 body */
  login: (data: { username: string; password: string }): Promise<{ token: string; user: { id: number; username: string; role: string }; message: string }> =>
    client.post('/login', data),

  /** 获取当前用户信息 */
  me: (): Promise<{ logged_in: boolean; user_id: number; username: string; role: string; permissions?: string[]; global_audit?: boolean }> =>
    client.get('/me'),

  /** 退出登录 */
  logout: (): Promise<{ message: string }> =>
    client.post('/logout'),
};
