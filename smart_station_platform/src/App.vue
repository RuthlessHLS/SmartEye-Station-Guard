<template>
  <div id="app-container">
    <header class="app-header">
      <nav>
        <router-link to="/">首页</router-link>
        <router-link to="/monitor">智能监控</router-link>
        <router-link to="/alerts">告警中心</router-link>
        <router-link to="/reports">AI日报</router-link>
        <router-link to="/data-screen">数据大屏</router-link>
        <router-link to="/users">用户管理</router-link>
        <router-link to="/login">登录</router-link>
        <router-link to="/register">注册</router-link>
      </nav>
    </header>

    <main class="app-main">
      <router-view />
    </main>

    <footer class="app-footer">
      <p>&copy; 2025 智慧车站智能监控与大数据分析平台</p>
    </footer>
  </div>
</template>

<script setup>
// App.vue 根组件通常不需要太多逻辑，主要用于路由视图的显示
</script>

<style scoped>
#app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh; /* 最小高度占满视口 */
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
}

.app-header {
  background-color: #42b983;
  padding: 15px;
  color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.app-header nav {
  display: flex;
  justify-content: center;
  gap: 20px;
}

.app-header nav a {
  color: white;
  text-decoration: none;
  font-weight: bold;
  padding: 5px 10px;
  border-radius: 4px;
  transition: background-color 0.3s ease;
}

.app-header nav a:hover,
.app-header nav a.router-link-active {
  background-color: #35a476;
}

.app-main {
  flex-grow: 1; /* 占据剩余空间 */
  padding: 20px;
  background-color: #f0f2f5;
}

.app-footer {
  background-color: #333;
  color: white;
  padding: 10px;
  font-size: 0.8em;
  box-shadow: 0 -2px 4px rgba(0, 0, 0, 0.1);
}
</style>
