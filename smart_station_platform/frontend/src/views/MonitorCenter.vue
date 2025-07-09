<template>
  <div class="monitor-center">
    <el-container>
      <!-- 左侧摄像头列表 -->
      <el-aside width="300px">
        <div class="camera-sidebar">
          <div class="sidebar-header">
            <h3>监控列表</h3>
            <el-button type="primary" size="small" @click="showAddDialog">
              <el-icon><Plus /></el-icon>
              添加摄像头
            </el-button>
          </div>
          
          <el-input
            v-model="searchQuery"
            placeholder="搜索摄像头..."
            prefix-icon="Search"
            clearable
            class="search-input"
          />
          
          <el-scrollbar height="calc(100vh - 180px)">
            <el-collapse v-model="activeGroups" accordion>
              <el-collapse-item 
                v-for="group in filteredCameraGroups" 
                :key="group.id" 
                :title="group.name"
                :name="group.id"
              >
                <template #title>
                  <div class="group-title">
                    <span>{{ group.name }}</span>
                    <el-tag size="small" type="info">{{ group.cameras.length }}</el-tag>
                  </div>
                </template>
                
                <div class="camera-list">
                  <div 
                    v-for="camera in group.cameras"
                    :key="camera.id"
                    class="camera-item"
                    :class="{ active: selectedCamera?.id === camera.id }"
                    @click="selectCamera(camera)"
                  >
                    <div class="camera-info">
                      <div class="camera-name">{{ camera.name }}</div>
                      <div class="camera-location">{{ camera.location }}</div>
                    </div>
                    <el-tag 
                      size="small" 
                      :type="camera.status === 'online' ? 'success' : 'danger'"
                    >
                      {{ camera.status === 'online' ? '在线' : '离线' }}
                    </el-tag>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </el-scrollbar>
        </div>
      </el-aside>
      
      <!-- 主要内容区 -->
      <el-container>
        <el-header height="60px">
          <div class="header-content">
            <div class="camera-info" v-if="selectedCamera">
              <h2>{{ selectedCamera.name }}</h2>
              <el-tag>{{ selectedCamera.location }}</el-tag>
            </div>
            <div class="header-controls">
              <el-button-group>
                <el-button 
                  :type="isRecording ? 'danger' : 'primary'"
                  @click="toggleRecording"
                >
                  <el-icon><VideoPlay v-if="!isRecording" /><VideoPause v-else /></el-icon>
                  {{ isRecording ? '停止录制' : '开始录制' }}
                </el-button>
                <el-button 
                  type="primary" 
                  @click="toggleFullscreen"
                >
                  <el-icon><FullScreen /></el-icon>
                  全屏
                </el-button>
              </el-button-group>
            </div>
          </div>
        </el-header>
        
        <el-main>
          <el-row :gutter="20" class="main-content">
            <!-- 视频显示区域 -->
            <el-col :span="18">
              <el-card class="video-card" shadow="never">
                <div class="video-container" ref="videoContainer">
                  <div class="video-wrapper" ref="videoWrapper">
                    <video 
                      ref="videoPlayer"
                      class="video-player"
                      :src="streamUrl"
                      controls
                      autoplay
                      muted
                    ></video>
                    <canvas 
                      ref="overlayCanvas"
                      class="overlay-canvas"
                      @mousedown="startDrawing"
                      @mousemove="drawing"
                      @mouseup="endDrawing"
                    ></canvas>
                  </div>
                  
                  <!-- 视频控制面板 -->
                  <div class="video-controls">
                    <el-row :gutter="20">
                      <el-col :span="8">
                        <el-card shadow="never" class="control-card">
                          <template #header>
                            <span>画面控制</span>
                          </template>
                          <div class="control-item">
                            <span>亮度</span>
                            <el-slider
                              v-model="brightness"
                              :min="0"
                              :max="200"
                              :step="1"
                              @change="updateVideoFilters"
                            />
                          </div>
                          <div class="control-item">
                            <span>对比度</span>
                            <el-slider
                              v-model="contrast"
                              :min="0"
                              :max="200"
                              :step="1"
                              @change="updateVideoFilters"
                            />
                          </div>
                        </el-card>
                      </el-col>
                      <el-col :span="8">
                        <el-card shadow="never" class="control-card">
                          <template #header>
                            <span>PTZ控制</span>
                          </template>
                          <div class="ptz-controls">
                            <el-button-group>
                              <el-button @click="ptzControl('up')">上</el-button>
                              <el-button @click="ptzControl('down')">下</el-button>
                              <el-button @click="ptzControl('left')">左</el-button>
                              <el-button @click="ptzControl('right')">右</el-button>
                            </el-button-group>
                            <el-button-group>
                              <el-button @click="ptzControl('zoomIn')">放大</el-button>
                              <el-button @click="ptzControl('zoomOut')">缩小</el-button>
                            </el-button-group>
                          </div>
                        </el-card>
                      </el-col>
                      <el-col :span="8">
                        <el-card shadow="never" class="control-card">
                          <template #header>
                            <span>区域管理</span>
                          </template>
                          <div class="area-controls">
                            <el-button 
                              :type="isDrawing ? 'danger' : 'warning'"
                              @click="toggleDrawMode"
                            >
                              {{ isDrawing ? '退出绘制' : '绘制区域' }}
                            </el-button>
                            <el-button 
                              type="success" 
                              :disabled="!isDrawing"
                              @click="saveArea"
                            >
                              保存区域
                            </el-button>
                            <el-button 
                              type="danger" 
                              @click="clearAreas"
                            >
                              清除区域
                            </el-button>
                          </div>
                        </el-card>
                      </el-col>
                    </el-row>
                  </div>
                </div>
              </el-card>
            </el-col>
            
            <!-- AI分析和告警 -->
            <el-col :span="6">
              <el-card class="ai-panel" shadow="never">
                <template #header>
                  <div class="panel-header">
                    <span>AI分析</span>
                    <el-switch
                      v-model="aiEnabled"
                      active-text="开启"
                      inactive-text="关闭"
                    />
                  </div>
                </template>
                
                <el-tabs v-model="activeTab">
                  <el-tab-pane label="实时告警" name="alerts">
                    <div class="alert-stats">
                      <div class="stat-item">
                        <div class="stat-value">{{ realtimeAlerts.length }}</div>
                        <div class="stat-label">今日告警</div>
                      </div>
                    </div>
                    <el-scrollbar height="400px">
                      <div class="alert-list">
                        <div 
                          v-for="alert in realtimeAlerts" 
                          :key="alert.id"
                          class="alert-item"
                          :class="alert.type"
                        >
                          <div class="alert-time">{{ alert.time }}</div>
                          <div class="alert-type">{{ alert.type }}</div>
                          <div class="alert-location">{{ alert.location }}</div>
                        </div>
                      </div>
                      <el-empty v-if="realtimeAlerts.length === 0" description="暂无告警" />
                    </el-scrollbar>
                  </el-tab-pane>
                  
                  <el-tab-pane label="人脸识别" name="face">
                    <div class="analysis-section">
                      <div class="stat-item">
                        <div class="stat-value">{{ faceCount }}</div>
                        <div class="stat-label">检测到的人数</div>
                      </div>
                      <div class="face-list">
                        <div 
                          v-for="face in detectedFaces" 
                          :key="face.id"
                          class="face-item"
                        >
                          <el-avatar :src="face.image || '/default-avatar.png'" />
                          <div class="face-info">
                            <div class="face-name">{{ face.name || '未识别' }}</div>
                            <el-tag size="small" :type="face.type">
                              {{ face.confidence }}%
                            </el-tag>
                          </div>
                        </div>
                      </div>
                    </div>
                  </el-tab-pane>
                  
                  <el-tab-pane label="行为分析" name="behavior">
                    <div class="analysis-section">
                      <el-descriptions :column="1" border>
                        <el-descriptions-item label="异常行为">
                          {{ abnormalBehavior || '无' }}
                        </el-descriptions-item>
                        <el-descriptions-item label="人流量">
                          {{ peopleCount }}
                        </el-descriptions-item>
                        <el-descriptions-item label="区域入侵">
                          <el-tag :type="areaInvasion ? 'danger' : 'success'">
                            {{ areaInvasion ? '是' : '否' }}
                          </el-tag>
                        </el-descriptions-item>
                      </el-descriptions>
                    </div>
                  </el-tab-pane>
                </el-tabs>
              </el-card>
            </el-col>
          </el-row>
        </el-main>
      </el-container>
    </el-container>
    
    <!-- 添加摄像头对话框 -->
    <el-dialog
      v-model="addDialogVisible"
      title="添加摄像头"
      width="500px"
    >
      <el-form
        ref="addFormRef"
        :model="addForm"
        :rules="addRules"
        label-width="100px"
      >
        <el-form-item label="摄像头名称" prop="name">
          <el-input v-model="addForm.name" />
        </el-form-item>
        <el-form-item label="所属分组" prop="groupId">
          <el-select v-model="addForm.groupId" placeholder="选择分组">
            <el-option
              v-for="group in cameraGroups"
              :key="group.id"
              :label="group.name"
              :value="group.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="RTSP地址" prop="rtspUrl">
          <el-input v-model="addForm.rtspUrl" />
        </el-form-item>
        <el-form-item label="位置信息" prop="location">
          <el-input v-model="addForm.location" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="handleAddCamera">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { 
  Plus, 
  Search, 
  VideoPlay, 
  VideoPause, 
  FullScreen 
} from '@element-plus/icons-vue';

// 状态定义
const searchQuery = ref('');
const activeGroups = ref(['group1']);
const selectedCamera = ref(null);
const streamUrl = ref('');
const isRecording = ref(false);
const aiEnabled = ref(true);
const activeTab = ref('alerts');
const videoContainer = ref(null);
const videoWrapper = ref(null);
const videoPlayer = ref(null);
const overlayCanvas = ref(null);

// 视频控制参数
const brightness = ref(100);
const contrast = ref(100);

// AI分析数据
const faceCount = ref(0);
const detectedFaces = ref([
  { id: 1, name: '张三', image: null, confidence: 98, type: 'success' },
  { id: 2, name: '李四', image: null, confidence: 95, type: 'success' },
  { id: 3, name: null, image: null, confidence: 85, type: 'warning' }
]);

const abnormalBehavior = ref('奔跑');
const peopleCount = ref(15);
const areaInvasion = ref(false);

// 摄像头分组数据
const cameraGroups = ref([
  {
    id: 'group1',
    name: '一楼大厅',
    cameras: [
      { id: 'cam1', name: '前门摄像头', status: 'online', location: '大厅入口' },
      { id: 'cam2', name: '后门摄像头', status: 'online', location: '大厅后侧' }
    ]
  },
  {
    id: 'group2',
    name: '二楼办公区',
    cameras: [
      { id: 'cam3', name: '走廊摄像头', status: 'offline', location: '走廊中段' },
      { id: 'cam4', name: '会议室摄像头', status: 'online', location: '大会议室' }
    ]
  }
]);

// 实时告警数据
const realtimeAlerts = reactive([
  { id: 1, time: '14:30', type: '陌生人闯入', location: '大厅入口' },
  { id: 2, time: '14:25', type: '区域入侵', location: '办公区' },
  { id: 3, time: '14:20', type: '人流量异常', location: '走廊' }
]);

// 添加摄像头相关
const addDialogVisible = ref(false);
const adding = ref(false);
const addFormRef = ref(null);
const addForm = reactive({
  name: '',
  groupId: '',
  rtspUrl: '',
  location: ''
});

const addRules = {
  name: [
    { required: true, message: '请输入摄像头名称', trigger: 'blur' },
    { min: 2, max: 20, message: '长度在 2 到 20 个字符', trigger: 'blur' }
  ],
  groupId: [
    { required: true, message: '请选择所属分组', trigger: 'change' }
  ],
  rtspUrl: [
    { required: true, message: '请输入RTSP地址', trigger: 'blur' },
    { pattern: /^rtsp:\/\/.+/, message: '请输入正确的RTSP地址', trigger: 'blur' }
  ],
  location: [
    { required: true, message: '请输入位置信息', trigger: 'blur' }
  ]
};

// 绘制相关
const isDrawing = ref(false);
let ctx = null;
let drawnAreas = reactive([]);
let currentDrawing = [];

// 计算属性
const filteredCameraGroups = computed(() => {
  if (!searchQuery.value) return cameraGroups.value;
  
  return cameraGroups.value.map(group => ({
    ...group,
    cameras: group.cameras.filter(camera =>
      camera.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      camera.location.toLowerCase().includes(searchQuery.value.toLowerCase())
    )
  })).filter(group => group.cameras.length > 0);
});

// 方法定义
const selectCamera = (camera) => {
  selectedCamera.value = camera;
  streamUrl.value = `rtsp://example.com/stream/${camera.id}`;
  ElMessage.success(`已切换到 ${camera.name}`);
  startAIAnalysis();
};

const toggleRecording = () => {
  isRecording.value = !isRecording.value;
  ElMessage.success(isRecording.value ? '开始录制' : '录制已停止');
};

const toggleFullscreen = () => {
  if (!videoContainer.value) return;
  
  if (!document.fullscreenElement) {
    videoContainer.value.requestFullscreen();
  } else {
    document.exitFullscreen();
  }
};

const updateVideoFilters = () => {
  if (!videoPlayer.value) return;
  videoPlayer.value.style.filter = `brightness(${brightness.value}%) contrast(${contrast.value}%)`;
};

const ptzControl = (direction) => {
  ElMessage.success(`PTZ控制：${direction}`);
};

const startAIAnalysis = () => {
  // 模拟AI分析数据更新
  setInterval(() => {
    if (!aiEnabled.value) return;
    
    faceCount.value = Math.floor(Math.random() * 10);
    peopleCount.value = Math.floor(Math.random() * 30);
    areaInvasion.value = Math.random() > 0.7;
  }, 3000);
};

const showAddDialog = () => {
  addDialogVisible.value = true;
  if (addFormRef.value) {
    addFormRef.value.resetFields();
  }
};

const handleAddCamera = async () => {
  if (!addFormRef.value) return;
  
  try {
    await addFormRef.value.validate();
    adding.value = true;
    
    // 模拟添加摄像头
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    const newCamera = {
      id: `cam${Date.now()}`,
      name: addForm.name,
      status: 'online',
      location: addForm.location
    };
    
    const group = cameraGroups.value.find(g => g.id === addForm.groupId);
    if (group) {
      group.cameras.push(newCamera);
    }
    
    ElMessage.success('添加摄像头成功');
    addDialogVisible.value = false;
  } catch (error) {
    ElMessage.error('添加摄像头失败');
  } finally {
    adding.value = false;
  }
};

// 绘制功能
const toggleDrawMode = () => {
  isDrawing.value = !isDrawing.value;
  if (isDrawing.value) {
    ElMessage.info('进入绘制模式，请在视频上点击绘制多边形');
    overlayCanvas.value.addEventListener('click', handleCanvasClick);
  } else {
    ElMessage.info('退出绘制模式');
    overlayCanvas.value.removeEventListener('click', handleCanvasClick);
    currentDrawing = [];
    redrawAreas();
  }
};

const handleCanvasClick = (event) => {
  const rect = overlayCanvas.value.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  currentDrawing.push({ x, y });
  redrawAreas();
  drawCurrentDrawing();
};

const redrawAreas = () => {
  if (!ctx) return;
  ctx.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height);
  drawnAreas.forEach(area => {
    drawPolygon(area, 'rgba(255, 0, 0, 0.3)', 'red');
  });
};

const drawCurrentDrawing = () => {
  if (currentDrawing.length < 1) return;
  ctx.beginPath();
  ctx.moveTo(currentDrawing[0].x, currentDrawing[0].y);
  for (let i = 1; i < currentDrawing.length; i++) {
    ctx.lineTo(currentDrawing[i].x, currentDrawing[i].y);
  }
  ctx.strokeStyle = 'yellow';
  ctx.lineWidth = 2;
  ctx.stroke();
};

const drawPolygon = (points, fillStyle, strokeStyle) => {
  if (points.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i++) {
    ctx.lineTo(points[i].x, points[i].y);
  }
  ctx.closePath();
  ctx.fillStyle = fillStyle;
  ctx.strokeStyle = strokeStyle;
  ctx.lineWidth = 2;
  ctx.fill();
  ctx.stroke();
};

const saveArea = () => {
  if (currentDrawing.length < 3) {
    ElMessage.warning('请至少绘制三个点来形成一个多边形区域！');
    return;
  }
  drawnAreas.push([...currentDrawing]);
  ElMessage.success('危险区域已保存！');
  currentDrawing = [];
  isDrawing.value = false;
  overlayCanvas.value.removeEventListener('click', handleCanvasClick);
  redrawAreas();
};

const clearAreas = () => {
  drawnAreas.splice(0, drawnAreas.length);
  currentDrawing = [];
  redrawAreas();
  ElMessage.info('所有危险区域已清除！');
};

// 危险区域绘制相关
let isDrawingArea = false;
let currentPath = [];

const startDrawing = (event) => {
  if (!isDrawing.value) return;
  isDrawingArea = true;
  const rect = overlayCanvas.value.getBoundingClientRect();
  currentPath = [{
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  }];
};

const drawing = (event) => {
  if (!isDrawingArea || !isDrawing.value) return;
  
  const rect = overlayCanvas.value.getBoundingClientRect();
  currentPath.push({
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  });
  
  drawPath();
};

const endDrawing = () => {
  isDrawingArea = false;
  if (currentPath.length > 2) {
    drawPath(true);
  }
  currentPath = [];
};

const drawPath = (closed = false) => {
  if (!ctx || currentPath.length === 0) return;
  
  ctx.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height);
  
  ctx.beginPath();
  ctx.moveTo(currentPath[0].x, currentPath[0].y);
  
  for (let i = 1; i < currentPath.length; i++) {
    ctx.lineTo(currentPath[i].x, currentPath[i].y);
  }
  
  if (closed) {
    ctx.closePath();
    ctx.fillStyle = 'rgba(255, 0, 0, 0.2)';
    ctx.fill();
  }
  
  ctx.strokeStyle = 'red';
  ctx.lineWidth = 2;
  ctx.stroke();
};

// 生命周期钩子
onMounted(() => {
  // 初始化画布
  if (overlayCanvas.value && videoWrapper.value) {
    ctx = overlayCanvas.value.getContext('2d');
    const rect = videoWrapper.value.getBoundingClientRect();
    overlayCanvas.value.width = rect.width;
    overlayCanvas.value.height = rect.height;
  }
  
  // 默认选择第一个摄像头
  if (cameraGroups.value.length > 0 && cameraGroups.value[0].cameras.length > 0) {
    selectCamera(cameraGroups.value[0].cameras[0]);
  }
});

onUnmounted(() => {
  // 清理资源
});
</script>

<style scoped>
.monitor-center {
  height: 100vh;
  background-color: #f5f7fa;
}

.camera-sidebar {
  height: 100vh;
  background-color: #fff;
  border-right: 1px solid #dcdfe6;
}

.sidebar-header {
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #dcdfe6;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.search-input {
  margin: 15px 20px;
  width: calc(100% - 40px);
}

.group-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.camera-list {
  padding: 10px;
}

.camera-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid #e4e7ed;
}

.camera-item:hover {
  background-color: #f5f7fa;
  border-color: #409eff;
}

.camera-item.active {
  background-color: #e6f7ff;
  border-color: #409eff;
}

.camera-info {
  flex: 1;
}

.camera-name {
  font-weight: 600;
  color: #2c3e50;
}

.camera-location {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.el-header {
  background-color: #fff;
  border-bottom: 1px solid #dcdfe6;
  padding: 0 20px;
}

.header-content {
  height: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.camera-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.camera-info h2 {
  margin: 0;
  font-size: 18px;
}

.main-content {
  height: calc(100vh - 60px);
  padding: 20px;
}

.video-card {
  height: 100%;
}

.video-container {
  height: 100%;
  position: relative;
}

.video-wrapper {
  position: relative;
  width: 100%;
  height: calc(100% - 200px);
  background-color: #000;
  border-radius: 4px;
  overflow: hidden;
}

.video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.video-controls {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
}

.control-card {
  height: 140px;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.control-item span {
  width: 60px;
  font-size: 14px;
}

.ptz-controls {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
}

.area-controls {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ai-panel {
  height: calc(100vh - 100px);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.alert-stats {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 6px;
  margin-bottom: 10px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.alert-list {
  padding: 10px 0;
}

.alert-item {
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 6px;
  border-left: 4px solid #409eff;
  background-color: #f8f9fa;
}

.alert-item.陌生人闯入 {
  border-left-color: #f56c6c;
}

.alert-item.区域入侵 {
  border-left-color: #e6a23c;
}

.alert-item.人流量异常 {
  border-left-color: #909399;
}

.alert-time {
  font-size: 12px;
  color: #909399;
}

.alert-type {
  font-weight: 600;
  color: #2c3e50;
  margin: 4px 0;
}

.alert-location {
  font-size: 12px;
  color: #606266;
}

.analysis-section {
  padding: 10px 0;
}

.face-list {
  margin-top: 20px;
}

.face-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
}

.face-info {
  flex: 1;
}

.face-name {
  font-weight: 600;
  color: #2c3e50;
}

:deep(.el-collapse-item__header) {
  font-weight: 600;
}

:deep(.el-tabs__content) {
  padding: 0;
}

@media (max-width: 1200px) {
  .el-aside {
    width: 250px !important;
  }
}
</style>
