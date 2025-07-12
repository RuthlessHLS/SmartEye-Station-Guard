<!-- App.vue (修改为布局切换器) -->
<template>
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
