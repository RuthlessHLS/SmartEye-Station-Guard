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
  optimizeDeps: { // 确保这里添加了
    include: [
      'echarts',
      'mapbox-gl',
      'element-plus',
    ],
  },
})
