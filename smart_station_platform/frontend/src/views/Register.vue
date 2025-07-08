<template>
  <div class="register-container">
    <el-card class="register-card">
      <template #header>
        <div class="card-header">
          <span>用户注册</span>
        </div>
      </template>
      <el-form :model="registerForm" :rules="rules" ref="registerFormRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="registerForm.username" placeholder="请输入用户名"></el-input>
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input type="password" v-model="registerForm.password" placeholder="请输入密码"></el-input>
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input type="password" v-model="registerForm.confirmPassword" placeholder="请再次输入密码"></el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="submitForm">注册</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
      <div class="login-link">
        <router-link to="/login">已有账户？立即登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';
import { ElMessage } from 'element-plus';
import router from '../router'; // 导入路由实例
import api from '../api'; // 导入封装的API请求

const registerFormRef = ref(null);
const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
});

const validatePass = (rule, value, callback) => {
  if (value === '') {
    callback(new Error('请再次输入密码'));
  } else if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致!'));
  } else {
    callback();
  }
};

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' },
  ],
  confirmPassword: [{ required: true, validator: validatePass, trigger: 'blur' }],
};

const submitForm = async () => {
  if (!registerFormRef.value) return;
  registerFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        // 假设后端注册接口为 /api/users/register/
        const response = await api.post('/users/register/', {
          username: registerForm.username,
          password: registerForm.password,
        });
        ElMessage.success('注册成功！');
        router.push('/login'); // 注册成功后跳转到登录页
      } catch (error) {
        ElMessage.error('注册失败：' + (error.response?.data?.detail || '请检查输入或用户名是否已存在！'));
        console.error('Register error:', error);
      }
    } else {
      ElMessage.warning('请检查输入信息！');
      return false;
    }
  });
};

const resetForm = () => {
  if (!registerFormRef.value) return;
  registerFormRef.value.resetFields();
};
</script>

<style scoped>
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 120px);
  background-color: #f5f7fa;
}
.register-card {
  width: 450px;
  padding: 20px;
}
.card-header {
  text-align: center;
  font-size: 1.2em;
  font-weight: bold;
}
.login-link {
  margin-top: 20px;
  text-align: center;
}
</style>
