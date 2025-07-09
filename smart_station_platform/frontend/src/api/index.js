import axios from 'axios';
import router from '../router'; // 引入Vue Router实例

const service = axios.create({
  baseURL: import.meta.env.VITE_APP_API_BASE_URL || 'http://127.0.0.1:8000', // 基础URL，不包含/api
  timeout: 10000, // 请求超时时间
});

// 请求拦截器
service.interceptors.request.use(
  config => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers['Authorization'] = 'Bearer ' + token; // 让每个请求携带JWT Token
    }
    return config;
  },
  error => {
    console.log(error); // for debug
    return Promise.reject(error);
  }
);

// 响应拦截器
service.interceptors.response.use(
  response => {
    // 如果是登录或刷新token的响应，直接返回完整的response
    if (response.config.url.includes('/token/')) {
      return response;
    }
    return response.data;
  },
  async error => {
    const originalRequest = error.config;
    // 如果是 401 (未授权) 并且不是刷新 token 的请求，尝试刷新 token
    if (error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          // 尝试向后端刷新 Token 的接口发送请求
          const res = await service.post('/token/refresh/', { refresh: refreshToken });
          const newAccessToken = res.data.access;
          localStorage.setItem('access_token', newAccessToken); // 更新存储的 access_token
          // 重新设置授权头，然后重新发送原始请求
          originalRequest.headers['Authorization'] = 'Bearer ' + newAccessToken;
          return service(originalRequest); // 重新发送原始请求
        }
      } catch (refreshError) {
        console.error('Refresh token failed:', refreshError);
        // 刷新 token 失败，清除旧 token 并跳转到登录页
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        router.push('/login'); // 使用导入的router实例跳转到登录页
        return Promise.reject(refreshError);
      }
    }
    console.log('err' + error); // for debug
    return Promise.reject(error);
  }
);

export default service;
