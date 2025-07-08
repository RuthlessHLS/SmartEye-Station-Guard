<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <span>用户登录</span>
        </div>
      </template>
      <el-form :model="loginForm" :rules="rules" ref="loginFormRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="loginForm.username" placeholder="请输入用户名"></el-input>
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input type="password" v-model="loginForm.password" placeholder="请输入密码"></el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="submitForm">登录</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
      <div class="register-link">
        <router-link to="/register">没有账户？立即注册</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';
import { ElMessage } from 'element-plus';
import router from '../router'; // 导入路由实例
import api from '../api'; // 导入封装的API请求

const loginFormRef = ref(null); // 表单引用
const loginForm = reactive({
  username: '',
  password: '',
});

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
};

const submitForm = async () => {
  if (!loginFormRef.value) return;
  loginFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        const response = await api.post('/token/', { // 对应后端JWT登录接口
          username: loginForm.username,
          password: loginForm.password,
        });
        localStorage.setItem('access_token', response.access);
        localStorage.setItem('refresh_token', response.refresh);
        ElMessage.success('登录成功！');
        router.push('/'); // 登录成功后跳转到首页
      } catch (error) {
        ElMessage.error('登录失败：' + (error.response?.data?.detail || '用户名或密码错误！'));
        console.error('Login error:', error);
      }
    } else {
      ElMessage.warning('请检查输入信息！');
      return false;
    }
  });
};

const resetForm = () => {
  if (!loginFormRef.value) return;
  loginFormRef.value.resetFields();
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 120px); /* 减去头部和底部高度 */
  background-color: #f5f7fa;
}
.login-card {
  width: 400px;
  padding: 20px;
}
.card-header {
  text-align: center;
  font-size: 1.2em;
  font-weight: bold;
}
.register-link {
  margin-top: 20px;
  text-align: center;
}
</style>
