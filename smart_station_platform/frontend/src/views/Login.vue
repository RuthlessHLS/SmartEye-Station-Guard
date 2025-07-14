<template>
  <div class="auth-page">
    <div class="auth-container">
      <h1 class="title">智能监控站点管理系统</h1>

      <form @submit.prevent="handleLoginAttempt" class="auth-form">
        <div class="form-item">
          <input type="text" v-model="form.username" placeholder="请输入用户名" required>
        </div>
        <div class="form-item">
          <input type="password" v-model="form.password" placeholder="请输入密码" required>
        </div>

        <!-- 显示错误信息 -->
        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>

        <div class="form-options">
          <label class="remember-me">
            <input type="checkbox" v-model="form.remember"> 记住密码
          </label>
          <a href="#" class="forgot-password">忘记密码？</a>
        </div>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
        
        <!-- 添加人脸识别登录选项 -->
        <div class="alternative-login">
          <span>或者</span>
        </div>
        <button type="button" @click="goToFaceLogin" class="face-login-btn">
          <i class="face-icon">👤</i> 人脸识别登录
        </button>

        <div class="switch-link">
          还没有账号？ <router-link to="/register">立即注册</router-link>
        </div>
      </form>
    </div>

    <!-- 引入并使用滑动验证码组件 -->
    <SliderCaptcha
      v-if="showCaptcha"
      v-model:visible="showCaptcha"
      @success="onCaptchaSuccess"
      @close="loading = false"
    />
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';
import { useRouter } from 'vue-router';
import SliderCaptcha from './SliderCaptcha.vue'; // 假设滑动验证码组件在同级目录

// 1. 引入 useAuthStore，不再需要 axios 和 useRouter
import { useAuthStore } from '@/stores/auth';

// 2. 初始化 Pinia store
const authStore = useAuthStore();
const router = useRouter();

// 状态控制
const loading = ref(false);
const showCaptcha = ref(false);
const errorMessage = ref('');

// 登录表单数据
const form = reactive({
  username: '',
  password: '',
  remember: false,
});

// 存储验证码成功后的数据
const captchaResult = reactive({
  captcha_key: '',
  captcha_position: 0,
});

// 用户点击 "登录" 按钮，触发此方法
const handleLoginAttempt = () => {
  errorMessage.value = ''; // 先清空之前的错误
  if (!form.username || !form.password) {
    errorMessage.value = '请输入用户名和密码';
    return;
  }
  // 点击登录后立即进入 loading 状态
  loading.value = true;
  showCaptcha.value = true;
};

// 跳转到人脸登录页面
const goToFaceLogin = () => {
  router.push('/face-login');
};

// 监听验证码组件的 `success` 事件
const onCaptchaSuccess = async (result) => {
  try {
    // 保存验证码结果
    const loginData = {
      username: form.username,
      password: form.password,
      captcha_key: result.captcha_key,
      captcha_position: Math.round(result.captcha_position).toString(), // 确保是整数字符串
    };

    console.log('验证码验证成功，准备登录');
    showCaptcha.value = false;

    // 调用 authStore 中的 login action，并等待它完成
    await authStore.login(loginData);

  } catch (error) {
    console.error('登录过程中发生错误:', error);
    
    // 从 action 中抛出的错误会被这里捕获
    let msg = '登录失败，请重试。';
    
    if (error.response?.data) {
      const errorData = error.response.data;
      console.log('服务器返回的错误数据:', errorData);
      
      if (typeof errorData === 'string') {
        msg = errorData;
      } else if (errorData.detail) {
        msg = errorData.detail;
      } else if (errorData.captcha) {
        msg = errorData.captcha;
      } else if (errorData.username) {
        msg = `用户名: ${errorData.username[0]}`;
      } else if (errorData.password) {
        msg = `密码: ${errorData.password[0]}`;
      } else if (errorData.non_field_errors) {
        msg = errorData.non_field_errors[0];
      }
    } else if (error.message) {
      msg = error.message;
    }

    errorMessage.value = msg;
    
    // 如果是验证码错误，重新显示验证码
    if (msg.includes('验证码') || msg.includes('captcha')) {
      console.log('验证码错误，重新显示验证码组件');
      showCaptcha.value = true;
    }
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f0f2f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji';
}
.auth-container {
  width: 400px;
  padding: 40px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.title {
  font-size: 24px;
  font-weight: 600;
  text-align: center;
  margin-bottom: 30px;
  color: #333;
}
.auth-form .form-item {
  margin-bottom: 20px;
}
.auth-form input[type="text"],
.auth-form input[type="password"] {
  width: 100%;
  padding: 12px 15px;
  font-size: 16px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  transition: all 0.3s;
  box-sizing: border-box;
}
.auth-form input:focus {
  border-color: #40a9ff;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
  outline: none;
}
.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
  font-size: 14px;
}
.remember-me {
  color: #666;
  cursor: pointer;
}
.remember-me input {
  margin-right: 5px;
}
.forgot-password, .switch-link a {
  color: #1890ff;
  text-decoration: none;
}
.forgot-password:hover, .switch-link a:hover {
  text-decoration: underline;
}
.submit-btn {
  width: 100%;
  padding: 12px;
  font-size: 16px;
  color: #fff;
  background-color: #1890ff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
}
.submit-btn:hover {
  background-color: #40a9ff;
}
.submit-btn:disabled {
  background-color: #b3d9ff;
  cursor: not-allowed;
}
.switch-link {
  margin-top: 20px;
  text-align: center;
  font-size: 14px;
  color: #666;
}
/* 错误信息样式 */
.error-message {
  color: #f56c6c;
  font-size: 14px;
  margin-bottom: 15px;
  text-align: center;
}
/* 添加人脸识别登录样式 */
.alternative-login {
  display: flex;
  align-items: center;
  margin: 15px 0;
  text-align: center;
  position: relative;
}
.alternative-login span {
  padding: 0 10px;
  background-color: #fff;
  color: #999;
  position: relative;
  z-index: 2;
  margin: 0 auto;
}
.alternative-login::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  width: 100%;
  height: 1px;
  background-color: #e8e8e8;
  z-index: 1;
}
.face-login-btn {
  width: 100%;
  padding: 12px;
  font-size: 16px;
  color: #1890ff;
  background-color: #f0f7ff;
  border: 1px solid #91d5ff;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  justify-content: center;
  align-items: center;
}
.face-login-btn:hover {
  background-color: #e6f7ff;
  border-color: #69c0ff;
}
.face-icon {
  font-size: 18px;
  margin-right: 8px;
}
</style>

