<template>
  <div id="app-container">
    <!-- 仅在非登录/注册页面显示头部 -->
    <header v-if="!isAuthPage" class="app-header">
      <nav>
        <!-- 登录后显示的导航 -->
        <template v-if="authStore.isAuthenticated">
          <router-link to="/dashboard">首页</router-link>
          <router-link to="/monitor">智能监控</router-link>
          <router-link to="/ai-monitor">AI监控</router-link>
          <router-link to="/face-registration">人脸录入</router-link>
          <router-link to="/alerts">告警中心</router-link>
          <router-link to="/reports">AI日报</router-link>
          <router-link to="/data-screen">数据大屏</router-link>
          <router-link to="/users">用户管理</router-link>
        </template>

        <!-- [修改点] 这个 spacer 元素不再需要了 -->
        <!-- <div class="nav-spacer"></div> -->

        <!-- 根据登录状态显示右侧内容 -->
        <template v-if="authStore.isAuthenticated">
          <!-- 这里可以放个人中心下拉菜单 -->
          <span class="welcome-user">欢迎, {{ authStore.user?.nickname || authStore.user?.username }}</span>
          <a href="#" @click.prevent="handleLogout" class="logout-link">退出登录</a>
        </template>
        <template v-else>
          <!-- 未登录时显示 -->
          <router-link to="/login">登录</router-link>
          <router-link to="/register">注册</router-link>
        </template>
      </nav>
    </header>

    <main class="app-main" :class="{ 'full-screen': isAuthPage }">
      <router-view />
    </main>

    <footer v-if="!isAuthPage" class="app-footer">
      <p>© 2025 智慧车站智能监控与大数据分析平台</p>
    </footer>
  </div>
</template>

<script setup>
// script 部分保持不变
import { computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { ElMessageBox, ElMessage } from 'element-plus';

const route = useRoute();
const authStore = useAuthStore();

const isAuthPage = computed(() => route.name === 'Login' || route.name === 'Register');

const handleLogout = () => {
  ElMessageBox.confirm('您确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    authStore.logout();
    ElMessage.success('已安全退出！');
  }).catch(() => {});
};

onMounted(() => {
  if (authStore.token && !authStore.user) {
    authStore.fetchUser();
  }
});
</script>

<!-- ====================================================== -->
<!-- =============  CSS 修改的核心在这里  =============== -->
<!-- ====================================================== -->
<style scoped>
#app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  font-family: Avenir, Helvetica, Arial, sans-serif;
  color: #2c3e50;
}
.app-header {
  background-color: #ffffff;
  padding: 0 40px; /* 增加左右内边距，让整体不那么靠边 */
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}
.app-header nav {
  display: flex;
  align-items: center;
  height: 64px; /* 可以适当增加导航栏高度 */

  /* 【核心修改1】使用 space-between 来实现两端对齐的均匀分布 */
  justify-content: space-between;
}
.app-header nav a {
  color: #303133;
  text-decoration: none;
  font-weight: 500;
  padding: 0 10px; /* 调整内边距 */

  /* 【核心修改2】增大字体大小 */
  font-size: 16px; /* 或者 1.1em, 1rem 等 */
}
.app-header nav a.router-link-exact-active {
  color: #409eff;
}

/* 【核心修改3】右侧的用户信息和登出链接组合在一起 */
.app-header nav .welcome-user,
.app-header nav .logout-link {
  /* 让它们在 flex 布局中表现得像一个整体 */
  margin-left: 20px;
  white-space: nowrap; /* 防止 "欢迎, xxx" 文字换行 */
}

.welcome-user {
  color: #606266;
  font-size: 15px; /* 可以单独调整字体大小 */
}
.logout-link {
  color: #F56C6C;
  font-size: 15px;
}
.app-main {
  flex-grow: 1;
  padding: 20px;
  background-color: #f0f2f5;
}
.app-main.full-screen { padding: 0; }
.app-footer {
  background-color: #f0f2f5;
  color: #909399;
  padding: 15px;
  text-align: center;
}
</style>
