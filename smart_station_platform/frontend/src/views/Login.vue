<template>
  <div class="login-container">
    <div class="login-background">
      <div class="background-overlay"></div>
    </div>
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <div class="logo-section">
            <img src="@/assets/logo.svg" class="logo" alt="智能监控系统" />
            <h2>智能监控站点管理系统</h2>
          </div>
        </div>
      </template>
      
      <el-form 
        :model="loginForm" 
        :rules="rules" 
        ref="loginFormRef" 
        label-width="0"
        @keyup.enter="submitForm"
      >
        <el-form-item prop="username">
          <el-input 
            v-model="loginForm.username" 
            placeholder="请输入用户名"
            prefix-icon="User"
            size="large"
            :disabled="loading"
            clearable
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input 
            type="password" 
            v-model="loginForm.password" 
            placeholder="请输入密码"
            prefix-icon="Lock"
            size="large"
            show-password
            :disabled="loading"
            clearable
          />
        </el-form-item>
        
        <div class="login-options">
          <el-checkbox v-model="loginForm.remember" :disabled="loading">
            记住密码
          </el-checkbox>
          <el-link type="primary" :underline="false">忘记密码？</el-link>
        </div>
        
        <el-form-item>
          <el-button 
            type="primary" 
            class="login-button" 
            size="large"
            :loading="loading"
            @click="submitForm"
          >
            {{ loading ? '登录中...' : '登录' }}
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="register-link">
        <span>还没有账号？</span>
        <router-link to="/register">立即注册</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import api from '../api';

const router = useRouter();
const loginFormRef = ref(null);
const loading = ref(false);

const loginForm = reactive({
  username: '',
  password: '',
  remember: false
});

// 增强的表单验证规则
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应为3-20个字符', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: '用户名只能包含字母、数字、下划线和横线', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度应为6-20个字符', trigger: 'blur' }
  ]
};

// 页面加载时检查本地存储
onMounted(() => {
  const savedUsername = localStorage.getItem('remembered_username');
  const savedPassword = localStorage.getItem('remembered_password');
  if (savedUsername && savedPassword) {
    loginForm.username = savedUsername;
    loginForm.password = atob(savedPassword); // 简单的base64解码
    loginForm.remember = true;
  }
});

const submitForm = async () => {
  if (!loginFormRef.value) return;
  
  try {
    const valid = await loginFormRef.value.validate();
    if (!valid) return;
    
    loading.value = true;
    
    const response = await api.post('/token/', {
      username: loginForm.username,
      password: loginForm.password,
    });
    
    // 处理记住密码
    if (loginForm.remember) {
      localStorage.setItem('remembered_username', loginForm.username);
      localStorage.setItem('remembered_password', btoa(loginForm.password)); // 简单的base64编码
    } else {
      localStorage.removeItem('remembered_username');
      localStorage.removeItem('remembered_password');
    }
    
    // 存储认证信息
    localStorage.setItem('access_token', response.access);
    localStorage.setItem('refresh_token', response.refresh);
    
    ElMessage.success('登录成功！');
    router.push('/');
    
  } catch (error) {
    ElMessage.error('登录失败：' + (error.response?.data?.detail || '用户名或密码错误！'));
    console.error('Login error:', error);
  } finally {
    loading.value = false;
  }
};

const resetForm = () => {
  if (!loginFormRef.value) return;
  loginFormRef.value.resetFields();
};
</script>

<style scoped>
.login-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  overflow: hidden;
}

.login-background {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  z-index: -1;
}

.background-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.3);
}

.login-card {
  width: 420px;
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(10px);
  background: rgba(255, 255, 255, 0.95);
}

.card-header {
  padding: 0;
}

.logo-section {
  text-align: center;
  padding: 20px 0;
}

.logo {
  width: 64px;
  height: 64px;
  margin-bottom: 16px;
}

h2 {
  margin: 0;
  color: #2c3e50;
  font-size: 20px;
  font-weight: 600;
}

.login-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.login-button {
  width: 100%;
  height: 44px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 6px;
}

.register-link {
  text-align: center;
  margin-top: 20px;
  color: #606266;
  font-size: 14px;
}

.register-link a {
  color: #409eff;
  text-decoration: none;
  margin-left: 4px;
}

.register-link a:hover {
  text-decoration: underline;
}

:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-input__wrapper) {
  border-radius: 6px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

:deep(.el-input__wrapper:hover) {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

:deep(.el-button--primary) {
  background: linear-gradient(135deg, #409eff 0%, #667eea 100%);
  border: none;
  transition: all 0.3s ease;
}

:deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, #337ecc 0%, #5a6fd8 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

:deep(.el-checkbox__label) {
  color: #606266;
  font-size: 14px;
}

@media (max-width: 480px) {
  .login-card {
    width: 90%;
    margin: 0 20px;
  }
}
</style>
