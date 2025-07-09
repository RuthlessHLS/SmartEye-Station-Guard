<template>
  <div class="register-container">
    <div class="register-background">
      <div class="background-overlay"></div>
    </div>
    <el-card class="register-card">
      <template #header>
        <div class="card-header">
          <div class="logo-section">
            <img src="@/assets/logo.svg" class="logo" alt="智能监控系统" />
            <h2>用户注册</h2>
          </div>
        </div>
      </template>
      
      <el-form 
        :model="registerForm" 
        :rules="rules" 
        ref="registerFormRef" 
        label-width="0"
        @keyup.enter="submitForm"
      >
        <el-form-item prop="username">
          <el-input 
            v-model="registerForm.username" 
            placeholder="请输入用户名"
            prefix-icon="User"
            size="large"
            :disabled="loading"
            clearable
          />
        </el-form-item>
        
        <el-form-item prop="email">
          <el-input 
            v-model="registerForm.email" 
            placeholder="请输入邮箱地址"
            prefix-icon="Message"
            size="large"
            :disabled="loading"
            clearable
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input 
            type="password" 
            v-model="registerForm.password" 
            placeholder="请输入密码"
            prefix-icon="Lock"
            size="large"
            show-password
            :disabled="loading"
            clearable
          />
        </el-form-item>
        
        <el-form-item prop="confirmPassword">
          <el-input 
            type="password" 
            v-model="registerForm.confirmPassword" 
            placeholder="请再次输入密码"
            prefix-icon="Lock"
            size="large"
            show-password
            :disabled="loading"
            clearable
          />
        </el-form-item>
        
        <el-form-item prop="agreement" class="agreement-item">
          <el-checkbox v-model="registerForm.agreement" :disabled="loading">
            我已阅读并同意
            <el-link type="primary" :underline="false" @click="showAgreement">
              《用户协议》
            </el-link>
            和
            <el-link type="primary" :underline="false" @click="showPrivacy">
              《隐私政策》
            </el-link>
          </el-checkbox>
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            class="register-button" 
            size="large"
            :loading="loading"
            @click="submitForm"
          >
            {{ loading ? '注册中...' : '立即注册' }}
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="login-link">
        <span>已有账号？</span>
        <router-link to="/login">立即登录</router-link>
      </div>
    </el-card>
    
    <!-- 用户协议对话框 -->
    <el-dialog
      v-model="agreementVisible"
      title="用户协议"
      width="600px"
      append-to-body
    >
      <div class="agreement-content">
        <h3>智能监控站点管理系统用户协议</h3>
        <p>欢迎使用智能监控站点管理系统！请仔细阅读以下条款：</p>
        <ol>
          <li>用户应遵守相关法律法规，不得利用本系统进行任何违法活动</li>
          <li>保护个人账号安全，不得将账号信息泄露给他人</li>
          <li>不得进行任何危害系统安全的行为，包括但不限于恶意攻击、数据篡改等</li>
          <li>遵守数据保护和隐私规范，合理使用监控数据</li>
          <li>对自己的操作行为负责，承担相应的法律责任</li>
        </ol>
      </div>
    </el-dialog>
    
    <!-- 隐私政策对话框 -->
    <el-dialog
      v-model="privacyVisible"
      title="隐私政策"
      width="600px"
      append-to-body
    >
      <div class="privacy-content">
        <h3>隐私政策声明</h3>
        <p>我们重视您的隐私保护，承诺：</p>
        <ol>
          <li>仅收集必要的个人信息，用于系统功能实现</li>
          <li>采用行业标准的加密技术保护您的数据安全</li>
          <li>不会向第三方泄露您的个人信息</li>
          <li>定期审查和更新安全措施，确保数据安全</li>
          <li>您拥有访问、修改和删除个人信息的权利</li>
        </ol>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import api from '../api';

const router = useRouter();
const registerFormRef = ref(null);
const loading = ref(false);
const agreementVisible = ref(false);
const privacyVisible = ref(false);

const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  agreement: false
});

// 自定义密码验证
const validatePassword = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请输入密码'));
  } else if (value.length < 8) {
    callback(new Error('密码长度不能少于8位'));
  } else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(value)) {
    callback(new Error('密码必须包含大小写字母和数字'));
  } else {
    callback();
  }
};

// 确认密码验证
const validateConfirmPassword = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请再次输入密码'));
  } else if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'));
  } else {
    callback();
  }
};

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 5, max: 20, message: '用户名长度应为5-20个字符', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线' }
  ],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, validator: validatePassword, trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, validator: validateConfirmPassword, trigger: 'blur' }
  ],
  agreement: [
    {
      validator: (rule, value, callback) => {
        if (!value) {
          callback(new Error('请阅读并同意用户协议和隐私政策'));
        } else {
          callback();
        }
      },
      trigger: 'change'
    }
  ]
};

const submitForm = async () => {
  if (!registerFormRef.value) return;
  
  try {
    const valid = await registerFormRef.value.validate();
    if (!valid) return;
    
    loading.value = true;
    
    const response = await api.post('/users/register/', {
      username: registerForm.username,
      email: registerForm.email,
      password: registerForm.password,
      password2: registerForm.confirmPassword,
      nickname: registerForm.username
    });
    
    ElMessage.success('注册成功！');
    router.push('/login');
    
  } catch (error) {
    ElMessage.error('注册失败：' + (error.response?.data?.detail || '请检查输入或用户名是否已存在！'));
    console.error('Register error:', error);
  } finally {
    loading.value = false;
  }
};

const resetForm = () => {
  if (!registerFormRef.value) return;
  registerFormRef.value.resetFields();
};

const showAgreement = () => {
  agreementVisible.value = true;
};

const showPrivacy = () => {
  privacyVisible.value = true;
};
</script>

<style scoped>
.register-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  overflow: hidden;
}

.register-background {
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

.register-card {
  width: 450px;
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

.register-button {
  width: 100%;
  height: 44px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 6px;
}

.agreement-item {
  margin: 20px 0;
}

.login-link {
  text-align: center;
  margin-top: 20px;
  color: #606266;
  font-size: 14px;
}

.login-link a {
  color: #409eff;
  text-decoration: none;
  margin-left: 4px;
}

.login-link a:hover {
  text-decoration: underline;
}

.agreement-content,
.privacy-content {
  max-height: 400px;
  overflow-y: auto;
  padding: 20px;
}

.agreement-content h3,
.privacy-content h3 {
  margin-top: 0;
  margin-bottom: 20px;
  text-align: center;
  color: #2c3e50;
}

.agreement-content ol,
.privacy-content ol {
  padding-left: 20px;
  line-height: 1.8;
}

.agreement-content li,
.privacy-content li {
  margin-bottom: 10px;
}

:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-input__wrapper) {
  border-radius: 6px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
</style>
