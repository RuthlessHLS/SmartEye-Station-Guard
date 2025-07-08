import { createRouter, createWebHistory } from 'vue-router'
// 导入视图组件，这些文件你稍后会创建
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Dashboard from '../views/Dashboard.vue'
import MonitorCenter from '../views/MonitorCenter.vue'
import AlertManagement from '../views/AlertManagement.vue'
import DailyReport from '../views/DailyReport.vue'
import DataScreen from '../views/DataScreen.vue'
import UserManagement from '../views/UserManagement.vue'


const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: Login
    },
    {
      path: '/register',
      name: 'Register',
      component: Register
    },
    {
      path: '/',
      name: 'Dashboard',
      component: Dashboard,
      meta: { requiresAuth: true } // 需要认证
    },
    {
      path: '/monitor',
      name: 'MonitorCenter',
      component: MonitorCenter,
      meta: { requiresAuth: true }
    },
    {
      path: '/alerts',
      name: 'AlertManagement',
      component: AlertManagement,
      meta: { requiresAuth: true }
    },
    {
      path: '/reports',
      name: 'DailyReport',
      component: DailyReport,
      meta: { requiresAuth: true }
    },
    {
      path: '/data-screen',
      name: 'DataScreen',
      component: DataScreen,
      meta: { requiresAuth: true }
    },
    {
      path: '/users',
      name: 'UserManagement',
      component: UserManagement,
      meta: { requiresAuth: true }
    },
    // 添加一个 catch-all 路由进行重定向或 404
    {
      path: '/:catchAll(.*)',
      redirect: '/' // 默认重定向到主页
    }
  ]
})

// 导航守卫，用于验证用户是否已登录 (简化版)
router.beforeEach((to, from, next) => {
  const loggedIn = localStorage.getItem('access_token'); // 假设Token存储在localStorage
  if (to.meta.requiresAuth && !loggedIn && to.path !== '/login' && to.path !== '/register') {
    next('/login');
  } else {
    next();
  }
});

export default router
