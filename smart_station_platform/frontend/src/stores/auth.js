// src/stores/auth.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import router from '@/router';
import { backendService as apiClient } from '@/api';

// localStorage key 定义
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY = 'user';

export const useAuthStore = defineStore('auth', () => {
  // 使用一个安全的函数来初始化 user state
  const getInitialUser = () => {
    const userStr = localStorage.getItem(USER_KEY);
    if (!userStr) return null;
    try {
      return JSON.parse(userStr);
    } catch (_) {
      localStorage.removeItem(USER_KEY);
      return null;
    }
  };

  // State
  const token = ref(localStorage.getItem(ACCESS_TOKEN_KEY));
  const refreshToken = ref(localStorage.getItem(REFRESH_TOKEN_KEY));
  const user = ref(getInitialUser());
  let isRefreshing = false;
  let failedQueue = [];

  // Computed
  const isAuthenticated = computed(() => !!token.value && !!user.value);
  const isAdmin = computed(() => user.value?.is_staff === true);
  const userId = computed(() => user.value?.id);

  // Helpers
  const processQueue = (error, newToken = null) => {
    failedQueue.forEach(prom => {
      if (error) {
        prom.reject(error);
      } else {
        prom.resolve(newToken);
      }
    });
    failedQueue = [];
  };

  function setAuthData(accessToken, newRefreshToken, userData) {
    token.value = accessToken;
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;

    if (newRefreshToken) {
      refreshToken.value = newRefreshToken;
      localStorage.setItem(REFRESH_TOKEN_KEY, newRefreshToken);
    }
    if (userData) {
      user.value = userData;
      localStorage.setItem(USER_KEY, JSON.stringify(userData));
    }
  }

  function clearAuth() {
    token.value = null;
    refreshToken.value = null;
    user.value = null;
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    delete apiClient.defaults.headers.common['Authorization'];
  }

  // Actions
  async function login(credentials) {
    try {
      clearAuth();
      console.log('发送登录请求:', { ...credentials, password: '***' });
      const response = await apiClient.post('/api/users/login/', credentials);
      
      console.log('登录响应数据:', response.data);
      
      // 检查响应数据
      if (!response.data) {
        throw new Error('无效的登录响应数据');
      }

      // 检查响应数据结构
      const { token, refresh_token, user: userData } = response.data;
      console.log('解析的数据:', { token, refresh_token, userData });

      if (!token) {
        throw new Error('未收到访问令牌');
      }

      // 设置认证数据和用户信息
      setAuthData(token, refresh_token, userData);
      router.push('/dashboard');
    } catch (error) {
      console.error('登录失败:', error);
      if (error.response) {
        console.error('错误响应:', error.response.data);
        console.error('状态码:', error.response.status);
      }
      throw error;
    }
  }

  function logout() {
    clearAuth();
    router.push('/login');
  }

  async function fetchUser() {
    if (!token.value) return;
    try {
      const response = await apiClient.get('/api/users/profile/');
      setAuthData(token.value, refreshToken.value, response.data);
    } catch (error) {
      console.error('获取用户信息失败:', error);
      logout();
    }
  }

  async function updateUserProfile(profileData) {
    const response = await apiClient.patch('/api/users/profile/', profileData);
    setAuthData(token.value, refreshToken.value, response.data);
  }

  async function changePassword(passwordData) {
    await apiClient.post('/api/users/change-password/', passwordData);
  }

  // 初始化 Authorization header
  if (token.value) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token.value}`;
    // 如果有 token，尝试获取用户信息
    fetchUser().catch(console.error);
  }

  return {
    token,
    user,
    isAuthenticated,
    isAdmin,
    userId,
    login,
    logout,
    fetchUser,
    updateUserProfile,
    changePassword,
  };
});

