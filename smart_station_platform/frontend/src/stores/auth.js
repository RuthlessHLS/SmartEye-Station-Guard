// src/stores/auth.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import router from '@/router';
import api from '@/api';


// localStorage key 定义
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY = 'user';

export const useAuthStore = defineStore('auth', () => {

  // 使用一个安全的函数来初始化 user state，防止 JSON 解析错误

  const getInitialUser = () => {
    const userStr = localStorage.getItem(USER_KEY);
    if (!userStr) return null;
    try {
      return JSON.parse(userStr);

      // 如果解析失败，说明数据已损坏，清除它

    } catch (_) {
      localStorage.removeItem(USER_KEY);
      return null;
    }
  };

  // State
  const token = ref(localStorage.getItem(ACCESS_TOKEN_KEY));
  const refreshToken = ref(localStorage.getItem(REFRESH_TOKEN_KEY));
  const user = ref(getInitialUser());


  // 刷新相关变量
  let isRefreshing = false;
  let failedQueue = [];


  // Computed

  const isAuthenticated = computed(() => !!token.value && !!user.value);
  const isAdmin = computed(() => user.value?.is_staff === true);
  const userId = computed(() => user.value?.id);


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


  // 设置认证数据
  // function setAuthData(accessToken, newRefreshToken, userData) {
  //   token.value = accessToken;
  //   localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  //   apiClient.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;

  function setAuthData(accessToken, newRefreshToken, userData) {
    token.value = accessToken;
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    api.backendService.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;


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
    delete api.backendService.defaults.headers.common['Authorization'];
  }

  // Actions
  async function login(credentials) {
    try {
      clearAuth();
      console.log('发送登录请求:', { ...credentials, password: '***' });

      // 发送登录请求
      const response = await api.auth.login(credentials);

      // 验证响应数据
      if (!response || !response.data || typeof response.data !== 'object') {
        throw new Error('无效的登录响应数据');
      }

      const { token, refresh_token, user } = response.data;

      // 验证必需的字段
      if (!token || !refresh_token || !user) {
        console.error('登录响应数据不完整:', response);
        throw new Error('登录响应数据不完整');
      }

      // 验证用户数据
      if (!user.id || !user.username) {
        console.error('用户数据不完整:', user);
        throw new Error('用户数据不完整');
      }

      // 设置认证数据和用户信息
      setAuthData(token, refresh_token, user);

      // 登录成功后跳转
      router.push('/dashboard');
    } catch (error) {
      console.error('登录失败:', error);
      let errorMessage = '登录失败，请重试';

      if (error.response) {
        const { status, data } = error.response;
        console.log('错误响应:', data);

        // 处理验证码相关错误
        if (data.captcha) {
          if (Array.isArray(data.captcha)) {
            errorMessage = data.captcha[0];
          } else {
            errorMessage = data.captcha;
          }
          throw new Error(errorMessage);
        }

        // 处理其他错误
        if (status === 401) {
          errorMessage = '用户名或密码错误';
        } else if (status === 400) {
          if (data.detail) {
            errorMessage = data.detail;
          } else if (data.non_field_errors) {
            errorMessage = data.non_field_errors[0];
          } else if (data.error) {
            errorMessage = data.error;
          } else {
            // 尝试获取第一个错误信息
            const firstError = Object.values(data)[0];
            errorMessage = Array.isArray(firstError) ? firstError[0] : '请求参数错误';
          }
        } else if (status === 500) {
          errorMessage = '服务器错误，请稍后重试';
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      throw new Error(errorMessage);
    }
  }

  function logout() {
    clearAuth();
    router.push('/login');
  }

  async function fetchUser() {
    if (!token.value) return;
    try {
      const response = await api.auth.getProfile();
      setAuthData(token.value, refreshToken.value, response.data);
    } catch (error) {
      console.error('获取用户信息失败:', error);
      // 静默清除认证数据，不自动跳转到登录页
      clearAuth();
    }
  }

  async function updateUserProfile(profileData) {
    const response = await api.auth.updateProfile(profileData);
    setAuthData(token.value, refreshToken.value, response.data);
  }

  async function changePassword(passwordData) {
    await api.auth.changePassword(passwordData);
  }

  // 初始化 Authorization header
  if (token.value) {
    api.backendService.defaults.headers.common['Authorization'] = `Bearer ${token.value}`;
    // 延迟验证token，避免应用启动时的401错误
    setTimeout(() => {
      if (token.value && !user.value) {
        fetchUser().catch(console.error);
      }
    }, 1000);
  }

  // 返回 store 对象

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

