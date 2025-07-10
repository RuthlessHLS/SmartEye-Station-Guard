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
          <div class="card-content">
            <p>此处将展示当前实时告警数量、重点区域风险等级等。</p>
            <el-empty description="暂无数据"></el-empty>
          </div>
          <el-button type="primary" @click="router.push('/monitor')">进入智能监控中心</el-button>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>运营数据洞察</span>
            </div>
          </template>
           <div class="card-content">
            <p>此处将展示客流量趋势、资源利用率等运营指标。</p>
            <el-empty description="暂无数据"></el-empty>
          </div>
          <el-button type="success" @click="router.push('/data-screen')">查看数据大屏</el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- 包含“快速导航”的整个 el-row 已经被删除了 -->

  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';

const router = useRouter();

// 【重要修改】
// 由于“退出登录”按钮已经从这个页面移除（现在位于全局导航栏 App.vue 中），
// 此处的 logout 函数和相关的 Element Plus 弹窗组件导入也一并移除了，让组件更简洁。

</script>

<style scoped>
.dashboard-container {
  padding: 20px;
}

.dashboard-container h1 {
  text-align: center;
  margin-bottom: 40px;
  font-size: 2em;
  color: #303133;
}

.box-card {
  height: 350px; /* 固定卡片高度 */
  display: flex;
  flex-direction: column;
}

.card-header {
  font-size: 1.2em;
  font-weight: bold;
}

.card-content {
  flex-grow: 1; /* 让内容区域占据所有剩余空间 */
  display: flex;
  flex-direction: column;
}

.card-content p {
  margin-bottom: 10px;
  color: #606266;
}

/* 让 el-empty 填满其父容器的剩余空间 */
.card-content .el-empty {
  flex-grow: 1;
}

/* 按钮总是位于卡片底部 */
.box-card .el-button {
  margin-top: auto; /* 使用 margin-top: auto 将按钮推到底部 */
  width: 100%; /* 让按钮宽度与卡片一致 */
  padding: 12px 0;
  font-size: 1em;
}
</style>
