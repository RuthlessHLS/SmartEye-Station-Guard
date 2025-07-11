import axios from 'axios';
import router from '../router';

// 后端API服务实例
const backendService = axios.create({
  baseURL: import.meta.env.VITE_APP_API_BASE_URL || 'http://127.0.0.1:8000',
  timeout: 10000,
});

// AI服务实例
const aiService = axios.create({
  baseURL: import.meta.env.VITE_APP_AI_SERVICE_URL || 'http://127.0.0.1:8001',
  timeout: 30000,  // 增加超时时间到30秒
});

// 请求重试配置
const retryConfig = {
  retries: 3,
  retryDelay: (retryCount) => {
    return retryCount * 1000;
  },
  retryCondition: (error) => {
    return axios.isAxiosError(error) && (
      !error.response ||
      [408, 500, 502, 503, 504].includes(error.response.status)
    );
  }
};

// 请求拦截器 - 后端服务
backendService.interceptors.request.use(
  config => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers['Authorization'] = 'Bearer ' + token;
    }
    return config;
  },
  error => {
    console.error('Request error:', error);
    return Promise.reject(error);
  }
);

// 请求拦截器 - AI服务
aiService.interceptors.request.use(
  config => {
    config.headers['X-API-Key'] = import.meta.env.VITE_APP_AI_SERVICE_API_KEY;
    return config;
  },
  error => {
    console.error('AI service request error:', error);
    return Promise.reject(error);
  }
);

// 响应拦截器 - 后端服务
backendService.interceptors.response.use(
  response => {
    if (response.config.url.includes('/login/') || response.config.url.includes('/token/refresh/')) {
      return response;
    }
    return response.data;
  },
  async error => {
    const originalRequest = error.config;
    
    if (!error.response) {
      console.error('Network error:', error.message);
      return Promise.reject(error);
    }

    if (error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const res = await backendService.post('/api/users/token/refresh/', { refresh: refreshToken });
          if (res.data && res.data.access) {
            localStorage.setItem('access_token', res.data.access);
            originalRequest.headers['Authorization'] = 'Bearer ' + res.data.access;
            return backendService(originalRequest);
          }
        }
      } catch (refreshError) {
        console.error('Token refresh failed:', refreshError);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        router.push('/login');
        return Promise.reject(refreshError);
      }
    }

    if (error.response.status >= 500) {
      console.error('Server error:', error.response.data);
    }
    return Promise.reject(error);
  }
);

// 响应拦截器 - AI服务
aiService.interceptors.response.use(
  response => response.data,
  async error => {
    if (!error.response) {
      console.error('AI service connection error:', error.message);
    } else if (error.response.status === 401) {
      console.error('AI service authentication failed');
    } else if (error.response.status >= 500) {
      console.error('AI service error:', error.response.data);
    }
    return Promise.reject(error);
  }
);

// 工具函数：带重试的请求
const requestWithRetry = async (service, config) => {
  let retries = retryConfig.retries;
  
  while (retries > 0) {
    try {
      return await service(config);
    } catch (error) {
      retries--;
      if (retries === 0 || !retryConfig.retryCondition(error)) {
        throw error;
      }
      await new Promise(resolve => 
        setTimeout(resolve, retryConfig.retryDelay(retryConfig.retries - retries))
      );
    }
  }
};

// 默认导出API服务对象
const api = {
  // 用户认证相关接口
  auth: {
    login: (data) => backendService.post('/api/users/login/', data),
    register: (data) => backendService.post('/api/users/register/', data),
    refreshToken: (data) => backendService.post('/api/users/token/refresh/', data),
    getProfile: () => backendService.get('/api/users/profile/'),
    updateProfile: (data) => backendService.patch('/api/users/profile/', data),
    changePassword: (data) => backendService.post('/api/users/change-password/', data),
    getCaptcha: () => backendService.get('/api/users/captcha/generate/'),
  },
  // 告警相关接口
  alerts: {
    getList: (params) => backendService.get('/api/alerts/', { params }),
    getDetail: (id) => backendService.get(`/api/alerts/${id}/`),
    create: (data) => backendService.post('/api/alerts/', data),
    update: (id, data) => backendService.patch(`/api/alerts/${id}/`, data),
    delete: (id) => backendService.delete(`/api/alerts/${id}/`),
    handle: (id, data) => backendService.patch(`/api/alerts/${id}/handle/`, data),
  },
  // AI服务相关接口
  ai: {
    startStream: (data) => aiService.post('/stream/start/', data),
    stopStream: () => aiService.post('/stream/stop/'),  // 添加末尾斜杠
    testStreamConnection: (data) => aiService.post('/stream/test/', {  // 添加末尾斜杠
      url: data.url,
      type: data.type
    }),
    analyzeFrame: (data) => aiService.post('/frame/analyze/', data),
    getStreamStatus: () => aiService.get('/system/status/'),
  }
};

export { backendService, aiService, requestWithRetry };
export default api;
