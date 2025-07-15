// src/stores/userManagement.js

import { defineStore } from 'pinia';
import { ref } from 'vue';
import api from '@/api';
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
      const response = await api.auth.getUsers(url);
      
      // 检查响应数据结构（response现在直接是数据，不需要.data）
      if (!response) {
        throw new Error('无效的响应数据');
      }

      // 处理不同的响应数据格式
      if (Array.isArray(response)) {
        users.value = response;
      } else if (response.results && Array.isArray(response.results)) {
        users.value = response.results;
      } else if (response.data && Array.isArray(response.data)) {
        users.value = response.data;
      } else {
        console.log('实际响应数据结构:', response);
        throw new Error('服务器返回的数据格式不正确');
      }

    } catch (err) {
      console.error('获取用户列表失败:', err);
      error.value = err.message || '无法加载用户数据，请稍后重试。';
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

