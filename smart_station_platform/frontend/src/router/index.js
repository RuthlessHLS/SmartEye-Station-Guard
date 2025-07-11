import { createRouter, createWebHistory } from 'vue-router';

// 导入所有需要的视图组件
import Login from '../views/Login.vue';
import Register from '../views/Register.vue';
import Dashboard from '../views/Dashboard.vue';
import MonitorCenter from '../views/MonitorCenter.vue';
import AIVideoMonitor from '../views/AIVideoMonitor.vue';
import AlertManagement from '../views/AlertManagement.vue';
import DailyReport from '../views/DailyReport.vue';
import DataScreen from '../views/DataScreen.vue';
import UserManagement from '../views/UserManagement.vue';
import UserProfile from '../views/UserProfile.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // --- 根路径重定向 ---
    {
      path: '/',
      redirect: '/dashboard'
    },

    // --- 认证相关路由 (使用 AuthLayout，无导航栏) ---
    {
      path: '/login',
      name: 'Login',
      component: Login,
      meta: {
        requiresAuth: false,
        layout: 'auth' // 指定使用 auth 布局
      }
    },
    {
      path: '/register',
      name: 'Register',
      component: Register,
      meta: {
        requiresAuth: false,
        layout: 'auth' // 指定使用 auth 布局
      }
    },

    // --- 主应用路由 (使用默认的 MainLayout，有白色导航栏) ---
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: Dashboard,
      meta: { requiresAuth: true } // layout 未指定，将使用 'default' (MainLayout)
    },
    {
      path: '/monitor',
      name: 'MonitorCenter',
      component: MonitorCenter,
      meta: { requiresAuth: true }
    },
    {
      path: '/ai-monitor',
      name: 'AIVideoMonitor',
      component: AIVideoMonitor,
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
      path: '/profile',
      name: 'UserProfile',
      component: UserProfile,
      meta: { requiresAuth: true }
    },
    {
      path: '/users',
      name: 'UserManagement',
      component: UserManagement,
      meta: { requiresAuth: true }
    },

    // --- 捕获所有未匹配的路由 ---
    {
      // 确保这个路由在列表的最后
      path: '/:catchAll(.*)',
      redirect: '/dashboard'
    }
  ]
});

// 导航守卫保持不变，它的逻辑非常完善，无需修改
router.beforeEach((to, from, next) => {
  // 使用 '!!' 将字符串转换为布尔值，更严谨
  const loggedIn = !!localStorage.getItem('access_token');
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

export default router;
