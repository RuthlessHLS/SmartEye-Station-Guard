<!-- src/views/UserProfile.vue -->
<template>
  <div class="user-profile-container">
    <h1>个人中心</h1>
    <el-tabs v-model="activeTab" class="profile-tabs">
      <!-- 个人资料 -->
      <el-tab-pane label="个人资料" name="info">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>基本信息</span>
              <el-button type="primary" link @click="isEditingInfo = !isEditingInfo">
                {{ isEditingInfo ? '取消' : '编辑' }}
              </el-button>
            </div>
          </template>

          <!-- [核心修改] 在这里添加所有需要展示的字段 -->
          <el-descriptions :column="2" border>
            <el-descriptions-item label="用户名">{{ userInfo.username }}</el-descriptions-item>
            <el-descriptions-item label="邮箱">{{ userInfo.email }}</el-descriptions-item>

            <!-- 新增：显示昵称 -->
            <el-descriptions-item label="昵称">{{ userInfo.nickname || '未设置' }}</el-descriptions-item>

            <!-- 新增：显示手机号 -->
            <el-descriptions-item label="手机号">{{ userInfo.phone_number || '未绑定' }}</el-descriptions-item>

            <!-- 新增：显示性别 -->
            <el-descriptions-item label="性别">{{ userInfo.gender || '保密' }}</el-descriptions-item>

            <el-descriptions-item label="加入时间">{{ new Date(userInfo.date_joined).toLocaleDateString() }}</el-descriptions-item>

            <!-- 新增：显示个人简介，并让它占满一行 -->
            <el-descriptions-item label="个人简介" :span="2">{{ userInfo.bio || '暂无简介' }}</el-descriptions-item>
          </el-descriptions>

          <!-- 编辑表单保持不变，它会在点击“编辑”后出现 -->
          <el-form
            ref="infoFormRef"
            :model="infoForm"
            :rules="infoRules"
            label-width="80px"
            style="margin-top: 20px;"
            v-if="isEditingInfo"
          >
            <el-form-item label="昵称" prop="nickname">
              <el-input v-model="infoForm.nickname"></el-input>
            </el-form-item>
            <el-form-item label="手机号" prop="phone_number">
              <el-input v-model="infoForm.phone_number"></el-input>
            </el-form-item>
            <el-form-item label="性别" prop="gender">
               <el-radio-group v-model="infoForm.gender">
                <el-radio :label="1">男</el-radio>
                <el-radio :label="2">女</el-radio>
                <el-radio :label="0">保密</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="个人简介" prop="bio">
              <el-input type="textarea" v-model="infoForm.bio"></el-input>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="submitInfoUpdate" :loading="infoLoading">保存修改</el-button>
            </el-form-item>
          </el-form>

        </el-card>
      </el-tab-pane>

      <!-- 修改密码部分保持不变 -->
      <el-tab-pane label="修改密码" name="password">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>安全设置</span>
            </div>
          </template>
          <el-form
            ref="passwordFormRef"
            :model="passwordForm"
            :rules="passwordRules"
            label-width="100px"
            style="width: 400px; margin: 20px;"
          >
            <el-form-item label="当前密码" prop="current_password">
              <el-input type="password" v-model="passwordForm.current_password" show-password></el-input>
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input type="password" v-model="passwordForm.new_password" show-password></el-input>
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input type="password" v-model="passwordForm.confirm_password" show-password></el-input>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="submitPasswordChange" :loading="passwordLoading">确认修改</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { ElMessage } from 'element-plus';

const authStore = useAuthStore();

// --- Tabs and Forms Refs ---
const activeTab = ref('info');
const infoFormRef = ref(null);
const passwordFormRef = ref(null);

// --- User Info State ---
const isEditingInfo = ref(false);
const infoLoading = ref(false);
const userInfo = computed(() => authStore.user || {}); // 使用计算属性确保响应式

const infoForm = reactive({
  nickname: '',
  phone_number: '',
  gender: 0,
  bio: '',
});

const infoRules = {
  nickname: [{ required: true, message: '昵称不能为空', trigger: 'blur' }],
  phone_number: [
    // 手机号可以为空，但如果填了就要符合格式
    { pattern: /^(1\d{10})?$/, message: '请输入有效的11位手机号', trigger: 'blur' }
  ],
};

// --- Password Change State ---
const passwordLoading = ref(false);
const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
});

const validatePass2 = (rule, value, callback) => {
  if (value === '') {
    callback(new Error('请再次输入新密码'));
  } else if (value !== passwordForm.new_password) {
    callback(new Error("两次输入的新密码不一致!"));
  } else {
    callback();
  }
};

const passwordRules = {
  current_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }, { min: 8, message: '密码长度不能少于8位', trigger: 'blur' }],
  confirm_password: [{ required: true, validator: validatePass2, trigger: 'blur' }],
};


// --- Methods ---
onMounted(() => {
  // 组件挂载时，从 store 初始化表单数据
  if (authStore.user) {
    Object.assign(infoForm, {
      nickname: authStore.user.nickname || '',
      phone_number: authStore.user.phone_number || '',
      gender: authStore.user.gender_code || 0, // 假设后端返回一个 gender_code
      bio: authStore.user.bio || '',
    });
  }
});

// 提交个人信息更新
const submitInfoUpdate = async () => {
  if (!infoFormRef.value) return;
  await infoFormRef.value.validate(async (valid) => {
    if (valid) {
      infoLoading.value = true;
      try {
        await authStore.updateUserProfile(infoForm);
        ElMessage.success('个人信息更新成功！');
        isEditingInfo.value = false;
      } catch (error) {
        const msg = error.response?.data?.detail || '更新失败，请重试。';
        ElMessage.error(msg);
      } finally {
        infoLoading.value = false;
      }
    }
  });
};

// 提交密码修改
const submitPasswordChange = async () => {
  if (!passwordFormRef.value) return;
  await passwordFormRef.value.validate(async (valid) => {
    if (valid) {
      passwordLoading.value = true;
      try {
        await authStore.changePassword(passwordForm);
        ElMessage.success('密码修改成功！您可能需要重新登录。');
        // 清空表单
        passwordFormRef.value.resetFields();
        // 建议：密码修改成功后可以强制用户登出
        // authStore.logout();
      } catch (error) {
        const msg = error.response?.data?.detail || '密码修改失败，请检查当前密码是否正确。';
        ElMessage.error(msg);
      } finally {
        passwordLoading.value = false;
      }
    }
  });
};
</script>

<style scoped>
.user-profile-container {
  max-width: 900px;
  margin: 0 auto;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.profile-tabs {
  margin-top: 20px;
}
</style>
