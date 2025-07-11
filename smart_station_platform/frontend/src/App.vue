<!-- App.vue (修改为布局切换器) -->
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

  <component :is="layout">
    <router-view />
  </component>

</template>

<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import MainLayout from './layouts/MainLayout.vue';
import AuthLayout from './layouts/AuthLayout.vue';

const route = useRoute();

// 定义布局映射
const layouts = {
  default: MainLayout,
  auth: AuthLayout,
};

// 计算属性，根据当前路由的 meta.layout 返回对应的布局组件
// 如果没有指定布局，则使用 'default' 布局 (MainLayout)
const layout = computed(() => {
  const layoutName = route.meta.layout || 'default';
  return layouts[layoutName];
});
</script>

<style>
/* 全局样式可以放在这里，或者在 main.css 中 */
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}
</style>
