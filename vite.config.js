import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': '/src'
    }
  },
  server: {
    host: '0.0.0.0', // 允许通过IP地址访问
    port: 5174,
    proxy: {
      // 代理后端API请求
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // 代理AI服务API请求
      '/ai-api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ai-api/, '') // 移除前缀
      },
      // 代理WebSocket连接
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
      }
    }
  }
}) 