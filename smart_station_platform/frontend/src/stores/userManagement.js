// src/stores/userManagement.js

import { defineStore } from 'pinia';
import { ref } from 'vue';
import { useAuthStore } from './auth';

export const useUserManagementStore = defineStore('userManagement', () => {
  const users = ref([]);
  const loading = ref(false);
  const error = ref(null);

  async function fetchUsers(query = '') {
    // 1. 获取 auth store 实例
    const authStore = useAuthStore();
    // 2. 从 auth store 中获取 request 函数
    const request = authStore.request;

    loading.value = true;
    error.value = null;
    try {
      const url = query ? `/users/directory/?search=${query}` : '/users/directory/';

      // 3. 使用 request 函数发送请求
      const response = await request({ method: 'get', url: url });

      users.value = response.data.results || response.data;

    } catch (err) {
      console.error('获取用户列表失败:', err);
      error.value = '无法加载用户数据，请稍后重试。';
    } finally {
      loading.value = false;
    }
  }

  return {
    users,
    loading,
    error,
    fetchUsers,
  };
});
