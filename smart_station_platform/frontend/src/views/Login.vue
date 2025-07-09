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
        <div class="form-options">
          <label class="remember-me">
            <input type="checkbox" v-model="form.remember"> 记住密码
          </label>
          <a href="#" class="forgot-password">忘记密码？</a>
        </div>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>

        <div class="switch-link">
          还没有账号？ <a href="/register">立即注册</a>
        </div>
      </form>
    </div>

    <!-- 滑动验证码组件 -->
    <SliderCaptcha
      v-if="showCaptcha"
      v-model:visible="showCaptcha"
      @success="onCaptchaSuccess"
    />
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';
import axios from 'axios';
// 1. 导入 SliderCaptcha 组件 (请确保路径正确)
import SliderCaptcha from './SliderCaptcha.vue'; // 假设 SliderCaptcha.vue 在同级目录

// 状态控制
const loading = ref(false);
const showCaptcha = ref(false);

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

// 2. 用户点击 "登录" 按钮，触发此方法
const handleLoginAttempt = () => {
  // 前端基础校验
  if (!form.username || !form.password) {
    alert('请输入用户名和密码');
    return;
  }
  // 显示验证码组件
  showCaptcha.value = true;
};

// 3. 监听验证码组件的 `success` 事件
const onCaptchaSuccess = (result) => {
  // 保存验证码结果
  captchaResult.captcha_key = result.captcha_key;
  captchaResult.captcha_position = result.captcha_position;

  // 隐藏验证码模态框
  showCaptcha.value = false;

  // 立即执行真正的登录提交
  submitLogin();
};

// 4. 包含完整数据的最终提交函数
const submitLogin = async () => {
  loading.value = true;
  try {
    const payload = {
      username: form.username,
      password: form.password,
      captcha_key: captchaResult.captcha_key,
      captcha_position: captchaResult.captcha_position,
    };

    // 修正API端点 - 使用用户应用中带验证码的登录端点
    const response = await axios.post('http://127.0.0.1:8000/api/users/token/', payload);

    alert('登录成功！');
    console.log('Token:', response.data);

    // 保存token并跳转到主页
    localStorage.setItem('access_token', response.data.access);
    localStorage.setItem('refresh_token', response.data.refresh);
    window.location.href = '/';

  } catch (error) {
    // 从后端响应中提取更具体的错误信息
    const errorData = error.response?.data;
    let errorMessage = '登录失败，请重试。';
    
    if (!error.response) {
      // 网络错误或服务器未运行
      errorMessage = '无法连接到服务器，请检查网络连接或联系管理员';
    } else if (errorData) {
      // 覆盖默认错误信息
      errorMessage = errorData.detail || errorData.captcha || 
                    (errorData.username && `用户名: ${errorData.username[0]}`) || 
                    (errorData.password && `密码: ${errorData.password[0]}`) || 
                    JSON.stringify(errorData);
    }
    
    alert(errorMessage);
    console.error('登录失败:', error);
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
</style>
