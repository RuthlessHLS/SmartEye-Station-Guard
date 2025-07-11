<!-- src/views/UserManagement.vue (使用 Pinia Store) -->
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
          @input="debouncedSearch"
          @clear="clearSearch"
          style="width: 300px"
        />
      </div>
    </div>

    <!-- 用户列表表格 -->
    <!-- v-loading 直接绑定 store.loading -->
    <el-table :data="store.users" v-loading="store.loading" style="width: 100%" border>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" width="180" />
      <el-table-column prop="nickname" label="昵称" width="180" />
      <el-table-column prop="email" label="邮箱" width="220" />
      <el-table-column prop="phone_number" label="手机号" min-width="150" />
    </el-table>

    <!-- 错误状态显示 -->
    <div v-if="store.error" class="error-state">
      <p>{{ store.error }}</p>
      <el-button @click="retryFetch" type="primary">重试</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { Search } from '@element-plus/icons-vue';
import _ from 'lodash'; // 引入 lodash 用于防抖

// 1. 引入并使用 userManagement store
import { useUserManagementStore } from '@/stores/userManagement';

// --- 初始化 Store ---
const store = useUserManagementStore();

// --- 组件本地状态 ---
const searchQuery = ref('');

// --- 事件处理函数 ---

// 页面加载时获取全部用户
onMounted(() => {
  store.fetchUsers();
});

// [核心修改] 2. 创建一个防抖函数，它会调用 store.fetchUsers
const debouncedSearch = _.debounce(() => {
  store.fetchUsers(searchQuery.value);
}, 500); // 延迟 500ms

// 清除搜索框时，重新获取全部用户
const clearSearch = () => {
  store.fetchUsers();
};

// 错误状态下的重试按钮
const retryFetch = () => {
  store.fetchUsers(searchQuery.value);
};

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

.error-state {
  text-align: center;
  margin-top: 40px;
  color: #f56c6c;
}
</style>
