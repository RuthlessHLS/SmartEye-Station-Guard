// src/stores/auth.js (最终版，包含通用请求方法)

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import axios from 'axios';
import router from '@/router';

// 创建一个 Axios 实例 (保持私有，不直接导出)
const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
  timeout: 10000,
});

// ... (localStorage key 定义)
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY = 'user';


export const useAuthStore = defineStore('auth', () => {
  // ... (State 和刷新逻辑)
  const token = ref(localStorage.getItem(ACCESS_TOKEN_KEY));
  const refreshToken = ref(localStorage.getItem(REFRESH_TOKEN_KEY));
  const user = ref(JSON.parse(localStorage.getItem(USER_KEY) || 'null'));
  const isAuthenticated = computed(() => !!token.value && !!user.value);
  let isRefreshing = false;
  let failedQueue = [];

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

  // 创建一个通用的请求方法
  const request = (config) => {
    return apiClient(config);
  };

  // --- Actions ---
  async function login(credentials) {
    clearAuth();
    const response = await request({ method: 'post', url: '/users/token/', data: credentials });
    setAuthData(response.data.access, response.data.refresh);
    await fetchUser();
    router.push('/dashboard');
  }

  function logout() {
    clearAuth();
    router.push('/login');
  }

  async function fetchUser() {
    if (!token.value) return;
    try {
      const response = await request({ method: 'get', url: '/users/profile/' });
      setAuthData(token.value, refreshToken.value, response.data);
    } catch (error) {
      console.error('获取用户信息失败, Token可能已过期:', error);
      logout();
    }
  }

  async function updateUserProfile(profileData) {
    const response = await request({ method: 'patch', url: '/users/profile/', data: profileData });
    setAuthData(token.value, refreshToken.value, response.data);
  }

  async function changePassword(passwordData) {
    await request({ method: 'post', url: '/users/profile/change-password/', data: passwordData });
  }

  // --- Axios 拦截器 ---
  apiClient.interceptors.response.use(
    response => response,
    async (error) => {
      // ... 刷新逻辑 ...
       const originalRequest = error.config;

      if (error.response.status === 401 && originalRequest.url !== '/users/token/refresh/' && !originalRequest._retry) {

        if (isRefreshing) {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          }).then(newToken => {
            originalRequest.headers['Authorization'] = 'Bearer ' + newToken;
            return apiClient(originalRequest);
          });
        }

        originalRequest._retry = true;
        isRefreshing = true;

        try {
          const refreshResponse = await apiClient.post('/users/token/refresh/', {
            refresh: refreshToken.value,
          });

          const newAccessToken = refreshResponse.data.access;
          setAuthData(newAccessToken);
          originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`;
          processQueue(null, newAccessToken);
          return apiClient(originalRequest);

        } catch (refreshError) {
          console.error('无法刷新 Token:', refreshError);
          processQueue(refreshError, null);
          logout();
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      }
      return Promise.reject(error);
    }
  );

  if (token.value) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token.value}`;
  }

  return {
    token,
    user,
    isAuthenticated,
    // 导出 request 方法，不再导出 apiClient
    request,
    login,
    logout,
    fetchUser,
    updateUserProfile,
    changePassword,
  };
});
