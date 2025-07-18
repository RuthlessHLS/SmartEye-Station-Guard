
import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { setupHistoryFallback } from './history-fallback'

// 导入视图组件
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Dashboard from '../views/Dashboard.vue'
import AIVideoMonitor from '../views/AIVideoMonitor.vue'
import AlertManagement from '../views/AlertManagement.vue'
import DailyReport from '../views/DailyReport.vue'
import DataScreen from '../views/DataScreen.vue'
import UserManagement from '../views/UserManagement.vue'
import UserProfile from '../views/UserProfile.vue'
import FaceRegistration from '../views/FaceRegistration.vue'
import FaceLogin from '../views/FaceLogin.vue'
import VideoReplay from '../views/VideoReplay.vue'


const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
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
    {
      path: '/face-login',
      name: 'FaceLogin',
      component: FaceLogin,
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
      path: '/ai-monitor',
      name: 'AIVideoMonitor',
      component: AIVideoMonitor,
      meta: { requiresAuth: true }
    },
    {
      path: '/face-registration',
      name: 'FaceRegistration',
      component: FaceRegistration,
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
    {
      path: '/replay',
      name: 'VideoReplay',
      component: VideoReplay,
      meta: { requiresAuth: true }
    },

    // --- 捕获所有未匹配的路由 ---
    {
      path: '/:catchAll(.*)',
      redirect: '/dashboard'
    }
  ]
});

// 导航守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();
  const requiresAuth = to.meta.requiresAuth;

  if (requiresAuth && !authStore.isAuthenticated) {
    next('/login');
  } else if (!requiresAuth && authStore.isAuthenticated && (to.name === 'Login' || to.name === 'Register')) {
    next({ name: 'Dashboard' });
  } else {
    next();
  }
});

// 应用历史模式回退处理
export default setupHistoryFallback(router);
