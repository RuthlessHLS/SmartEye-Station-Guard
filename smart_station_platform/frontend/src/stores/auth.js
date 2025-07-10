// src/stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios' // 假设你使用axios
import router from '@/router' // 引入router

// 创建一个 Axios 实例，方便统一配置
const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000/api' // 你的后端API地址
})

export const useAuthStore = defineStore('auth', () => {
  // 从 localStorage 初始化 token
  const token = ref(localStorage.getItem('accessToken'))
  const user = ref(null)

  // 计算属性，判断是否已登录
  const isAuthenticated = computed(() => !!token.value)

  // 设置 token 并存储到 localStorage
  function setToken(accessToken) {
    token.value = accessToken
    localStorage.setItem('accessToken', accessToken)
    // 为后续所有请求设置 Authorization 头
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`
  }

  // 清除 token
  function clearToken() {
    token.value = null
    user.value = null
    localStorage.removeItem('accessToken')
    delete apiClient.defaults.headers.common['Authorization']
  }

  // 登录操作
  async function login(credentials) {
    try {
      // credentials 包含 username, password, captcha_key, captcha_position
      const response = await apiClient.post('/users/token/', credentials)
      setToken(response.data.access) // simple-jwt 返回 access 和 refresh
      // 可以在这里再请求一次用户信息
      await fetchUser()
      // 登录成功后跳转到主面板
      router.push('/dashboard')
    } catch (error) {
      console.error('登录失败:', error.response.data)
      // 抛出错误，让组件可以处理UI提示
      throw error
    }
  }

  // 获取用户信息
  async function fetchUser() {
    if (isAuthenticated.value) {
      try {
        const response = await apiClient.get('/users/profile/')
        user.value = response.data
      } catch (error) {
        console.error('获取用户信息失败:', error)
        // token 可能失效，执行登出
        logout()
      }
    }
  }

  // 登出操作
  function logout() {
    clearToken()
    // 跳转到登录页
    router.push('/login')
  }

  // 应用加载时，如果存在token，则自动设置请求头
  if (token.value) {
     apiClient.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    logout,
    fetchUser,
    apiClient // 导出 apiClient 供其他地方使用
  }
})
