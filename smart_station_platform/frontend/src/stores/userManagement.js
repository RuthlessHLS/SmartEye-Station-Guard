// src/stores/userManagement.js

import { defineStore } from 'pinia';
import { ref } from 'vue';
import { backendService as apiClient } from '@/api';
import { useAuthStore } from './auth';

export const useUserManagementStore = defineStore('userManagement', () => {
  const users = ref([]);
  const loading = ref(false);
  const error = ref(null);

  async function fetchUsers(query = '') {
    loading.value = true;
    error.value = null;
    try {
      const url = query ? `/api/users/directory/?search=${query}` : '/api/users/directory/';

      // 使用 apiClient 发送请求
      const response = await apiClient.get(url);
      
      // 检查响应数据结构
      if (Array.isArray(response)) {
        users.value = response;
      } else if (response.results) {
        users.value = response.results;
      } else {
        console.error('Unexpected response format:', response);
        error.value = '服务器返回的数据格式不正确';
      }

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
