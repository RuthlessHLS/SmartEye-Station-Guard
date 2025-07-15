import axios from 'axios';
import router from '../router';

// 后端API服务实例
const backendService = axios.create({
  baseURL: import.meta.env.VITE_APP_API_BASE_URL || 'http://127.0.0.1:8000',
  timeout: 10000,
  withCredentials: true, // 允许跨域请求携带凭证
});

// AI服务实例
const aiService = axios.create({
  baseURL: import.meta.env.VITE_APP_AI_SERVICE_URL || 'http://127.0.0.1:8002', // <-- 【修复】修正AI服务的正确端口
  timeout: 120000,  // 增加超时时间到120秒
  withCredentials: false, // AI服务不需要携带凭证
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
    // 每次请求时重新从localStorage获取最新的token
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
    // 对于登录、刷新令牌和验证码请求，直接返回响应
    if (response.config.url.includes('/login/') || 
        response.config.url.includes('/token/refresh/') ||
        response.config.url.includes('/captcha/generate/')
    ) {
      return response;
    }
    return response.data;
  },
  async error => {
    const originalRequest = error.config;
    
    if (!error.response) {
      console.error('网络错误:', error.message);
      error.message = '网络连接错误，请检查网络后重试';
      return Promise.reject(error);
    }

    // 处理401错误（未授权）
    if (error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          // 临时移除拦截器，避免无限递归
          const response = await axios.post(
            (import.meta.env.VITE_APP_API_BASE_URL || 'http://127.0.0.1:8000') + '/api/users/token/refresh/', 
            { refresh: refreshToken },
            {
              headers: { 'Content-Type': 'application/json' },
              withCredentials: true
            }
          );
          
          // 检查响应数据结构
          if (response && response.data && response.data.access) {
            // 更新本地存储的token
            localStorage.setItem('access_token', response.data.access);
            // 更新原始请求的Authorization头
            originalRequest.headers['Authorization'] = 'Bearer ' + response.data.access;
            // 重试原始请求
            return backendService(originalRequest);
          }
        }
        // 如果刷新失败，清除令牌并重定向到登录页
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        router.push('/login');
      } catch (refreshError) {
        console.error('令牌刷新失败:', refreshError);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        router.push('/login');
        return Promise.reject(refreshError);
      }
    }

    // 处理验证码相关错误
    if (originalRequest.url.includes('/captcha/') || originalRequest.url.includes('/login/')) {
      console.error('验证码/登录错误:', error.response.data);
      if (error.response.data?.captcha) {
        error.message = Array.isArray(error.response.data.captcha) 
          ? error.response.data.captcha[0] 
          : error.response.data.captcha;
      } else if (error.response.status === 400) {
        if (error.response.data?.non_field_errors) {
          error.message = error.response.data.non_field_errors[0];
        } else if (error.response.data?.detail) {
          error.message = error.response.data.detail;
        } else {
          error.message = '验证码验证失败，请重试';
        }
      } else if (error.response.status >= 500) {
        error.message = '服务暂时不可用，请稍后重试';
      }
      return Promise.reject(error);
    }

    // 处理其他错误
    if (error.response.status >= 500) {
      console.error('服务器错误:', error.response.data);
      error.message = error.response.data?.error || '服务器内部错误，请稍后重试';
    } else if (error.response.status === 400) {
      console.error('请求错误:', error.response.data);
      const errorData = error.response.data;
      if (typeof errorData === 'string') {
        error.message = errorData;
      } else if (errorData.detail) {
        error.message = errorData.detail;
      } else if (errorData.non_field_errors) {
        error.message = errorData.non_field_errors[0];
      } else {
        const firstError = Object.values(errorData)[0];
        error.message = Array.isArray(firstError) ? firstError[0] : '请求参数错误';
      }
    } else if (error.response.status === 403) {
      error.message = '没有权限执行此操作';
    } else if (error.response.status === 404) {
      error.message = '请求的资源不存在';
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
  backendService,  // 导出backendService实例
  aiService,       // 导出aiService实例
  
  // 用户认证相关接口
  auth: {
    login: (data) => backendService.post('/api/users/login/', data),
    register: (data) => backendService.post('/api/users/register/', data),
    refreshToken: (data) => backendService.post('/api/users/token/refresh/', data),
    getProfile: () => backendService.get('/api/users/profile/'),
    updateProfile: (data) => backendService.patch('/api/users/profile/', data),
    changePassword: (data) => backendService.post('/api/users/change-password/', data),
    getCaptcha: () => backendService.get('/api/users/captcha/generate/'),
    getUsers: (url) => backendService.get(url),
  },
  // 告警相关接口
  alerts: {
    getList: (params) => backendService.get('/api/alerts/', { params }),
    getDetail: (id) => backendService.get(`/api/alerts/${id}/`),
    create: (data) => backendService.post('/api/alerts/', data),
    update: (id, data) => backendService.patch(`/api/alerts/${id}/`, data),
    handle: (id, data) => backendService.patch(`/api/alerts/${id}/handle/`, data),
  },
  // AI服务相关接口
  ai: {
    startStream: (config) => {
      // 【修复】为startStream请求直接传递完整的配置
      return requestWithRetry(aiService, {
        url: '/stream/start/',
        method: 'post',
        data: config
      });
    },
    stopStream: (camera_id) => {
      return requestWithRetry(aiService, {
        url: `/stream/stop/${camera_id}`,
        method: 'post'
      });
    },
    // WebRTC相关接口
    createWebRTCOffer: (camera_id) => {
      return requestWithRetry(aiService, {
        url: `/webrtc/offer/${camera_id}`,
        method: 'post'
      });
    },
    sendWebRTCAnswer: (connection_id, answer) => {
      return aiService.post(`/webrtc/answer/${connection_id}`, answer);
    },
    closeWebRTCConnection: (connection_id) => {
      return aiService.delete(`/webrtc/connection/${connection_id}`);
    },
    // 添加获取WebRTC状态的方法
    getWebRTCStatus: () => {
      return aiService.get('/webrtc/status');
    },
    verifyFace: (data) => {
      return requestWithRetry(aiService, {
        url: '/face/verify',
        method: 'post',
        data: data
      });
    },
    checkFaceExists: (params) => {
      return requestWithRetry(aiService, {
        url: '/face/check/',
        method: 'get',
        params
      });
    },
    extractFramesFromVideo: (data) => {
      return requestWithRetry(aiService, {
        url: '/face/extract_frames/',
        method: 'post',
        data,
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
    },
    registerFace: (data) => {
      return requestWithRetry(aiService, {
        url: '/face/register/',
        method: 'post',
        data,
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
    },
    updateSettings: (camera_id, settings) => {
      return requestWithRetry(aiService, {
        url: `/frame/analyze/settings/${camera_id}`,
        method: 'post',
        data: settings
      });
    },
    analyzeFrame: (formData, config = {}) => {
      return requestWithRetry(aiService, {
        url: '/frame/analyze/',
        method: 'post',
        data: formData,
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        ...config
      });
    },
    testStream: (url, type) => {
      return requestWithRetry(aiService, {
        url: '/stream/test/',
        method: 'post',
        data: { url, type }
      });
    },
    testConnection: () => {
      return requestWithRetry(aiService, {
        url: '/system/status/',
        method: 'get'
      });
    },
    clearDetectionCache: (camera_id) => {
      return requestWithRetry(aiService, {
        url: `/detection/cache/clear/${camera_id}`,
        method: 'post'
      });
    },
    getStabilizationConfig: (camera_id) => {
      return requestWithRetry(aiService, {
        url: `/detection/stabilization/config/${camera_id}`,
        method: 'get'
      });
    },
    updateStabilizationConfig: (camera_id, config) => {
      return requestWithRetry(aiService, {
        url: '/detection/stabilization/config/',
        method: 'post',
        data: {
          camera_id,
          ...config
        }
      });
    },
    applyStabilizationPreset: (preset, camera_id) => {
      return requestWithRetry(aiService, {
        url: `/detection/stabilization/preset/${preset}`,
        method: 'post',
        data: { camera_id }
      });
    },
    getSystemStatus: () => {
      return requestWithRetry(aiService, {
        url: '/system/status/',
        method: 'get'
      });
    }
  }
};

// 创建useApi钩子函数
export const useApi = () => {
  return api;
};

// 导出服务实例和API对象
export { backendService, aiService };
export default api;
