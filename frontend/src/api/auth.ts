import client from './client';

/** 用户自定义背景/主题（按用户隔离存储在后端） */
export interface UserThemePayload {
  /** 配色（primaryColor/backgroundColor/cardColor/textColor/cardOpacity） */
  theme?: {
    primaryColor?: string;
    backgroundColor?: string;
    cardColor?: string;
    textColor?: string;
    cardOpacity?: number;
  };
  /** 背景质感：glass/frosted/metallic/paper/neon/liquid-mesh/depth/flat/transparent */
  texture?: string;
  /** 玻璃透明度 0-1 */
  glass_alpha?: number;
  /** 霓虹品牌色：purple/cyan */
  neon_accent?: string;
  /** 背景图 base64，null 表示无 */
  bg_image?: string | null;
}

export const authApi = {
  /** 登录 — 响应拦截器已解包，直接返回 body */
  login: (data: { username: string; password: string }): Promise<{ token: string; user: { id: number; username: string; role: string }; message: string }> =>
    client.post('/login', data),

  /** 获取当前用户信息（含权限与自定义背景） */
  me: (): Promise<{ logged_in: boolean; user_id: number; username: string; role: string; permissions?: string[]; global_audit?: boolean; theme?: UserThemePayload | null }> =>
    client.get('/me'),

  /** 保存当前用户的自定义背景/主题（按用户隔离存储） */
  saveUserTheme: (payload: UserThemePayload): Promise<{ message: string; theme: UserThemePayload }> =>
    client.put('/theme', payload),

  /** 退出登录 */
  logout: (): Promise<{ message: string }> =>
    client.post('/logout'),
};
