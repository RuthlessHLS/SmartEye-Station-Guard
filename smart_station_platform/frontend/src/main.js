import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

// 可选：屏蔽过量 console.log 调试输出（根据环境变量 VITE_SUPPRESS_CONSOLE 控制）
import './utils/suppressLogs.js'

// Element Plus 导入
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css' // Element Plus 样式

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus) // 使用 Element Plus

app.mount('#app')
