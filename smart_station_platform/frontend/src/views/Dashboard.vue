<template>
  <div class="dashboard-container">
    <h1>欢迎来到智慧车站智能监控与大数据分析平台</h1>
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>实时安全概览</span>
            </div>
          </template>
          <p>此处将展示当前实时告警数量、重点区域风险等级等。</p>
          <el-empty description="暂无数据"></el-empty>
          <el-space>
            <el-button type="primary" @click="router.push('/monitor')">智能监控中心</el-button>
            <el-button type="success" @click="router.push('/ai-monitor')">🤖 AI实时分析</el-button>
          </el-space>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>运营数据洞察</span>
            </div>
          </template>
          <p>此处将展示客流量趋势、资源利用率等运营指标。</p>
          <el-empty description="暂无数据"></el-empty>
          <el-button type="success" @click="router.push('/data-screen')">查看数据大屏</el-button>
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="20" style="margin-top: 20px;">
        <el-col :span="24">
             <el-card class="box-card">
              <template #header>
                <div class="card-header">
                  <span>快速导航</span>
                </div>
              </template>
              <el-space wrap>
                <el-button type="info" @click="router.push('/alerts')">告警事件管理</el-button>
                <el-button type="warning" @click="router.push('/reports')">AI监控日报</el-button>
                <el-button type="danger" @click="logout">退出登录</el-button>
              </el-space>
             </el-card>
        </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';

const router = useRouter();

const logout = () => {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
  .then(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    ElMessage.success('已安全退出！');
    router.push('/login');
  })
  .catch(() => {
    // 用户取消操作
  });
};
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
}
.dashboard-container h1 {
  text-align: center;
  margin-bottom: 30px;
  color: #303133;
}
.box-card {
  margin-bottom: 20px;
  min-height: 250px;
  display: flex;
  flex-direction: column;
}
.box-card .card-header {
  font-size: 1.1em;
  font-weight: bold;
  color: #303133;
}
.box-card p {
  margin-top: 10px;
  color: #606266;
}
.box-card .el-empty {
  flex-grow: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.box-card .el-button {
  margin-top: auto; /* 将按钮推到底部 */
}
</style>
