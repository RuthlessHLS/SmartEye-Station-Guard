<template>
  <div class="alert-management-container">
    <h1>告警事件管理</h1>
    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm" class="filter-form">
        <el-form-item label="告警类型">
          <el-select v-model="filterForm.type" placeholder="选择类型" clearable>
            <el-option label="所有" value=""></el-option>
            <el-option label="陌生人闯入" value="stranger_intrusion"></el-option>
            <el-option label="明火烟雾" value="fire_smoke"></el-option>
            <el-option label="人员跌倒" value="person_fall"></el-option>
            <el-option label="异常声音: 尖叫" value="abnormal_sound_scream"></el-option>
            <el-option label="异常声音: 音量异常" value="acoustic_volume_anomaly"></el-option>
            <el-option label="异常声音: 高频" value="acoustic_high_frequency"></el-option>
            <el-option label="异常声音: 突发噪声" value="acoustic_sudden_noise"></el-option>
            <el-option label="未知人脸检测" value="unknown_face_detected"></el-option>
            </el-select>
        </el-form-item>
        <el-form-item label="处理状态">
          <el-select v-model="filterForm.status" placeholder="选择状态" clearable>
            <el-option label="所有" value=""></el-option>
            <el-option label="待确认" value="pending"></el-option>
            <el-option label="处理中" value="in_progress"></el-option>
            <el-option label="已解决" value="resolved"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filterForm.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始日期时间"
            end-placeholder="结束日期时间"
            value-format="YYYY-MM-DD HH:mm:ss"
          ></el-date-picker>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchAlerts">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="alert-list-card">
      <el-table :data="alerts" v-loading="loading" stripe border style="width: 100%" height="calc(100vh - 350px)">
        <el-table-column type="index" label="序号" width="60"></el-table-column>
        <el-table-column prop="alert_time" label="告警时间" width="180"></el-table-column>
        <el-table-column prop="camera_id" label="摄像头ID" width="100"></el-table-column>
        <el-table-column prop="event_type_display" label="告警类型" width="120"></el-table-column>
        <el-table-column prop="location_desc" label="告警位置" show-overflow-tooltip></el-table-column>
        <el-table-column prop="status_display" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row.status)">{{ scope.row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="handler" label="处理人" width="100"></el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="viewDetails(scope.row)">详情</el-button>
            <el-button
              size="small"
              type="warning"
              :disabled="scope.row.status === 'resolved'"
              @click="handleAlert(scope.row)"
            >
              处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="pagination.currentPage"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="pagination.total"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
        background
        class="pagination-container"
      ></el-pagination>
    </el-card>

    <el-dialog v-model="dialogVisible" title="告警详情" width="60%" destroy-on-close>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="告警ID">{{ currentAlert.id }}</el-descriptions-item>
        <el-descriptions-item label="告警类型">{{ currentAlert.event_type_display }}</el-descriptions-item>
        <el-descriptions-item label="告警时间">{{ currentAlert.alert_time }}</el-descriptions-item>
        <el-descriptions-item label="摄像头ID">{{ currentAlert.camera_id }}</el-descriptions-item>
        <el-descriptions-item label="告警状态">{{ currentAlert.status_display }}</el-descriptions-item>
        <el-descriptions-item label="处理人">{{ currentAlert.handler || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="告警位置" :span="2">{{ currentAlert.location_desc || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="置信度" :span="2">{{ (currentAlert.confidence * 100).toFixed(2) }}%</el-descriptions-item>
        <el-descriptions-item label="告警截图" :span="2">
          <el-image
            v-if="currentAlert.image_snapshot_url"
            :src="currentAlert.image_snapshot_url"
            fit="contain"
            style="width: 100%; max-height: 300px;"
          ></el-image>
          <span v-else>暂无截图</span>
        </el-descriptions-item>
        <el-descriptions-item label="视频回放" :span="2">
          <video
            v-if="currentAlert.video_clip_url"
            :src="currentAlert.video_clip_url"
            controls
            style="width: 100%; max-height: 300px;"
          ></video>
          <span v-else>暂无视频回放</span>
        </el-descriptions-item>
        <el-descriptions-item label="处理备注" :span="2">
          <el-input
            v-model="currentAlert.processing_notes"
            :rows="3"
            type="textarea"
            placeholder="请输入处理备注"
            :disabled="currentAlert.status === 'resolved'"
          ></el-input>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">关闭</el-button>
          <el-button
            type="primary"
            v-if="currentAlert.status !== 'resolved'"
            @click="updateAlertStatus"
          >
            更新状态
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import api from '../api'; // 导入API请求服务

const alerts = ref([]);
const loading = ref(false);
const filterForm = reactive({
  type: '',
  status: '',
  dateRange: [],
});
const pagination = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0,
});

const dialogVisible = ref(false);
const currentAlert = reactive({});

let ws = null; // WebSocket 实例

// 告警类型映射 (用于显示)
const alertTypeMap = {
  stranger_intrusion: '陌生人闯入',
  dangerous_area_intrusion: '危险区域入侵',
  person_fall: '人员跌倒',
  fire_smoke: '明火烟雾',
  abnormal_sound: '异常声音',
  // ...更多类型
};

// 告警状态映射 (用于显示)
const alertStatusMap = {
  pending: '待确认',
  in_progress: '处理中',
  resolved: '已解决',
};

onMounted(() => {
  fetchAlerts();
  connectWebSocket();
});

onUnmounted(() => {
  if (ws) {
    ws.close();
  }
});

const connectWebSocket = () => {
  ws = new WebSocket('ws://127.0.0.1:8000/ws/alerts/');

  ws.onopen = () => {
    console.log('Alert Management WebSocket connected');
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'alert' && data.data) {
      const newAlert = {
        ...data.data,
        alert_time: new Date(data.data.timestamp).toLocaleString(), // 转换时间格式
        event_type_display: alertTypeMap[data.data.event_type] || data.data.event_type,
        status_display: alertStatusMap[data.data.status || 'pending'], // 默认待确认
        status: data.data.status || 'pending',
        location_desc: JSON.stringify(data.data.location), // 简化位置描述
      };
      alerts.value.unshift(newAlert); // 将新告警添加到列表顶部
      pagination.total++; // 总数增加
      ElMessage.info(`收到新告警：${newAlert.event_type_display} - ${newAlert.alert_time}`);
    }
  };

  ws.onclose = () => {
    console.log('Alert Management WebSocket disconnected. Attempting reconnect...');
    setTimeout(connectWebSocket, 5000);
  };

  ws.onerror = (error) => {
    console.error('Alert Management WebSocket error:', error);
  };
};


const fetchAlerts = async () => {
  loading.value = true;
  try {
    const params = {
      page: pagination.currentPage,
      page_size: pagination.pageSize,
      event_type: filterForm.type, // 修改参数名为 event_type
      status: filterForm.status,
      start_time: filterForm.dateRange && filterForm.dateRange[0] ? filterForm.dateRange[0] : '',
      end_time: filterForm.dateRange && filterForm.dateRange[1] ? filterForm.dateRange[1] : '',
    };
    // 修正API路径，添加/api前缀
    const response = await api.alerts.getList(params);
    alerts.value = response.results.map(alert => {
      return {
      ...alert,
        alert_time: alert.timestamp.replace('T', ' ').slice(0, 19), // 保证与数据库一致
      event_type_display: alertTypeMap[alert.event_type] || alert.event_type,
      status_display: alertStatusMap[alert.status],
      location_desc: JSON.stringify(alert.location), // 简化位置描述
      };
    });
    pagination.total = response.count;
  } catch (error) {
    ElMessage.error('获取告警列表失败！');
    console.error('Fetch alerts error:', error);
  } finally {
    loading.value = false;
  }
};

const resetFilters = () => {
  filterForm.type = '';
  filterForm.status = '';
  filterForm.dateRange = [];
  pagination.currentPage = 1;
  fetchAlerts();
};

const getStatusTagType = (status) => {
  switch (status) {
    case 'pending': return 'danger';
    case 'in_progress': return 'warning';
    case 'resolved': return 'success';
    default: return 'info';
  }
};

const viewDetails = (row) => {
  Object.assign(currentAlert, row); // 赋值到 reactive 对象
  dialogVisible.value = true;
};

const handleAlert = (row) => {
  ElMessageBox.prompt('请输入处理备注', '处理告警', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPattern: /\S/, // 非空
    inputErrorMessage: '备注不能为空',
  })
    .then(async ({ value }) => {
      // 根据当前状态决定下一个状态
      let nextStatus = 'in_progress';
      if (row.status === 'in_progress') {
        nextStatus = 'resolved';
      }
      try {
        await api.alerts.handle(row.id, {
          status: nextStatus,
          processing_notes: value,
        });
        ElMessage.success(
          nextStatus === 'resolved' ? '告警已标记为已解决！' : '告警已标记为处理中！'
        );
        fetchAlerts(); // 刷新列表
      } catch (error) {
        ElMessage.error('处理告警失败！');
        console.error('Handle alert error:', error);
      }
    })
    .catch(() => {
      ElMessage.info('取消处理。');
    });
};

const updateAlertStatus = async () => {
  try {
    // 使用正确的API方法更新告警状态
    const newStatus = currentAlert.status === 'pending' ? 'in_progress' : 'resolved';
    await api.alerts.handle(currentAlert.id, {
      status: newStatus,
      processing_notes: currentAlert.processing_notes,
    });
    ElMessage.success('告警状态更新成功！');
    dialogVisible.value = false;
    fetchAlerts(); // 刷新列表
  } catch (error) {
    ElMessage.error('更新告警状态失败！');
    console.error('Update alert status error:', error);
  }
};

const handleSizeChange = (val) => {
  pagination.pageSize = val;
  fetchAlerts();
};

const handleCurrentChange = (val) => {
  pagination.currentPage = val;
  fetchAlerts();
};
</script>

<style scoped>
.alert-management-container {
  padding: 20px;
}
.alert-management-container h1 {
  text-align: center;
  margin-bottom: 20px;
}
.filter-card {
  margin-bottom: 20px;
}
.pagination-container {
  margin-top: 20px;
  justify-content: center;
  display: flex;
}
</style>
