// src/stores/auth.js

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import axios from 'axios';
import router from '@/router';

// 创建一个 Axios 实例
const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000/api'
});

// [修复] 将 localStorage 的 key 定义为常量，确保全局统一
const ACCESS_TOKEN_KEY = 'access_token';
const USER_KEY = 'user';

export const useAuthStore = defineStore('auth', () => {
  // [修复] 使用一个安全的函数来初始化 user state，防止 JSON 解析错误
  const getInitialUser = () => {
    const userStr = localStorage.getItem(USER_KEY);
    if (!userStr) return null;
    try {
      return JSON.parse(userStr);
    } catch (e) {
      // 如果解析失败，说明数据已损坏，清除它
      localStorage.removeItem(USER_KEY);
      return null;
    }
  };

  // State: 从 localStorage 初始化 token 和 user
  const token = ref(localStorage.getItem(ACCESS_TOKEN_KEY));
  const user = ref(getInitialUser());

  // [修复] isAuthenticated 必须同时依赖 token 和 user
  const isAuthenticated = computed(() => !!token.value && !!user.value);

  // Actions
  function setToken(accessToken) {
    token.value = accessToken;
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;
  }

  // [修复] 增加 setUser 函数，用于存储用户信息到 state 和 localStorage
  function setUser(userData) {
    user.value = userData;
    localStorage.setItem(USER_KEY, JSON.stringify(userData));
  }

  function clearAuth() {
    token.value = null;
    user.value = null;
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    delete apiClient.defaults.headers.common['Authorization'];
  }

  async function fetchUser() {
    // [修复] 只要有 token 就应该尝试获取用户信息
    if (token.value) {
      try {
        const response = await apiClient.get('/users/profile/');
        // [修复] 使用 setUser 函数来存储用户信息
        setUser(response.data);
      } catch (error) {
        console.error('获取用户信息失败, Token可能已过期，将自动登出:', error);
        logout();
      }
    }
  }

  async function login(credentials) {
    clearAuth(); // 先清除旧数据
    try {
      const response = await apiClient.post('/users/token/', credentials);
      setToken(response.data.access);
      // [修复] 登录成功后，必须立即获取用户信息
      await fetchUser();
      // 只有在 token 和 user 都获取成功后才跳转
      router.push('/dashboard');
    } catch (error) {
      console.error('登录失败:', error.response?.data || error);
      throw error;
    }
  }

  function logout() {
    clearAuth();
    router.push('/login');
  }

  // 应用初始化时，如果存在token，则自动设置请求头
  if (token.value) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token.value}`;
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    logout,
    fetchUser,
    apiClient,
  };
});
