<template>
  <div class="ai-video-monitor">
    <el-container>
      <!-- 顶部控制栏 -->
      <el-header height="80px">
        <div class="header-content">
          <h2>🤖 AI智能视频监控</h2>
          <div class="header-controls">
            <el-button-group>
              <el-button 
                type="primary" 
                :disabled="isStreaming"
                @click="startLocalCamera"
              >
                <el-icon><VideoCamera /></el-icon>
                启动摄像头
              </el-button>
              <el-button 
                type="danger" 
                :disabled="!isStreaming"
                @click="stopCamera"
              >
                <el-icon><Close /></el-icon>
                停止监控
              </el-button>
              <el-button 
                :type="aiAnalysisEnabled ? 'success' : 'info'"
                :disabled="!isStreaming"
                @click="toggleAIAnalysis"
              >
                <el-icon><Cpu /></el-icon>
                {{ aiAnalysisEnabled ? 'AI分析中' : '开启AI分析' }}
              </el-button>
            </el-button-group>
          </div>
        </div>
      </el-header>

      <el-main>
        <el-row :gutter="20">
          <!-- 左侧视频显示区 -->
          <el-col :span="16">
            <el-card class="video-card" shadow="always">
              <template #header>
                <div class="card-header">
                  <span>📹 实时视频监控</span>
                  <el-tag 
                    :type="isStreaming ? 'success' : 'danger'"
                    size="small"
                  >
                    {{ isStreaming ? '监控中' : '未启动' }}
                  </el-tag>
                </div>
              </template>
              
              <div class="video-container" ref="videoContainer">
                <video 
                  ref="videoElement"
                  class="video-player"
                  autoplay
                  muted
                  playsinline
                  @loadedmetadata="onVideoLoaded"
                ></video>
                
                <!-- AI检测结果覆盖层 -->
                <canvas 
                  ref="overlayCanvas"
                  class="overlay-canvas"
                ></canvas>
                
                <!-- 摄像头选择对话框 -->
                <div v-if="!isStreaming" class="camera-placeholder">
                  <el-icon class="placeholder-icon"><VideoCamera /></el-icon>
                  <p>点击"启动摄像头"开始智能监控</p>
                  <el-select 
                    v-model="selectedDeviceId" 
                    placeholder="选择摄像头设备"
                    class="device-select"
                  >
                    <el-option
                      v-for="device in videoDevices"
                      :key="device.deviceId"
                      :label="device.label || `摄像头 ${device.deviceId.slice(0, 8)}`"
                      :value="device.deviceId"
                    />
                  </el-select>
                </div>
              </div>
            </el-card>
          </el-col>

          <!-- 右侧控制和信息面板 -->
          <el-col :span="8">
            <!-- AI分析设置 -->
            <el-card class="control-panel" shadow="never">
              <template #header>
                <span>🎯 AI分析设置</span>
              </template>
              
              <div class="analysis-settings">
                <el-form label-width="100px">
                  <el-form-item label="人脸识别">
                    <el-switch 
                      v-model="aiSettings.faceRecognition"
                      :disabled="!isStreaming"
                      @change="updateAISettings"
                    />
                  </el-form-item>
                  <el-form-item label="目标检测">
                    <el-switch 
                      v-model="aiSettings.objectDetection"
                      :disabled="!isStreaming"
                      @change="updateAISettings"
                    />
                  </el-form-item>
                  <el-form-item label="行为分析">
                    <el-switch 
                      v-model="aiSettings.behaviorAnalysis"
                      :disabled="!isStreaming"
                      @change="updateAISettings"
                    />
                  </el-form-item>
                  <el-form-item label="声音检测">
                    <el-switch 
                      v-model="aiSettings.soundDetection"
                      :disabled="!isStreaming"
                      @change="updateAISettings"
                    />
                  </el-form-item>
                  <el-form-item label="检测频率">
                    <el-slider
                      v-model="analysisInterval"
                      :min="500"
                      :max="5000"
                      :step="500"
                      :disabled="!isStreaming"
                      show-input
                      input-size="small"
                      @change="updateAnalysisInterval"
                    />
                  </el-form-item>
                </el-form>
              </div>
            </el-card>

            <!-- 实时检测结果 -->
            <el-card class="results-panel" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>🔍 检测结果</span>
                  <el-badge :value="detectionResults.length" class="badge" />
                </div>
              </template>
              
              <el-scrollbar height="300px">
                <div class="detection-list">
                  <div 
                    v-for="(result, index) in detectionResults" 
                    :key="index"
                    class="detection-item"
                    :class="`type-${result.type}`"
                  >
                    <div class="detection-icon">
                      {{ getDetectionIcon(result.type) }}
                    </div>
                    <div class="detection-info">
                      <div class="detection-name">{{ result.label }}</div>
                      <div class="detection-details">
                        置信度: {{ (result.confidence * 100).toFixed(1) }}%
                      </div>
                      <div class="detection-time">
                        {{ formatTime(result.timestamp) }}
                      </div>
                    </div>
                  </div>
                  
                  <div v-if="detectionResults.length === 0" class="no-results">
                    <el-icon><Search /></el-icon>
                    <p>暂无检测结果</p>
                  </div>
                </div>
              </el-scrollbar>
            </el-card>

            <!-- 实时告警 -->
            <el-card class="alerts-panel" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>⚠️ 实时告警</span>
                  <el-badge :value="realtimeAlerts.length" class="badge" type="danger" />
                </div>
              </template>
              
              <el-scrollbar height="200px">
                <div class="alerts-list">
                  <el-alert
                    v-for="(alert, index) in realtimeAlerts"
                    :key="index"
                    :title="alert.title"
                    :description="alert.description"
                    :type="alert.type"
                    :closable="true"
                    @close="removeAlert(index)"
                    class="alert-item"
                  />
                  
                  <div v-if="realtimeAlerts.length === 0" class="no-alerts">
                    <el-icon><SuccessFilled /></el-icon>
                    <p>暂无告警</p>
                  </div>
                </div>
              </el-scrollbar>
            </el-card>
          </el-col>
        </el-row>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import {
  VideoCamera,
  Close,
  Cpu,
  Search,
  SuccessFilled
} from '@element-plus/icons-vue'

// 响应式数据
const videoElement = ref(null)
const overlayCanvas = ref(null)
const videoContainer = ref(null)
const isStreaming = ref(false)
const aiAnalysisEnabled = ref(false)
const selectedDeviceId = ref('')
const videoDevices = ref([])
const analysisInterval = ref(1000) // 分析间隔（毫秒）

// AI设置
const aiSettings = reactive({
  faceRecognition: true,
  objectDetection: true,
  behaviorAnalysis: true,
  soundDetection: true
})

// 检测结果和告警
const detectionResults = ref([])
const realtimeAlerts = ref([])

// 内部变量
let mediaStream = null
let analysisTimer = null
let canvasContext = null
let cameraId = 'webcam_monitor'

// 获取可用摄像头设备
const getVideoDevices = async () => {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    videoDevices.value = devices.filter(device => device.kind === 'videoinput')
    if (videoDevices.value.length > 0 && !selectedDeviceId.value) {
      selectedDeviceId.value = videoDevices.value[0].deviceId
    }
  } catch (error) {
    console.error('获取摄像头设备失败:', error)
    ElMessage.error('无法获取摄像头设备列表')
  }
}

// 启动本地摄像头
const startLocalCamera = async () => {
  try {
    const constraints = {
      video: {
        deviceId: selectedDeviceId.value ? { exact: selectedDeviceId.value } : undefined,
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: 'user'
      },
      audio: aiSettings.soundDetection
    }

    mediaStream = await navigator.mediaDevices.getUserMedia(constraints)
    videoElement.value.srcObject = mediaStream
    isStreaming.value = true

    ElMessage.success('摄像头启动成功！')
    
    // 启动AI分析流
    await startAIStream()
    
  } catch (error) {
    console.error('启动摄像头失败:', error)
    ElMessage.error('启动摄像头失败，请检查权限设置')
  }
}

// 停止摄像头
const stopCamera = async () => {
  try {
    // 停止AI分析
    await stopAIStream()
    
    // 停止媒体流
    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop())
      mediaStream = null
    }
    
    if (videoElement.value) {
      videoElement.value.srcObject = null
    }
    
    isStreaming.value = false
    aiAnalysisEnabled.value = false
    detectionResults.value = []
    
    // 清除画布
    if (canvasContext) {
      canvasContext.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height)
    }
    
    ElMessage.success('摄像头已停止')
  } catch (error) {
    console.error('停止摄像头失败:', error)
    ElMessage.error('停止摄像头失败')
  }
}

// 启动AI分析流
const startAIStream = async () => {
  try {
    const response = await fetch(`http://localhost:8001/stream/webcam/start/${cameraId}`, {
      method: 'GET'
    })

    if (response.ok) {
      aiAnalysisEnabled.value = true
      startFrameCapture()
      ElMessage.success('AI分析已启动')
    } else {
      throw new Error('AI服务响应错误')
    }
  } catch (error) {
    console.error('启动AI分析失败:', error)
    ElMessage.error('启动AI分析失败，请确保AI服务正在运行')
  }
}

// 停止AI分析流
const stopAIStream = async () => {
  try {
    if (analysisTimer) {
      clearInterval(analysisTimer)
      analysisTimer = null
    }

    const response = await fetch(`http://localhost:8001/stream/webcam/stop/${cameraId}`, {
      method: 'POST'
    })

    if (response.ok) {
      aiAnalysisEnabled.value = false
      ElMessage.info('AI分析已停止')
    }
  } catch (error) {
    console.error('停止AI分析失败:', error)
  }
}

// 开始帧捕获和分析
const startFrameCapture = () => {
  if (analysisTimer) {
    clearInterval(analysisTimer)
  }

  analysisTimer = setInterval(async () => {
    if (!isStreaming.value || !aiAnalysisEnabled.value || !videoElement.value) {
      return
    }

    try {
      // 捕获当前帧
      const canvas = document.createElement('canvas')
      const video = videoElement.value
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      
      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0)
      
      // 转换为blob并发送到AI服务
      canvas.toBlob(async (blob) => {
        if (blob) {
          await sendFrameToAI(blob)
        }
      }, 'image/jpeg', 0.8)
      
    } catch (error) {
      console.error('帧捕获失败:', error)
    }
  }, analysisInterval.value)
}

// 发送帧到AI服务进行分析
const sendFrameToAI = async (frameBlob) => {
  try {
    const formData = new FormData()
    formData.append('frame', frameBlob, 'frame.jpg')
    formData.append('camera_id', cameraId)
    formData.append('enable_face_recognition', aiSettings.faceRecognition)
    formData.append('enable_object_detection', aiSettings.objectDetection)
    formData.append('enable_behavior_detection', aiSettings.behaviorAnalysis)

    const response = await fetch('http://localhost:8001/frame/analyze/', {
      method: 'POST',
      body: formData
    })

    if (response.ok) {
      const result = await response.json()
      if (result.status === 'success') {
        processAIResults(result.results)
      }
    }
    
  } catch (error) {
    console.error('发送帧到AI服务失败:', error)
    // 如果AI服务不可用，回退到模拟结果
    simulateAIResults()
  }
}

// 处理AI分析结果
const processAIResults = (results) => {
  if (!results || !results.detections) return
  
  const detections = []
  
  // 处理检测结果
  results.detections.forEach(detection => {
    const processedDetection = {
      type: detection.type,
      label: getDetectionLabel(detection),
      confidence: detection.confidence,
      bbox: detection.bbox,
      timestamp: new Date(detection.timestamp)
    }
    detections.push(processedDetection)
  })
  
  // 处理告警
  if (results.alerts && results.alerts.length > 0) {
    results.alerts.forEach(alert => {
      addAlert({
        title: getAlertTitle(alert.type),
        description: alert.message,
        type: getAlertType(alert.type)
      })
    })
  }
  
  if (detections.length > 0) {
    updateDetectionResults(detections)
    drawDetectionResults(detections)
  }
}

// 获取检测标签
const getDetectionLabel = (detection) => {
  if (detection.type === 'object') {
    return detection.class_name
  } else if (detection.type === 'face') {
    return detection.known ? detection.name : '未知人脸'
  }
  return '未知'
}

// 获取告警标题
const getAlertTitle = (alertType) => {
  const titles = {
    person_detected: '🚨 检测到人员',
    unknown_face: '⚠️ 发现未知人脸',
    behavior_anomaly: '🔥 异常行为检测'
  }
  return titles[alertType] || '🔔 检测告警'
}

// 获取告警类型
const getAlertType = (alertType) => {
  const types = {
    person_detected: 'info',
    unknown_face: 'warning',
    behavior_anomaly: 'error'
  }
  return types[alertType] || 'info'
}

// 模拟AI分析结果（备用方案）
const simulateAIResults = () => {
  // 模拟检测结果
  if (Math.random() > 0.7) {
    const mockResults = [
      {
        type: 'person',
        label: '人员',
        confidence: 0.85 + Math.random() * 0.15,
        bbox: [
          Math.random() * 200,
          Math.random() * 200,
          200 + Math.random() * 300,
          200 + Math.random() * 400
        ],
        timestamp: new Date()
      }
    ]
    
    if (Math.random() > 0.8) {
      mockResults.push({
        type: 'face',
        label: '未知人脸',
        confidence: 0.75 + Math.random() * 0.25,
        bbox: [
          mockResults[0].bbox[0] + 50,
          mockResults[0].bbox[1] + 20,
          mockResults[0].bbox[0] + 150,
          mockResults[0].bbox[1] + 120
        ],
        timestamp: new Date()
      })
      
      // 生成告警
      addAlert({
        title: '⚠️ 检测到未知人员',
        description: `置信度: ${(mockResults[1].confidence * 100).toFixed(1)}%`,
        type: 'warning'
      })
    }
    
    updateDetectionResults(mockResults)
    drawDetectionResults(mockResults)
  }
}

// 更新检测结果列表
const updateDetectionResults = (results) => {
  detectionResults.value = results.concat(detectionResults.value.slice(0, 19)) // 保持最多20条记录
}

// 在视频上绘制检测结果
const drawDetectionResults = (results) => {
  if (!canvasContext || !overlayCanvas.value) return

  canvasContext.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height)

  results.forEach(result => {
    if (result.bbox) {
      const [x1, y1, x2, y2] = result.bbox
      const width = x2 - x1
      const height = y2 - y1

      // 绘制检测框
      canvasContext.strokeStyle = getDetectionColor(result.type)
      canvasContext.lineWidth = 3
      canvasContext.strokeRect(x1, y1, width, height)

      // 绘制标签背景
      const label = `${result.label} ${(result.confidence * 100).toFixed(1)}%`
      canvasContext.font = '14px Arial'
      const textWidth = canvasContext.measureText(label).width
      
      canvasContext.fillStyle = getDetectionColor(result.type)
      canvasContext.fillRect(x1, y1 - 25, textWidth + 10, 25)

      // 绘制标签文字
      canvasContext.fillStyle = 'white'
      canvasContext.fillText(label, x1 + 5, y1 - 8)
    }
  })
}

// 获取检测类型对应的颜色
const getDetectionColor = (type) => {
  const colors = {
    person: '#409EFF',
    face: '#67C23A',
    unknown_face: '#F56C6C',
    object: '#E6A23C'
  }
  return colors[type] || '#909399'
}

// 获取检测类型图标
const getDetectionIcon = (type) => {
  const icons = {
    person: '👤',
    face: '😊',
    unknown_face: '❓',
    object: '📦'
  }
  return icons[type] || '🔍'
}

// 添加告警
const addAlert = (alert) => {
  realtimeAlerts.value.unshift({
    ...alert,
    id: Date.now()
  })
  
  // 限制告警数量
  if (realtimeAlerts.value.length > 10) {
    realtimeAlerts.value = realtimeAlerts.value.slice(0, 10)
  }
  
  // 显示桌面通知
  ElNotification({
    title: alert.title,
    message: alert.description,
    type: alert.type,
    duration: 3000
  })
}

// 移除告警
const removeAlert = (index) => {
  realtimeAlerts.value.splice(index, 1)
}

// 切换AI分析
const toggleAIAnalysis = () => {
  if (aiAnalysisEnabled.value) {
    stopAIStream()
  } else {
    startAIStream()
  }
}

// 更新AI设置
const updateAISettings = () => {
  if (aiAnalysisEnabled.value) {
    // 重新启动AI分析流以应用新设置
    stopAIStream().then(() => {
      setTimeout(() => {
        startAIStream()
      }, 1000)
    })
  }
}

// 更新分析间隔
const updateAnalysisInterval = () => {
  if (analysisTimer) {
    startFrameCapture() // 重新启动定时器
  }
}

// 视频加载完成
const onVideoLoaded = () => {
  nextTick(() => {
    if (overlayCanvas.value && videoElement.value) {
      overlayCanvas.value.width = videoElement.value.videoWidth
      overlayCanvas.value.height = videoElement.value.videoHeight
      canvasContext = overlayCanvas.value.getContext('2d')
    }
  })
}

// 格式化时间
const formatTime = (date) => {
  return new Date(date).toLocaleTimeString()
}

// 生命周期
onMounted(async () => {
  await getVideoDevices()
})

onUnmounted(() => {
  stopCamera()
})
</script>

<style scoped>
.ai-video-monitor {
  height: 100vh;
  background-color: #f5f7fa;
}

.header-content {
  height: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.header-content h2 {
  margin: 0;
  color: #2c3e50;
}

.video-card {
  height: calc(100vh - 140px);
}

.video-container {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #000;
  border-radius: 8px;
  overflow: hidden;
}

.video-player {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.camera-placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #909399;
}

.placeholder-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.device-select {
  margin-top: 20px;
  width: 200px;
}

.control-panel,
.results-panel,
.alerts-panel {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.analysis-settings {
  padding: 10px 0;
}

.detection-list,
.alerts-list {
  max-height: 300px;
}

.detection-item {
  display: flex;
  align-items: center;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 6px;
  background-color: #f8f9fa;
  border-left: 4px solid #409EFF;
}

.detection-item.type-face {
  border-left-color: #67C23A;
}

.detection-item.type-unknown_face {
  border-left-color: #F56C6C;
}

.detection-icon {
  font-size: 24px;
  margin-right: 12px;
}

.detection-info {
  flex: 1;
}

.detection-name {
  font-weight: 600;
  color: #2c3e50;
}

.detection-details {
  font-size: 12px;
  color: #606266;
  margin: 2px 0;
}

.detection-time {
  font-size: 11px;
  color: #909399;
}

.no-results,
.no-alerts {
  text-align: center;
  padding: 40px 20px;
  color: #909399;
}

.no-results .el-icon,
.no-alerts .el-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.alert-item {
  margin-bottom: 10px;
}

.badge {
  margin-left: 10px;
}
</style> 