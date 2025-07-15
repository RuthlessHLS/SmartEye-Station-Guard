import axios from 'axios';
import router from '../router';

// 后端API服务实例
const backendService = axios.create({
  baseURL: import.meta.env.VITE_APP_API_BASE_URL || 'http://127.0.0.1:8000',
  timeout: 30000, // 这里改成30000，表示30秒
});

// AI服务实例
const aiService = axios.create({
  baseURL: import.meta.env.VITE_APP_AI_SERVICE_URL || 'http://127.0.0.1:8001', // 修改为8001端口
  timeout: 30000, // AI服务可能需要更长的处理时间
});


// 请求重试配置
const retryConfig = {
  retries: 3,
  retryDelay: (retryCount) => {
    return retryCount * 1000; // 1s, 2s, 3s
  },
  retryCondition: (error) => {
    // 只在网络错误或特定HTTP状态码时重试
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
    // 添加API密钥
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
    if (response.config.url.includes('/token/')) {
      return response;
    }
    return response.data;
  },
  async error => {
    const originalRequest = error.config;
    
    // 网络错误处理
    if (!error.response) {
      console.error('Network error:', error.message);
      return Promise.reject(error);
    }

    // Token过期处理
    if (error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const res = await backendService.post('/api/token/refresh/', { refresh: refreshToken });
          const newAccessToken = res.data.access;
          localStorage.setItem('access_token', newAccessToken);
          originalRequest.headers['Authorization'] = 'Bearer ' + newAccessToken;
          return backendService(originalRequest);
        }
      } catch (refreshError) {
        console.error('Token refresh failed:', refreshError);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        router.push('/login');
        return Promise.reject(refreshError);
      }
    }

    // 其他错误处理
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
    // 处理AI服务特定错误
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
  get: (...args) => backendService.get(...args),
  post: (...args) => backendService.post(...args),
  patch: (...args) => backendService.patch(...args),
  delete: (...args) => backendService.delete(...args),
  // 告警相关接口
  alerts: {
    getList: (params) => backendService.get('/api/alerts/', { params }),
    getDetail: (id) => backendService.get(`/api/alerts/${id}/`),
    update: (id, data) => backendService.patch(`/api/alerts/${id}/`, data),
    delete: (id) => backendService.delete(`/api/alerts/${id}/`),
    handle: (id, data) => backendService.patch(`/api/alerts/${id}/handle/`, data), // 新增
  },
  // AI服务相关接口
  ai: {
    startStream: (data) => aiService.post('/stream/start/', data),
    stopStream: (cameraId) => aiService.post(`/stream/stop/${cameraId}`),
    analyzeFrame: (data) => aiService.post('/frame/analyze/', data),
  }
};

export { backendService, aiService, requestWithRetry };
export default api;
