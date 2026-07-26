import client from './client';
import type { User, UserFormValues } from '../types/data';

export const usersApi = {
  /** 获取用户列表 */
  getUsers: (): Promise<User[]> => client.get('/users'),

  /** 创建用户 */
  createUser: (data: UserFormValues): Promise<{ message: string; user: User }> =>
    client.post('/users', data),

  /** 更新用户 */
  updateUser: (id: number, data: Partial<UserFormValues>): Promise<{ message: string; user: User }> =>
    client.put(`/users/${id}`, data),

  /** 删除用户 */
  deleteUser: (id: number): Promise<{ message: string }> =>
    client.delete(`/users/${id}`),
};