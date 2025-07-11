
import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue'
import AboutView from '../views/AboutView.vue'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Dashboard from '../views/Dashboard.vue'
import AIVideoMonitor from '../views/AIVideoMonitor.vue'
import AlertManagement from '../views/AlertManagement.vue'
import DailyReport from '../views/DailyReport.vue'
import DataScreen from '../views/DataScreen.vue'
import UserManagement from '../views/UserManagement.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/about',
      name: 'about',
      component: AboutView,
      meta: { layout: 'default', requiresAuth: true }
    },
    {
      path: '/login',
      name: 'login',
      component: Login,
      meta: { layout: 'auth' }
    },
    {
      path: '/register',
      name: 'register',
      component: Register,
      meta: { layout: 'auth' }
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: Dashboard,
      meta: { layout: 'default', requiresAuth: true }
    },
    {
      path: '/ai-video-monitor',
      name: 'ai-video-monitor',
      component: AIVideoMonitor,
      meta: { layout: 'default', requiresAuth: true }
    },
    {
      path: '/alert-management',
      name: 'alert-management',
      component: AlertManagement,
      meta: { layout: 'default', requiresAuth: true }
    },
    {
      path: '/daily-report',
      name: 'daily-report',
      component: DailyReport,
      meta: { layout: 'default', requiresAuth: true }
    },
    {
      path: '/data-screen',
      name: 'data-screen',
      component: DataScreen,
      meta: { layout: 'default', requiresAuth: true }
    },
    {
      path: '/user-management',
      name: 'user-management',
      component: UserManagement,
      meta: { layout: 'default', requiresAuth: true }
    }
  ]
})

// 全局前置守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)

  // 如果路由需要认证
  if (requiresAuth) {
    // 检查是否已登录
    if (!authStore.isAuthenticated) {
      // 未登录则重定向到登录页
      next({
        path: '/login',
        query: { redirect: to.fullPath } // 保存原本要去的路径
      })
    } else {
      // 已登录则允许访问
      next()
    }
  } else {
    // 不需要认证的路由直接放行
    next()
  }
})

export default router
