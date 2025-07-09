<template>
  <div class="user-management-container">
    <h1>用户管理</h1>
    <el-card class="user-list-card">
      <template #header>
        <div class="card-header">
          <span>用户列表</span>
          <el-button type="primary" @click="openAddUserDialog">添加用户</el-button>
        </div>
      </template>
      <el-table :data="users" v-loading="loading" stripe border style="width: 100%">
        <el-table-column type="index" label="序号" width="60"></el-table-column>
        <el-table-column prop="username" label="用户名"></el-table-column>
        <el-table-column prop="email" label="邮箱"></el-table-column>
        <el-table-column prop="is_staff" label="管理员" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_staff ? 'success' : 'info'">
              {{ scope.row.is_staff ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="激活" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'danger'">
              {{ scope.row.is_active ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="date_joined" label="加入日期" width="180"></el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEditUserDialog(scope.row)">编辑</el-button>
            <el-button
              size="small"
              type="warning"
              @click="toggleUserActive(scope.row)"
              :disabled="scope.row.username === 'xhy'"
            >
              {{ scope.row.is_active ? '禁用' : '启用' }}
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="deleteUser(scope.row.id)"
              :disabled="scope.row.username === 'xhy'"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="pagination.currentPage"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="pagination.total"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
        background
        class="pagination-container"
      ></el-pagination>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="isEditMode ? '编辑用户' : '添加用户'"
      width="40%"
      destroy-on-close
    >
      <el-form :model="userForm" :rules="rules" ref="userFormRef" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" :disabled="isEditMode"></el-input>
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="userForm.email"></el-input>
        </el-form-item>
        <el-form-item label="密码" :prop="isEditMode ? '' : 'password'">
          <el-input type="password" v-model="userForm.password" placeholder="留空则不修改密码"></el-input>
        </el-form-item>
        <el-form-item label="管理员" prop="is_staff">
          <el-switch v-model="userForm.is_staff"></el-switch>
        </el-form-item>
        <el-form-item label="激活状态" prop="is_active">
          <el-switch v-model="userForm.is_active"></el-switch>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitUserForm">
            {{ isEditMode ? '保存' : '添加' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import api from '../api'; // 导入API请求服务

const users = ref([]);
const loading = ref(false);
const pagination = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0,
});

const dialogVisible = ref(false);
const isEditMode = ref(false); // 标识是否为编辑模式
const userFormRef = ref(null); // 表单引用
const userForm = reactive({
  id: null,
  username: '',
  email: '',
  password: '',
  is_staff: false,
  is_active: true,
});

const rules = reactive({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, message: '用户名至少3个字符', trigger: 'blur' },
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱格式', trigger: ['blur', 'change'] },
  ],
  password: [
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' },
  ],
});

onMounted(() => {
  fetchUsers();
});

const fetchUsers = async () => {
  loading.value = true;
  try {
    // 修正API路径，添加/api前缀
    const response = await api.get('/api/users/', {
      params: {
        page: pagination.currentPage,
        page_size: pagination.pageSize,
      },
    });
    users.value = response.results.map(user => ({
      ...user,
      date_joined: new Date(user.date_joined).toLocaleString(), // 格式化日期
    }));
    pagination.total = response.count;
  } catch (error) {
    ElMessage.error('获取用户列表失败！');
    console.error('Fetch users error:', error);
  } finally {
    loading.value = false;
  }
};

const openAddUserDialog = () => {
  isEditMode.value = false;
  // 重置表单数据
  Object.assign(userForm, {
    id: null,
    username: '',
    email: '',
    password: '',
    is_staff: false,
    is_active: true,
  });
  // 确保密码字段在添加模式下是必填的
  rules.password[0] = { required: true, message: '请输入密码', trigger: 'blur' };
  dialogVisible.value = true;
  nextTick(() => {
    userFormRef.value?.clearValidate(); // 清除验证状态
  });
};

const openEditUserDialog = (row) => {
  isEditMode.value = true;
  // 填充表单数据 (密码不直接回显)
  Object.assign(userForm, {
    id: row.id,
    username: row.username,
    email: row.email,
    password: '', // 密码不回显
    is_staff: row.is_staff,
    is_active: row.is_active,
  });
  // 密码字段在编辑模式下变为非必填
  rules.password[0] = { required: false };
  dialogVisible.value = true;
  nextTick(() => {
    userFormRef.value?.clearValidate();
  });
};

const submitUserForm = () => {
  userFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        if (isEditMode.value) {
          // 编辑用户，假设后端接口为 /api/users/{id}/update/
          const dataToUpdate = {
            email: userForm.email,
            is_staff: userForm.is_staff,
            is_active: userForm.is_active,
          };
          if (userForm.password) { // 只有密码不为空才发送
            dataToUpdate.password = userForm.password;
          }
          await api.patch(`/api/users/${userForm.id}/update/`, dataToUpdate);
          ElMessage.success('用户更新成功！');
        } else {
          // 添加用户，假设后端接口为 /api/users/register/ (或专门的admin创建用户接口)
          await api.post('/api/users/register/', {
            username: userForm.username,
            email: userForm.email,
            password: userForm.password,
            is_staff: userForm.is_staff,
            is_active: userForm.is_active,
          });
          ElMessage.success('用户添加成功！');
        }
        dialogVisible.value = false;
        fetchUsers(); // 刷新列表
      } catch (error) {
        ElMessage.error('操作失败：' + (error.response?.data?.detail || ''));
        console.error('Submit user form error:', error);
      }
    } else {
      ElMessage.warning('请检查表单信息！');
      return false;
    }
  });
};

const toggleUserActive = async (row) => {
  if (row.username === 'xhy') {
      ElMessage.warning('不能禁用/启用超级管理员账户！');
      return;
  }
  const confirmMessage = row.is_active ? `确定要禁用用户 ${row.username} 吗？` : `确定要启用用户 ${row.username} 吗？`;
  ElMessageBox.confirm(confirmMessage, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      try {
        // 假设后端接口为 /api/users/{id}/update_active_status/
        await api.patch(`/api/users/${row.id}/update_active_status/`, {
          is_active: !row.is_active,
        });
        ElMessage.success(`用户 ${row.is_active ? '禁用' : '启用'}成功！`);
        fetchUsers();
      } catch (error) {
        ElMessage.error('操作失败！');
        console.error('Toggle active status error:', error);
      }
    })
    .catch(() => {
      ElMessage.info('取消操作。');
    });
};

const deleteUser = async (id) => {
  const userToDelete = users.value.find(u => u.id === id);
  if (userToDelete && userToDelete.username === 'xhy') {
      ElMessage.warning('不能删除超级管理员账户！');
      return;
  }

  ElMessageBox.confirm('此操作将永久删除该用户，是否继续？', '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'error',
  })
    .then(async () => {
      try {
        // 假设后端接口为 /api/users/{id}/delete/
        await api.delete(`/api/users/${id}/delete/`);
        ElMessage.success('用户删除成功！');
        fetchUsers(); // 刷新列表
      } catch (error) {
        ElMessage.error('删除用户失败！');
        console.error('Delete user error:', error);
      }
    })
    .catch(() => {
      ElMessage.info('已取消删除。');
    });
};

const handleSizeChange = (val) => {
  pagination.pageSize = val;
  fetchUsers();
};

const handleCurrentChange = (val) => {
  pagination.currentPage = val;
  fetchUsers();
};
</script>

<style scoped>
.user-management-container {
  padding: 20px;
}
.user-management-container h1 {
  text-align: center;
  margin-bottom: 20px;
}
.user-list-card {
  margin-top: 20px;
}
.user-list-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 1.1em;
  font-weight: bold;
}
.pagination-container {
  margin-top: 20px;
  justify-content: center;
  display: flex;
}
</style>
