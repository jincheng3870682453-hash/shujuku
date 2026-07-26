import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider, App } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import router from './router';
import antdTheme from './styles/theme';
import './index.css';

// ── 启动时加载用户自定义颜色，覆盖设计令牌（Linear 暗色主题） ──
(function initColorOverrides() {
  try {
    const saved = localStorage.getItem('ui_colors');
    if (!saved) return;
    const c = JSON.parse(saved) as Record<string, string>;
    const set = (k: string, v: string) => v && document.documentElement.style.setProperty(k, v);
    set('--accent-default', c.primaryColor);
    set('--accent-hover', c.accentHover || c.primaryColor);
    set('--accent-active', c.accentActive || c.primaryColor);
    set('--surface-root', c.backgroundColor);
    set('--surface-card', c.cardColor);
    set('--text-primary', c.textColor);
  } catch {
    /* ignore */
  }
})();

// ── 启动时加载背景质感设置 ──
(function initTexture() {
  try {
    const texture = localStorage.getItem('dashboard_texture') || 'glass';
    // 双属性同步：data-texture + data-theme
    document.documentElement.setAttribute('data-texture', texture);
    document.documentElement.setAttribute('data-theme', texture);

    // 玻璃透明度（仅 Glass 质感下生效）
    const glassAlpha = localStorage.getItem('glass_alpha');
    if (glassAlpha !== null) {
      document.documentElement.style.setProperty('--tx-glass-alpha', glassAlpha);
    }

    // 霓虹品牌色（仅霓虹质感使用）
    const accent = localStorage.getItem('neon_accent');
    if (accent === 'cyan') {
      document.documentElement.setAttribute('data-neon-accent', 'cyan');
    }
  } catch {
    document.documentElement.setAttribute('data-texture', 'glass');
    document.documentElement.setAttribute('data-theme', 'glass');
  }
})();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30000,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={zhCN} theme={antdTheme}>
        <App>
          <RouterProvider router={router} />
        </App>
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
