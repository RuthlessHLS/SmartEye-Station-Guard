import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    https: false,
    cors: true,
    hmr: {
      host: 'localhost',
      protocol: 'ws',
      clientPort: 5174
    },
    host: '0.0.0.0',
    port: 5174,
    strictPort: true,
    // 添加historyApiFallback配置
    open: false,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ai': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ai/, '')
      }
    }
  },
  // 确保build输出正确处理路由
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // 添加rollupOptions以支持客户端路由
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'element-plus': ['element-plus'],
          'video-player': ['flv.js', 'hls.js', 'dplayer']
        }
      }
    }
  },
  // 添加历史模式回退配置
  experimental: {
    renderBuiltUrl(filename, { hostType }) {
      if (hostType === 'js') {
        return { runtime: `window.__publicPath + ${JSON.stringify(filename)}` };
      }
      return { relative: true };
    }
  },
  optimizeDeps: {
    include: [
      'element-plus',
      'flv.js',
      'hls.js',
      'video.js',
      'vue',
      'vue-router',
      'pinia'
    ]
  }
})
