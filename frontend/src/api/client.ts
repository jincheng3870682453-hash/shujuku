import axios from 'axios';

/**
 * 检测当前是否运行在 Electron 环境中
 */
const isElectron =
  typeof window !== 'undefined' &&
  typeof (window as unknown as Record<string, unknown>).electronAPI === 'object';

/**
 * 动态确定 API 基础 URL：
 * - Electron 环境：直接使用 localhost:5001/api（跨域，依赖后端 CORS）
 * - 浏览器开发环境：使用相对路径 /api（通过 Vite 代理，同源请求，session cookie 自动携带）
 */
const baseURL = isElectron
  ? 'http://localhost:5001/api'
  : '/api';

const client = axios.create({
  baseURL,
  timeout: 15000,
  withCredentials: true,  // 【修复】携带 cookie，Flask session 认证依赖此配置
  // 【修复】不设置默认 Content-Type，让 axios 自动判断：
  // - JSON 请求自动设为 application/json
  // - FormData 请求自动设为 multipart/form-data（带 boundary）
});

// 请求拦截器：自动附加 Token + 设置正确的 Content-Type
client.interceptors.request.use(
  (config) => {
    // 始终携带 token，后端 before_request 通过 Authorization header 恢复 session
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // 【修复】仅当 data 不是 FormData 时才设置 Content-Type 为 JSON
    // FormData 由浏览器自动设置正确的 multipart/form-data + boundary
    if (!(config.data instanceof FormData)) {
      config.headers['Content-Type'] = 'application/json';
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器：处理 401/403/500
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      const { status } = error.response;
      switch (status) {
        case 401:
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          window.location.href = '/login';
          break;
        case 403:
          console.error('权限不足');
          break;
        case 500:
          console.error('服务器错误');
          break;
      }
    }
    return Promise.reject(error);
  }
);

export default client;
