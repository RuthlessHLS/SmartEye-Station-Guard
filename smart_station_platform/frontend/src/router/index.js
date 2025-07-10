import { createRouter, createWebHistory } from 'vue-router'
// 导入视图组件
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
      component: Login,
      // [改进 2] 为公共路由添加 meta 字段，让逻辑更清晰
      meta: { requiresAuth: false }
    },
    {
      path: '/register',
      name: 'Register',
      component: Register,
      // [改进 2]
      meta: { requiresAuth: false }
    },
    {
      // [改进 3] 将根路径重定向放到路由列表的开头，更清晰
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/dashboard', // 将 Dashboard 作为一个具体的路径
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
    {
      // 捕获所有未匹配的路由
      path: '/:catchAll(.*)',
      redirect: '/dashboard' // 重定向到主仪表盘
    }
  ]
})

// [改进 1 & 2] 优化后的导航守卫
router.beforeEach((to, from, next) => {
  const loggedIn = localStorage.getItem('access_token');
  const requiresAuth = to.meta.requiresAuth;

  if (requiresAuth && !loggedIn) {
    // 情况 1: 访问受保护的页面，但未登录 -> 跳转到登录页
    next('/login');
  } else if (!requiresAuth && loggedIn && (to.name === 'Login' || to.name === 'Register')) {
    // 情况 2: 已登录，但试图访问登录/注册页 -> 跳转到主仪表盘
    next({ name: 'Dashboard' });
  } else {
    // 情况 3: 其他所有情况 (已登录访问受保护页，未登录访问公共页) -> 正常放行
    next();
  }
});

export default router
