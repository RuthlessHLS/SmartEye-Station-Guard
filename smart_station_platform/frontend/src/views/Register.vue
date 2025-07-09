<template>
  <div class="auth-page">
    <div class="auth-container register-container">
      <h1 class="title">用户注册</h1>

      <form @submit.prevent="handleRegisterAttempt" class="auth-form">
        <div class="form-item">
          <input type="text" v-model="form.username" placeholder="请输入用户名 (5-20位字母/数字/下划线)" required>
        </div>
        <div class="form-item">
          <input type="email" v-model="form.email" placeholder="请输入邮箱 (可选)">
        </div>
        <div class="form-item">
          <input type="tel" v-model="form.phone_number" placeholder="请输入11位手机号 (可选)">
        </div>
        <div class="form-item">
          <input type="password" v-model="form.password" placeholder="请输入密码 (至少8位)" required>
        </div>
        <div class="form-item">
          <input type="password" v-model="form.password2" placeholder="请再次输入密码" required>
        </div>

        <div class="form-item agreement">
          <label>
            <input type="checkbox" v-model="form.agreed"> 我已阅读并同意
            <a href="#" @click.prevent="showAgreement = true">《用户协议》</a> 和
            <a href="#" @click.prevent="showPrivacyPolicy = true">《隐私政策》</a>
          </label>
        </div>

        <button type="submit" class="submit-btn" :disabled="loading || !form.agreed">
          {{ loading ? '注册中...' : '立即注册' }}
        </button>

        <div class="switch-link">
          已有账号？ <a href="/login">立即登录</a>
        </div>
      </form>
    </div>

    <!-- 验证码组件 -->
    <SliderCaptcha
      v-if="showCaptcha"
      v-model:visible="showCaptcha"
      @success="onCaptchaSuccess"
    />

    <!-- 用户协议和隐私政策的模态框 (简单实现) -->
    <div v-if="showAgreement || showPrivacyPolicy" class="modal-overlay" @click="closeModals">
      <div class="modal-content" @click.stop>
        <button class="modal-close" @click="closeModals">×</button>
        <div v-if="showAgreement">
          <h2>智能监控站点管理系统用户协议</h2>
          <pre>欢迎使用智能监控站点管理系统！请仔细阅读以下条款：
1. 用户应遵守相关法律法规，不得利用本系统进行任何违法活动
2. 保护个人账号安全，不得将账号信息泄露给他人
3. 不得进行任何危害系统安全的行为，包括但不限于恶意攻击、数据篡改等
4. 遵守数据保护和隐私规范，合理使用监控数据
5. 对自己的操作行为负责，承担相应的法律责任</pre>
        </div>
        <div v-if="showPrivacyPolicy">
          <h2>隐私政策声明</h2>
          <pre>我们重视您的隐私保护，承诺：
1. 仅收集必要的个人信息，用于系统功能实现
2. 采用行业标准的加密技术保护您的数据安全
3. 不会向第三方泄露您的个人信息
4. 定期审查和更新安全措施，确保数据安全
5. 您拥有访问、修改和删除个人信息的权利</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';
import axios from 'axios';
// 1. 导入 SliderCaptcha 组件
import SliderCaptcha from './SliderCaptcha.vue'; // 假设 SliderCaptcha.vue 在同级目录

// 状态控制
const loading = ref(false);
const showCaptcha = ref(false);
const showAgreement = ref(false);
const showPrivacyPolicy = ref(false);

// 注册表单数据
const form = reactive({
  username: '',
  email: '',
  phone_number: '',
  password: '',
  password2: '',
  agreed: false,
});

// 存储验证码结果
const captchaResult = reactive({
  captcha_key: '',
  captcha_position: 0,
});

// 2. 用户点击 "注册" 按钮，触发此方法
const handleRegisterAttempt = () => {
  // 前端基础校验
  if (form.password !== form.password2) {
    alert('两次输入的密码不一致！');
    return;
  }
  if (!form.agreed) {
    alert('请先阅读并同意用户协议和隐私政策');
    return;
  }
  // 显示验证码模态框
  showCaptcha.value = true;
};

// 3. 监听验证码 `success` 事件
const onCaptchaSuccess = (result) => {
  captchaResult.captcha_key = result.captcha_key;
  captchaResult.captcha_position = result.captcha_position;
  showCaptcha.value = false;
  submitRegister(); // 成功后立即提交
};

// 4. 最终的注册提交函数
const submitRegister = async () => {
  loading.value = true;
  try {
    const payload = {
      username: form.username,
      password: form.password,
      password2: form.password2,
      email: form.email,
      phone_number: form.phone_number,
      captcha_key: captchaResult.captcha_key,
      captcha_position: captchaResult.captcha_position.toString(),
    };

    // 【重要】请将 URL 替换为你的后端 API 地址
    await axios.post('http://127.0.0.1:8000/api/users/register/', payload);

    alert('注册成功！即将跳转到登录页面。');
    // 注册成功后跳转到登录页
    window.location.href = '/login';

  } catch (error) {
    const errorData = error.response?.data;
    let errorMessage = '注册失败，请检查您输入的信息。';
     if (errorData) {
        // 将所有错误信息拼接起来显示
        errorMessage = Object.keys(errorData)
            .map(key => `${key}: ${Array.isArray(errorData[key]) ? errorData[key].join(', ') : errorData[key]}`)
            .join('\n');
    }
    alert(errorMessage);
    console.error('注册失败:', errorData);
  } finally {
    loading.value = false;
  }
};

const closeModals = () => {
  showAgreement.value = false;
  showPrivacyPolicy.value = false;
};
</script>

<style scoped>
/* 共享 Login.vue 的大部分样式 */
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
.register-container {
  width: 450px; /* 注册页可以宽一点 */
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
.auth-form input[type="password"],
.auth-form input[type="email"],
.auth-form input[type="tel"] {
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
.switch-link a {
  color: #1890ff;
  text-decoration: none;
}
.switch-link a:hover {
  text-decoration: underline;
}

/* 注册页特定样式 */
.agreement {
  font-size: 14px;
}
.agreement label {
  color: #666;
  cursor: pointer;
}
.agreement input {
  margin-right: 5px;
}
.agreement a {
  color: #1890ff;
  text-decoration: none;
}

/* 协议模态框样式 */
.modal-overlay {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  background-color: rgba(0,0,0,0.6);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
}
.modal-content {
  background: white;
  padding: 30px 40px;
  border-radius: 8px;
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
  position: relative;
}
.modal-close {
  position: absolute;
  top: 10px; right: 15px;
  font-size: 28px;
  border: none;
  background: transparent;
  cursor: pointer;
}
.modal-content h2 {
  margin-top: 0;
  text-align: center;
  margin-bottom: 20px;
}
.modal-content pre {
  white-space: pre-wrap; /* 自动换行 */
  font-family: inherit;
  font-size: 14px;
  line-height: 1.8;
}
</style>
