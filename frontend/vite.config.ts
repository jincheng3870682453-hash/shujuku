import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            if (id.includes('echarts') || id.includes('zrender')) return 'echarts';
            if (id.includes('xlsx')) return 'xlsx';
            if (id.includes('antd') || id.includes('@ant-design') || id.includes('rc-')) return 'antd';
            return 'vendor';
          }
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: false,  // 端口被占用时自动尝试下一个可用端口
    open: false,  // 由启动脚本负责打开浏览器
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
      },
    },
  },
});