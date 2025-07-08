import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

// Element Plus 导入
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css' // Element Plus 样式

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus) // 使用 Element Plus

app.mount('#app')
