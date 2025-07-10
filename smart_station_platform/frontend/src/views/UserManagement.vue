<template>
  <div class="user-directory-container">
    <div class="header-bar">
      <h1>用户通讯录</h1>
      <!-- 搜索框 -->
      <div class="search-box">
        <el-input
          v-model="searchQuery"
          placeholder="搜索用户名、昵称、邮箱或电话"
          :prefix-icon="Search"
          clearable
          @input="handleSearch"
          @clear="fetchUsers"
          style="width: 300px"
        />
      </div>
    </div>

    <!-- 用户列表表格 -->
    <el-table :data="userList" v-loading="loading" style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" width="180" />
      <el-table-column prop="nickname" label="昵称" width="180" />
      <el-table-column prop="email" label="邮箱" width="220" />
      <el-table-column prop="phone_number" label="手机号" min-width="150" />
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { Search } from '@element-plus/icons-vue';
import axios from 'axios';
import _ from 'lodash'; // 引入 lodash 用于防抖

// --- API 客户端配置 (与之前相同) ---
const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000/api/users/',
});

apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, error => {
  return Promise.reject(error);
});

// --- 组件状态定义 ---
const userList = ref([]);
const loading = ref(true);
const searchQuery = ref('');

// --- API 调用函数 ---
const fetchUsers = async (query = '') => {
  loading.value = true;
  try {
    // 根据是否有查询参数来构建 URL
    const url = query ? `directory/?search=${query}` : 'directory/';
    const response = await apiClient.get(url);
    userList.value = response.data;
  } catch (error) {
    console.error('获取用户列表失败:', error);
    ElMessage.error('获取用户列表失败，请稍后重试。');
  } finally {
    loading.value = false;
  }
};

// --- 事件处理函数 ---
onMounted(() => {
  fetchUsers(); // 页面加载时获取全部用户
});

// 使用 lodash 的 debounce 函数创建一个防抖版的搜索处理函数
// 这可以防止用户每输入一个字符就发送一次 API 请求，优化性能
// 延迟 500 毫秒后执行
const handleSearch = _.debounce(() => {
  fetchUsers(searchQuery.value);
}, 500);

</script>

<style scoped>
.user-directory-container {
  padding: 20px;
}

.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

h1 {
  margin: 0;
  font-size: 24px;
}
</style>
