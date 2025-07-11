<!-- src/layouts/AuthLayout.vue -->
<template>
  <div class="auth-layout">
    <router-view />
  </div>
</template>

<script setup>
// 这个布局很简单，甚至不需要 script 部分
</script>

<style scoped>
.auth-layout {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f0f2f5;
}
</style>
