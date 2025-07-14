<!-- src/layouts/MainLayout.vue -->
<template>
  <div class="main-layout">
    <header class="main-header">
      <div class="logo">
        <img :src="logoUrl" alt="Logo" class="logo-img" />
        <span class="logo-text">智慧车站监控平台</span>
      </div>
      <nav class="main-nav">
        <router-link to="/dashboard">首页</router-link>
        <router-link to="/ai-monitor">AI监控</router-link>
        <router-link to="/face-registration">人脸录入</router-link>
        <router-link to="/alerts">告警中心</router-link>
        <router-link to="/reports">AI日报</router-link>
        <router-link to="/data-screen">数据大屏</router-link>
        <router-link to="/face-registration">人脸录入</router-link>
        <router-link to="/users">用户管理</router-link>
      </nav>
      <div class="user-profile-section">
        <el-dropdown v-if="authStore.isAuthenticated" trigger="click">
          <span class="el-dropdown-link">
            <el-avatar v-if="authStore.user?.avatar" :src="authStore.user.avatar" size="small"></el-avatar>
            <span v-else class="username">{{ authStore.user?.nickname || authStore.user?.username }}</span>
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="goToProfile">个人中心</el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <template v-else>
          <router-link to="/login" class="login-link">登录</router-link>
          <router-link to="/register" class="register-link">注册</router-link>
        </template>
      </div>
    </header>

    <main class="main-content">
      <slot></slot>
    </main>

    <footer class="main-footer">
      <p>© 2025 智慧车站智能监控与大数据分析平台</p>
    </footer>
  </div>
</template>

<script setup>
import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'vue-router';
import { ArrowDown } from '@element-plus/icons-vue';
import myLogo from '@/assets/my-logo.png';

const authStore = useAuthStore();
const router = useRouter();
const logoUrl = myLogo;

const goToProfile = () => {
  router.push('/profile');
};

const handleLogout = () => {
  authStore.logout();
};
</script>

<style scoped>
.main-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: #f0f2f5;
}

.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 64px;
  background-color: #ffffff;
  border-bottom: 1px solid #f0f0f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  position: sticky;
  top: 0;
  z-index: 100;
}

.logo {
  display: flex;
  align-items: center;
}

.logo-img {
  height: 32px;
  margin-right: 12px;
}

.logo-text {
  font-size: 20px;
  font-weight: 600;
  color: #1f2d3d;
}

.main-nav {
  display: flex;
  align-items: center;
  gap: 20px;
}

.main-nav a {
  color: #333;
  text-decoration: none;
  padding: 0 4px 8px 4px;
  border-bottom: 2px solid transparent;
  transition: all 0.3s;
  font-weight: 500;
}

.main-nav a:hover {
  color: #409eff;
}

.main-nav a.router-link-active {
  color: #409eff;
  border-bottom-color: #409eff;
}

.user-profile-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-profile-section .el-dropdown-link {
  cursor: pointer;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
}

.login-link,
.register-link {
  color: #333;
  text-decoration: none;
  padding: 6px 12px;
  border-radius: 4px;
  transition: all 0.3s;
}

.login-link:hover,
.register-link:hover {
  color: #409eff;
  background-color: rgba(64, 158, 255, 0.1);
}

.main-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.main-footer {
  text-align: center;
  padding: 15px;
  color: #888;
  background-color: #fff;
  border-top: 1px solid #f0f0f0;
}
</style>
