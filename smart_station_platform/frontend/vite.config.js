import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 导入按需引入的插件
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'


// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // 配置 AutoImport 插件
    AutoImport({
      resolvers: [ElementPlusResolver()], // 解析 Element Plus 组件
    }),
    // 配置 Components 插件
    Components({
      resolvers: [ElementPlusResolver()], // 解析 Element Plus 组件
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    // 添加HTTPS支持
    https: false, // 如果需要HTTPS，设置为true
    // 允许使用不安全的请求
    cors: true,
    // 允许在非HTTPS环境下使用摄像头
    hmr: {
      host: 'localhost',
    },
    host: '0.0.0.0',
    port: 5174,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // 不要重写路径，保留/api前缀
      },
      '/ai': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ai/, '')
      }
    }
  },
  optimizeDeps: { // 确保这里添加了
    include: [
      'echarts',
      'mapbox-gl',
      'element-plus',
    ],
  },
})
