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
                  <el-form-item label="火焰检测">
                    <el-switch
                      v-model="aiSettings.fireDetection"
                      :disabled="!isStreaming"
                      @change="updateAISettings"
                    />
                    <div class="frequency-hint">
                      <small style="color: #f56c6c;">
                        🔥 检测火焰及相关危险
                      </small>
                    </div>
                  </el-form-item>
                  <el-form-item label="实时模式">
                    <el-switch
                      v-model="aiSettings.realtimeMode"
                      :disabled="!isStreaming"
                      active-text="高频检测"
                      inactive-text="节能模式"
                      @change="updateAISettings"
                    />
                    <div class="frequency-hint">
                      <small v-if="aiSettings.realtimeMode" style="color: #409EFF;">
                        🚀 实时模式：~15FPS高频检测，响应更快
                      </small>
                      <small v-else style="color: #67C23A;">
                        💡 节能模式：智能调频，省电优化
                      </small>
                    </div>
                  </el-form-item>
                  <el-form-item label="检测频率">
                    <el-slider
                      v-model="analysisInterval"
                      :min="100"
                      :max="2000"
                      :step="100"
                      :disabled="!isStreaming"
                      show-input
                      input-size="small"
                      @change="updateAnalysisInterval"
                    />
                    <div class="frequency-hint">
                      <small>{{Math.round(1000/analysisInterval)}} FPS (推荐: 100-500ms)</small>
                    </div>
                  </el-form-item>

                  <el-form-item label="性能优化" v-if="isStreaming">
                    <div class="optimization-status">
                      <div class="opt-item">
                        <el-icon><Cpu /></el-icon>
                        <span>帧差检测: 已启用</span>
                      </div>
                      <div class="opt-item">
                        <el-icon><VideoCamera /></el-icon>
                        <span>动态画质: 自适应</span>
                      </div>
                      <div class="opt-item">
                        <el-text type="success" size="small">
                          当前延迟: {{ performanceStats.avgProcessTime }}ms
                        </el-text>
                      </div>
                      <div class="performance-advice" v-if="performanceStats.avgProcessTime > 0">
                        <el-alert
                          :title="getPerformanceAdvice().title"
                          :description="getPerformanceAdvice().advice"
                          :type="getPerformanceAdvice().level"
                          :closable="false"
                          size="small"
                          show-icon
                        />
                      </div>
                    </div>
                  </el-form-item>

                  <el-form-item label="检测框测试" v-if="isStreaming">
                    <div class="test-controls">
                      <el-button
                        type="primary"
                        size="small"
                        @click="testDetectionBoxes"
                        :icon="Search"
                      >
                        测试检测框显示
                      </el-button>
                      <el-button
                        type="success"
                        size="small"
                        @click="forceDrawTestBox"
                        :icon="Edit"
                      >
                        强制绘制测试框
                      </el-button>
                      <el-button
                        type="warning"
                        size="small"
                        @click="clearDetectionBoxes"
                        :icon="Close"
                      >
                        清除检测框
                      </el-button>
                      <el-button
                        type="danger"
                        size="small"
                        @click="resetDetectionCache"
                        :icon="Refresh"
                      >
                        重置跟踪
                      </el-button>
                      <el-text type="info" size="small">
                        如果检测框异常，可尝试重置跟踪缓存
                      </el-text>
                    </div>
                  </el-form-item>

                  <el-form-item label="危险区域" v-if="isStreaming">
                    <div class="zone-controls">
                      <el-button
                        type="danger"
                        size="small"
                        @click="showZoneManager = true"
                        :icon="Location"
                      >
                        区域管理
                      </el-button>
                      <el-button
                        type="warning"
                        size="small"
                        @click="startDrawingZone"
                        :disabled="isDrawingZone"
                        :icon="Edit"
                      >
                        {{ isDrawingZone ? '绘制中...' : '绘制区域' }}
                      </el-button>
                      <el-text type="info" size="small">
                        已设置 {{ dangerZones.length }} 个危险区域
                      </el-text>
                    </div>
                  </el-form-item>

                  <el-form-item label="音频监控" v-if="aiSettings.soundDetection && isStreaming">
                    <div class="audio-monitor">
                      <div class="audio-level-display">
                        <span class="audio-text">音量: {{ performanceStats.audioLevel }}%</span>
                        <div class="audio-bar">
                          <div
                            class="audio-level"
                            :style="{
                              width: performanceStats.audioLevel + '%',
                              backgroundColor: performanceStats.audioLevel > 50 ? '#f56c6c' : '#67c23a'
                            }"
                          ></div>
                        </div>
                      </div>
                    </div>
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

            <!-- 性能监控 -->
            <el-card class="performance-panel" shadow="never" v-show="aiAnalysisEnabled">
              <template #header>
                <span>📊 性能监控</span>
              </template>

              <div class="performance-stats">
                <div class="stat-item">
                  <span class="stat-label">检测FPS</span>
                  <span class="stat-value">{{ performanceStats.fps }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">平均延迟</span>
                  <span class="stat-value">{{ performanceStats.avgProcessTime }}ms</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">并发跳过</span>
                  <span class="stat-value">{{ performanceStats.skippedFrames }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">无变化跳过</span>
                  <span class="stat-value">{{ performanceStats.motionSkippedFrames }}</span>
                </div>
                <div class="stat-item" v-if="aiSettings.soundDetection">
                  <span class="stat-label">音量级别</span>
                  <span class="stat-value">{{ performanceStats.audioLevel }}%</span>
                </div>
              </div>
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

    <!-- 危险区域管理对话框 -->
    <el-dialog
      v-model="showZoneManager"
      title="🚨 危险区域管理"
      width="800px"
      draggable
    >
      <div class="zone-manager">
        <!-- 区域列表 -->
        <div class="zone-list">
          <h4>已配置区域</h4>
          <el-table :data="dangerZones" stripe>
            <el-table-column prop="name" label="区域名称" width="120" />
            <el-table-column label="顶点数">
              <template #default="{ row }">
                {{ row.coordinates.length }}个
              </template>
            </el-table-column>
            <el-table-column prop="min_distance_threshold" label="距离阈值(px)" width="100" />
            <el-table-column prop="time_in_area_threshold" label="停留阈值(s)" width="100" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'danger'">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ $index }">
                <el-button
                  type="danger"
                  size="small"
                  @click="removeDangerZone($index)"
                  :icon="Close"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div v-if="dangerZones.length === 0" class="no-zones">
            <el-icon><Location /></el-icon>
            <p>暂无危险区域，请先绘制区域</p>
          </div>
        </div>

        <!-- 添加新区域 -->
        <div v-if="currentZonePoints.length > 0" class="new-zone-form">
          <h4>设置新区域参数</h4>
          <el-form label-width="120px">
            <el-form-item label="区域名称">
              <el-input v-model="newZoneName" placeholder="例如：机器设备区" />
            </el-form-item>
            <el-form-item label="距离阈值">
              <el-input-number
                v-model="newZoneMinDistance"
                :min="0"
                :max="200"
                :step="10"
                controls-position="right"
              />
              <small>人员距离区域边缘小于此值时告警(像素)</small>
            </el-form-item>
            <el-form-item label="停留阈值">
              <el-input-number
                v-model="newZoneDwellTime"
                :min="0"
                :max="300"
                :step="5"
                controls-position="right"
              />
              <small>人员在区域内停留超过此值时告警(秒)</small>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveDangerZone">
                保存区域
              </el-button>
              <el-button @click="cancelDrawing">
                取消
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showZoneManager = false">关闭</el-button>
          <el-button type="primary" @click="syncZonesToAI">
            同步到AI服务
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import {
  VideoCamera,
  Close,
  Cpu,
  Search,
  SuccessFilled,
  Refresh,
  Edit,
  Location
} from '@element-plus/icons-vue'
import { backendService, aiService, requestWithRetry } from '@/api';

// 响应式数据
const videoElement = ref(null)
const overlayCanvas = ref(null)
const videoContainer = ref(null)
const isStreaming = ref(false)
const aiAnalysisEnabled = ref(false)
const selectedDeviceId = ref('')
const videoDevices = ref([])
const analysisInterval = ref(300) // 分析间隔（毫秒）- 平衡性能与实时性，默认更快

// AI设置
const aiSettings = reactive({
  faceRecognition: true,
  objectDetection: true,
  behaviorAnalysis: true,
  soundDetection: true,
  fireDetection: true,    // 火焰检测
  realtimeMode: false     // 实时模式：更高的检测频率
})

// 检测结果和告警
const detectionResults = ref([])
const realtimeAlerts = ref([])
const lastFrameDetections = ref([]) // 缓存上一帧的检测结果用于平滑

// 危险区域相关
const dangerZones = ref([]) // 危险区域列表
const isDrawingZone = ref(false) // 是否正在绘制区域
const currentZonePoints = ref([]) // 当前绘制的区域点
const showZoneManager = ref(false) // 显示区域管理面板
const newZoneName = ref('') // 新区域名称
const newZoneMinDistance = ref(50) // 最小距离阈值
const newZoneDwellTime = ref(10) // 停留时间阈值

// 内部变量
let mediaStream = null
let analysisTimer = null
let canvasContext = null
let cameraId = 'webcam_monitor'

// 告警去重机制
const alertCooldowns = new Map() // 存储各类型告警的冷却时间
const ALERT_COOLDOWN = 5000 // 5秒冷却时间，避免频繁弹窗
let isProcessingFrame = false // 防止并发处理帧

// 性能优化相关
let lastFrameData = null // 上一帧的图像数据，用于帧差检测
let audioContext = null // 音频上下文，用于音量检测
let audioAnalyser = null // 音频分析器
let audioDataArray = null // 音频数据数组
const MOTION_THRESHOLD = 0.015 // 帧差阈值，更敏感的检测
let consecutiveSlowFrames = 0 // 连续慢帧计数
let currentImageScale = 1 // 当前图像缩放比例，用于坐标转换

// 性能监控
const performanceStats = reactive({
  fps: 0,
  avgProcessTime: 0,
  processedFrames: 0,
  skippedFrames: 0,
  motionSkippedFrames: 0, // 因为无变化而跳过的帧
  audioLevel: 0 // 当前音量级别
})

let frameProcessTimes = []
let lastStatsUpdate = Date.now()

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

// 初始化音频分析
const initAudioAnalysis = async (stream) => {
  try {
    audioContext = new (window.AudioContext || window.webkitAudioContext)()
    audioAnalyser = audioContext.createAnalyser()
    audioAnalyser.fftSize = 256

    const source = audioContext.createMediaStreamSource(stream)
    source.connect(audioAnalyser)

    audioDataArray = new Uint8Array(audioAnalyser.frequencyBinCount)

    // 开始音频监控
    startAudioMonitoring()

  } catch (error) {
    console.error('音频分析初始化失败:', error)
  }
}

// 音频监控状态控制
let audioMonitoringActive = false
let audioMonitoringId = null

// 开始音频监控
const startAudioMonitoring = () => {
  if (audioMonitoringActive) return // 防止重复启动

  audioMonitoringActive = true

  const monitorAudio = () => {
    if (!audioMonitoringActive || !audioAnalyser || !audioDataArray) {
      audioMonitoringId = null
      return
    }

    audioAnalyser.getByteFrequencyData(audioDataArray)

    // 计算平均音量
    const average = audioDataArray.reduce((sum, value) => sum + value, 0) / audioDataArray.length
    performanceStats.audioLevel = Math.round(average / 255 * 100)

    // 检测异常音量
    if (average > 100) { // 阈值可调整
      const now = Date.now()
      const alertKey = 'audio_volume_high'

      if (!alertCooldowns.has(alertKey) || now - alertCooldowns.get(alertKey) > ALERT_COOLDOWN) {
        addAlert({
          title: '🔊 检测到高音量',
          description: `音量级别: ${performanceStats.audioLevel}%`,
          type: 'warning'
        })

        // 发送音频告警到AI服务
        sendAudioAlertToAI(performanceStats.audioLevel, 'high_volume')

        alertCooldowns.set(alertKey, now)
      }
    }

    // 只有在监控激活时才继续
    if (audioMonitoringActive) {
      audioMonitoringId = requestAnimationFrame(monitorAudio)
    }
  }

  monitorAudio()
}

// 停止音频监控
const stopAudioMonitoring = () => {
  audioMonitoringActive = false
  if (audioMonitoringId) {
    cancelAnimationFrame(audioMonitoringId)
    audioMonitoringId = null
  }
}

// 超高效帧差检测 - 判断画面是否有显著变化
const hasSignificantMotion = (currentImageData, lastImageData) => {
  if (!lastImageData) return true // 第一帧总是发送

  const threshold = MOTION_THRESHOLD
  let diffPixels = 0
  const sampleCount = Math.min(500, Math.floor(currentImageData.length / 32)) // 限制采样数量
  const step = Math.max(32, Math.floor(currentImageData.length / sampleCount))

  // 超级稀疏采样检测，大幅提高性能
  for (let i = 0; i < currentImageData.length; i += step) {
    if (i + 2 >= currentImageData.length || i + 2 >= lastImageData.length) break

    // 使用亮度差异检测（更高效）
    const currentBrightness = (currentImageData[i] + currentImageData[i + 1] + currentImageData[i + 2]) / 3
    const lastBrightness = (lastImageData[i] + lastImageData[i + 1] + lastImageData[i + 2]) / 3

    if (Math.abs(currentBrightness - lastBrightness) > 20) { // 亮度差异阈值
      diffPixels++
    }
  }

  const motionRatio = diffPixels / sampleCount
  return motionRatio > threshold
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

    // 如果启用了声音检测，初始化音频分析
    if (aiSettings.soundDetection && mediaStream.getAudioTracks().length > 0) {
      await initAudioAnalysis(mediaStream)
    } else {
      // 确保音频监控处于停止状态
      stopAudioMonitoring()
    }

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
    realtimeAlerts.value = []
    lastFrameDetections.value = [] // 清除检测缓存

    // 重置性能统计
    performanceStats.fps = 0
    performanceStats.avgProcessTime = 0
    performanceStats.processedFrames = 0
    performanceStats.skippedFrames = 0
    performanceStats.motionSkippedFrames = 0
    performanceStats.audioLevel = 0
    frameProcessTimes = []
    isProcessingFrame = false

    // 清理音频相关资源
    stopAudioMonitoring() // 停止音频监控循环
    if (audioContext) {
      audioContext.close()
      audioContext = null
    }
    audioAnalyser = null
    audioDataArray = null
    lastFrameData = null

    // 清除告警冷却时间
    alertCooldowns.clear()

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

// 启动AI分析
const startAIStream = async () => {
  if (!isStreaming.value) {
    ElMessage.warning('请先启动摄像头');
    return;
  }

  try {
    // 前端直接启动AI分析，不需要让AI服务读取摄像头
    // AI服务将通过 /frame/analyze/ 接口接收前端发送的帧数据
    aiAnalysisEnabled.value = true;
    ElMessage.success('AI分析已启动');
    await startFrameCapture(); // 启动帧捕获循环
  } catch (error) {
    console.error('AI分析启动失败:', error);
    ElMessage.error('AI分析启动失败: ' + error.message);
    aiAnalysisEnabled.value = false;
  }
};

// 停止AI分析
const stopAIStream = async () => {
  try {
    // 前端直接停止AI分析，清理本地状态
    aiAnalysisEnabled.value = false;
    if (analysisTimer) {
      clearInterval(analysisTimer);
      analysisTimer = null;
    }
    ElMessage.info('AI分析已停止');
  } catch (error) {
    console.error('停止AI分析失败:', error);
    ElMessage.error('停止AI分析失败: ' + error.message);
  }
};

// 开始帧捕获和分析
const startFrameCapture = () => {
  if (analysisTimer) {
    clearTimeout(analysisTimer)
  }



  const scheduleNextCapture = () => {
    if (!isStreaming.value || !aiAnalysisEnabled.value) return

    const interval = getDynamicInterval()
    analysisTimer = setTimeout(async () => {
      await captureAndAnalyze()
      scheduleNextCapture()  // 递归调度下一次捕获
    }, interval)
  }

  const captureAndAnalyze = async () => {
    if (!isStreaming.value || !aiAnalysisEnabled.value || !videoElement.value) {
      return
    }

    // 防止并发处理，跳过正在处理的帧（实时模式下减少跳过）
    if (isProcessingFrame) {
      performanceStats.skippedFrames++
      // 实时模式下允许更多并发，降低跳帧率
      if (!aiSettings.realtimeMode) {
        return
      }
      // 实时模式下只在延迟过高时才跳帧
      if (performanceStats.avgProcessTime > 400) {
        return
      }
    }

    try {
      isProcessingFrame = true

      // 捕获当前帧
      const canvas = document.createElement('canvas')
      const video = videoElement.value

      // 更激进的动态分辨率调整
      let scale = 1
      if (performanceStats.avgProcessTime > 400) {
        scale = 0.3  // 超高延迟时使用极低分辨率
        consecutiveSlowFrames++
      } else if (performanceStats.avgProcessTime > 300) {
        scale = 0.4  // 高延迟时使用很低分辨率
        consecutiveSlowFrames++
      } else if (performanceStats.avgProcessTime > 200) {
        scale = 0.5  // 中延迟时使用低分辨率
        consecutiveSlowFrames = Math.max(0, consecutiveSlowFrames - 1)
      } else {
        scale = performanceStats.avgProcessTime > 100 ? 0.7 : 0.8  // 正常情况
        consecutiveSlowFrames = 0
      }

      // 如果连续多帧都很慢，进一步降低质量
      if (consecutiveSlowFrames > 3) {
        scale = Math.max(0.2, scale * 0.8)
      }

      // 保存当前缩放比例用于坐标转换
      currentImageScale = scale

      canvas.width = Math.floor(video.videoWidth * scale)
      canvas.height = Math.floor(video.videoHeight * scale)

      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

      // 获取当前帧数据用于帧差检测（使用降采样提高速度）
      const sampleWidth = Math.max(50, Math.floor(canvas.width / 8))
      const sampleHeight = Math.max(50, Math.floor(canvas.height / 8))
      const currentImageData = ctx.getImageData(0, 0, sampleWidth, sampleHeight).data

      // 检测画面变化（实时模式下降低跳帧概率）
      if (!aiSettings.realtimeMode && !hasSignificantMotion(currentImageData, lastFrameData)) {
        performanceStats.motionSkippedFrames++
        isProcessingFrame = false
        return // 画面无显著变化，跳过此帧（实时模式下不跳帧）
      }

      // 保存当前帧数据作为下一次比较的基准
      lastFrameData = new Uint8ClampedArray(currentImageData)

      // 极致的画质优化 - 根据延迟激进调整
      let quality = 0.4  // 默认较低画质
      if (performanceStats.avgProcessTime > 500) {
        quality = 0.2  // 超高延迟时使用极低画质
      } else if (performanceStats.avgProcessTime > 350) {
        quality = 0.3  // 高延迟时使用很低画质
      } else if (performanceStats.avgProcessTime > 200) {
        quality = 0.4  // 中延迟时使用低画质
      } else {
        quality = 0.5  // 正常情况稍微提高画质
      }

      // 保存实际发送的图像尺寸用于后续坐标转换
      const sentImageWidth = canvas.width
      const sentImageHeight = canvas.height

      console.log(`📸 发送图像尺寸: ${sentImageWidth}x${sentImageHeight} (缩放比例: ${scale})`)
      console.log(`📺 原始视频尺寸: ${video.videoWidth}x${video.videoHeight}`)

      // 转换为blob并发送到AI服务
      canvas.toBlob(async (blob) => {
        if (blob) {
          try {
            await sendFrameToAI(blob, sentImageWidth, sentImageHeight)
          } finally {
            isProcessingFrame = false
          }
        } else {
          isProcessingFrame = false
        }
      }, 'image/jpeg', quality)

    } catch (error) {
      console.error('帧捕获失败:', error)
      isProcessingFrame = false
    }
  }

  // 开始第一次捕获
  scheduleNextCapture()
}

// 发送帧到AI服务进行分析
const sendFrameToAI = async (frameBlob, sentImageWidth, sentImageHeight) => {
  const startTime = performance.now()

  // 保存发送的图像尺寸，用于坐标转换
  window.lastSentImageSize = { width: sentImageWidth, height: sentImageHeight }

  console.log(`📤 发送图像: ${sentImageWidth}x${sentImageHeight}`)

  try {
    const formData = new FormData()
    formData.append('frame', frameBlob, 'frame.jpg')
    formData.append('camera_id', cameraId)
    formData.append('enable_face_recognition', aiSettings.faceRecognition)
    formData.append('enable_object_detection', aiSettings.objectDetection)
    formData.append('enable_behavior_detection', aiSettings.behaviorAnalysis)
    formData.append('enable_fire_detection', aiSettings.fireDetection)
    formData.append('performance_mode', 'fast') // 使用快速模式减少处理时间

    // 创建AbortController来控制请求超时
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 20000) // 增加到10秒超时

    const response = await requestWithRetry(aiService, {
      method: 'post',
      url: '/frame/analyze/',
      data: formData,
      signal: controller.signal,
      timeout: 60000 // 增加axios超时到10秒
    });

    clearTimeout(timeoutId)

    console.log('🔍 AI服务原始响应:', response)

    // AI服务直接返回 {status: "success", results: {...}} 格式
    if (response && response.status === 'success') {
      console.log('✅ AI分析成功:', response.results)
      processAIResults(response.results)

      // 更新性能统计
      const processTime = performance.now() - startTime
      updatePerformanceStats(processTime, true)
    } else if (response && response.status === 'error') {
      console.warn('⚠️ AI分析失败:', response.message)
    } else {
      console.warn('⚠️ AI服务响应格式异常:', response)
    }

  } catch (error) {
    if (error.name === 'AbortError') {
      console.warn('AI请求超时，跳过此帧')
    } else {
      console.error('发送帧到AI服务失败:', error)
    }
    // 更新性能统计（失败的请求）
    const processTime = performance.now() - startTime
    updatePerformanceStats(processTime, false)
  }
}

// 更新性能统计
const updatePerformanceStats = (processTime, success) => {
  if (success) {
    performanceStats.processedFrames++
    frameProcessTimes.push(processTime)

    // 保持最近100次的处理时间
    if (frameProcessTimes.length > 100) {
      frameProcessTimes.shift()
    }

    // 计算平均处理时间
    const avgTime = frameProcessTimes.reduce((a, b) => a + b, 0) / frameProcessTimes.length
    performanceStats.avgProcessTime = Math.round(avgTime)
  }

  // 每5秒更新一次FPS
  const now = Date.now()
  if (now - lastStatsUpdate > 5000) {
    const timeDiff = (now - lastStatsUpdate) / 1000
    performanceStats.fps = Math.round(performanceStats.processedFrames / timeDiff * 10) / 10

    // 重置计数器
    performanceStats.processedFrames = 0
    performanceStats.skippedFrames = 0
    performanceStats.motionSkippedFrames = 0
    lastStatsUpdate = now
  }
}

// 处理AI分析结果
const processAIResults = (results) => {
  // 添加详细调试信息
  console.log('🔍 AI分析结果:', results)

  if (!results) {
    console.warn('⚠️ AI结果为空')
    return
  }

  if (!results.detections) {
    console.warn('⚠️ AI结果中没有检测数据:', results)
    return
  }

  console.log('📊 检测数据:', results.detections)

  const detections = []

  // 处理检测结果
  results.detections.forEach((detection, idx) => {
    console.log(`🎯 处理检测 ${idx + 1}:`, detection)
    
    // 统一坐标格式 - 如果有coordinates字段，优先使用
    let bbox = detection.bbox || null
    if (!bbox && detection.coordinates && detection.coordinates.length === 4) {
      console.log('🔄 从coordinates创建bbox:', detection.coordinates)
      bbox = detection.coordinates
    }

    const processedDetection = {
      type: detection.type,
      label: getDetectionLabel(detection),
      confidence: detection.confidence,
      bbox: bbox,
      timestamp: new Date(detection.timestamp || Date.now())
    }

    console.log('✅ 处理后的检测:', processedDetection)
    detections.push(processedDetection)
  })

  console.log(`🎨 准备绘制 ${detections.length} 个检测框`)

  // 处理告警
  if (results.alerts && results.alerts.length > 0) {
    console.log('🚨 处理告警:', results.alerts)
    results.alerts.forEach(alert => {
      addAlert({
        title: getAlertTitle(alert.type),
        description: alert.message,
        type: getAlertType(alert.type)
      })
    })
  }

  // 总是更新检测结果，即使为空（这样可以清除之前的检测框）
  updateDetectionResults(detections)
  drawDetectionResults(detections)
}

// 获取检测标签
const getDetectionLabel = (detection) => {
  if (detection.type === 'object') {
    return detection.class_name
  } else if (detection.type === 'face') {
    return detection.known ? detection.name : '未知人脸'
  } else if (detection.type === 'fire_detection') {
    return detection.detection_type === 'fire' ? '火焰' :
           detection.detection_type === 'smoke' ? '烟雾' :
           detection.class_name || '火灾风险'
  }
  return '未知'
}

// 获取告警标题
const getAlertTitle = (alertType) => {
  const titles = {
    person_detected: '🚨 检测到人员',
    unknown_face: '⚠️ 发现未知人脸',
    behavior_anomaly: '🔥 异常行为检测',
    abnormal_behavior_fall_down: '⚠️ 检测到跌倒',
    fire_fire: '🔥 火焰检测告警',
    fire_smoke: '💨 烟雾检测告警',
    fire_related: '⚠️ 火灾风险检测'
  }
  // 处理以fire_detection_开头的告警类型
  if (alertType && alertType.startsWith('fire_detection_')) {
    const subType = alertType.replace('fire_detection_', '')
    return titles[`fire_${subType}`] || '🔥 火灾风险检测'
  }
  // 处理以abnormal_behavior_开头的告警类型
  if (alertType && alertType.startsWith('abnormal_behavior_')) {
    const behaviorType = alertType.replace('abnormal_behavior_', '')
    return behaviorType === 'fall_down' ? '⚠️ 检测到跌倒' : '⚠️ 异常行为检测'
  }
  return titles[alertType] || '🔔 检测告警'
}

// 获取告警类型
const getAlertType = (alertType) => {
  const types = {
    person_detected: 'info',
    unknown_face: 'warning',
    behavior_anomaly: 'error',
    abnormal_behavior_fall_down: 'error', // 跌倒告警为错误级别（最高）
    fire_fire: 'error',        // 火焰告警为错误级别（最高）
    fire_smoke: 'error',       // 烟雾告警为错误级别（最高）
    fire_related: 'warning'    // 火灾风险为警告级别
  }

  // 处理以fire_detection_开头的告警类型
  if (alertType && alertType.startsWith('fire_detection_')) {
    const subType = alertType.replace('fire_detection_', '')
    return types[`fire_${subType}`] || 'error' // 默认火灾相关告警为错误级别
  }

  // 处理以abnormal_behavior_开头的告警类型
  if (alertType && alertType.startsWith('abnormal_behavior_')) {
    return 'error' // 异常行为都视为错误级别
  }

  return types[alertType] || 'info'
}

// 备用功能（已弃用，可用testDetectionBoxes代替）
// eslint-disable-next-line
function unusedFunction() {
  // 此函数被移除
}

// 计算两个检测框的距离（用于匹配）
const calculateDistance = (bbox1, bbox2) => {
  const center1 = [(bbox1[0] + bbox1[2]) / 2, (bbox1[1] + bbox1[3]) / 2]
  const center2 = [(bbox2[0] + bbox2[2]) / 2, (bbox2[1] + bbox2[3]) / 2]
  return Math.sqrt(Math.pow(center1[0] - center2[0], 2) + Math.pow(center1[1] - center2[1], 2))
}

// 优化的平滑检测框位置（配合AI端稳定化）
const smoothDetections = (newDetections, lastDetections) => {
  if (!lastDetections || lastDetections.length === 0) {
    return newDetections.map(det => ({
      ...det,
      isStable: det.is_stable || false
    }))
  }

  const smoothedResults = []
  const MATCH_THRESHOLD = 100 // 降低匹配阈值，AI端已做稳定化

  // 根据AI端的稳定性标记调整平滑因子
  const getSmoothFactor = (detection) => {
    if (detection.is_stable) {
      return aiSettings.realtimeMode ? 0.8 : 0.6 // 稳定目标更平滑
    } else {
      return aiSettings.realtimeMode ? 0.9 : 0.8 // 新目标响应更快
    }
  }

  newDetections.forEach(newDet => {
    let bestMatch = null
    let minDistance = Infinity

    // 寻找最佳匹配
    lastDetections.forEach(lastDet => {
      if (newDet.type === lastDet.type) {
        const distance = calculateDistance(newDet.bbox, lastDet.bbox)
        if (distance < MATCH_THRESHOLD && distance < minDistance) {
          minDistance = distance
          bestMatch = lastDet
        }
      }
    })

    if (bestMatch && !newDet.is_kept) { // 如果不是AI保留的对象才前端平滑
      const smoothFactor = getSmoothFactor(newDet)

      const smoothedBbox = [
        bestMatch.bbox[0] + (newDet.bbox[0] - bestMatch.bbox[0]) * smoothFactor,
        bestMatch.bbox[1] + (newDet.bbox[1] - bestMatch.bbox[1]) * smoothFactor,
        bestMatch.bbox[2] + (newDet.bbox[2] - bestMatch.bbox[2]) * smoothFactor,
        bestMatch.bbox[3] + (newDet.bbox[3] - bestMatch.bbox[3]) * smoothFactor
      ]

      smoothedResults.push({
        ...newDet,
        bbox: smoothedBbox,
        isStable: newDet.is_stable || true // 继承AI端的稳定性标记
      })
    } else {
      // AI端已处理或新目标，直接使用
      smoothedResults.push({
        ...newDet,
        isStable: newDet.is_stable || false
      })
    }
  })

  return smoothedResults
}

// 更新检测结果列表 - 带平滑处理
const updateDetectionResults = (results) => {
  // 对检测结果进行平滑处理
  const smoothedResults = smoothDetections(results, lastFrameDetections.value)

  // 更新当前帧结果
  detectionResults.value = smoothedResults.slice(0, 20) // 仅显示最新的20个检测结果

  // 缓存当前帧结果供下一帧使用
  lastFrameDetections.value = smoothedResults.slice()
}

// 在视频上绘制检测结果
const drawDetectionResults = (results) => {
  // 添加详细调试信息
  console.log('🎨 开始绘制检测框:', results)

  if (!canvasContext || !overlayCanvas.value) {
    console.error('❌ Canvas未初始化!')
    console.log('Canvas状态:', {
      canvasContext: !!canvasContext,
      overlayCanvas: !!overlayCanvas.value,
      videoElement: !!videoElement.value
    })
    return
  }

  const canvas = overlayCanvas.value
  const video = videoElement.value

  console.log('📐 Canvas和Video状态:', {
    canvasWidth: canvas.width,
    canvasHeight: canvas.height,
    videoWidth: video ? video.videoWidth : 'N/A',
    videoHeight: video ? video.videoHeight : 'N/A',
    videoDisplayWidth: video ? video.offsetWidth : 'N/A',
    videoDisplayHeight: video ? video.offsetHeight : 'N/A'
  })

  // 清除之前的绘制
  canvasContext.clearRect(0, 0, canvas.width, canvas.height)
  console.log('🧹 已清除Canvas')

  if (!results || results.length === 0) {
    console.log('📭 没有检测结果需要绘制')
    return
  }

  // 检查视频是否可用
  if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
    console.warn('⚠️ 视频尺寸无效，无法绘制检测框')
    return
  }

  // 计算坐标转换比例
  const canvasWidth = canvas.width
  const canvasHeight = canvas.height
  const videoWidth = video.videoWidth
  const videoHeight = video.videoHeight

  // 获取实际发送给AI服务的图像尺寸
  const sentImageSize = window.lastSentImageSize || { width: videoWidth, height: videoHeight }

  // AI返回的坐标是相对于发送图像尺寸的，需要转换到Canvas显示坐标
  // 转换链条：AI坐标(相对发送图像) → 原始视频坐标 → Canvas显示坐标
  const scaleX = canvasWidth / sentImageSize.width
  const scaleY = canvasHeight / sentImageSize.height

  console.log('📏 坐标转换信息:', {
    scaleX, scaleY,
    canvasSize: { width: canvasWidth, height: canvasHeight },
    videoSize: { width: videoWidth, height: videoHeight },
    sentImageSize: sentImageSize
  })

  // 绘制每个检测结果
  results.forEach((result, idx) => {
    console.log(`🖌️ 绘制检测框 ${idx + 1}:`, result)

    // 处理来自AI服务的不同坐标格式
    if (!result.bbox || result.bbox.length !== 4) {
      // 尝试从coordinates字段获取坐标（火焰检测模块使用这个字段）
      if (result.coordinates && result.coordinates.length === 4) {
        console.log(`⚙️ 使用coordinates替代bbox字段:`, result.coordinates)
        result.bbox = result.coordinates
      } else {
        console.warn(`⚠️ 检测框 ${idx + 1} 坐标数据无效:`, result)
        return
      }
    }

    const [x1, y1, x2, y2] = result.bbox

    console.log(`📍 AI返回坐标 (相对于原始图像): (${x1}, ${y1}) -> (${x2}, ${y2})`)

    // AI服务返回的坐标已经是相对于原始图像的，直接转换到Canvas显示坐标
    const displayX1 = x1 * scaleX
    const displayY1 = y1 * scaleY
    const displayX2 = x2 * scaleX
    const displayY2 = y2 * scaleY

    console.log(`📍 Canvas显示坐标: (${displayX1}, ${displayY1}) -> (${displayX2}, ${displayY2})`)

    const width = displayX2 - displayX1
    const height = displayY2 - displayY1

    console.log(`📐 框大小: ${width} x ${height}`)

    // 根据目标状态绘制不同样式的检测框
    const color = getDetectionColor(result.type)
    console.log(`🎨 使用颜色: ${color}`)

    canvasContext.strokeStyle = color

    // 根据目标状态设置线条样式
    if (result.is_kept) {
      // AI保留的对象：虚线框表示预测保持
      canvasContext.setLineDash([8, 4])
      canvasContext.lineWidth = 3
      canvasContext.globalAlpha = 0.8
    } else if (result.isStable || result.is_stable) {
      // 稳定目标：粗实线
      canvasContext.setLineDash([])
      canvasContext.lineWidth = 4
      canvasContext.globalAlpha = 1.0
    } else {
      // 新目标：细实线
      canvasContext.setLineDash([])
      canvasContext.lineWidth = 2
      canvasContext.globalAlpha = 0.9
    }

    console.log(`🖼️ 开始绘制矩形...`)
    canvasContext.strokeRect(displayX1, displayY1, width, height)

    // 重置绘制状态
    canvasContext.setLineDash([])
    canvasContext.globalAlpha = 1.0

    // 稳定目标添加角标提示
    if (result.isStable || result.is_stable) {
      canvasContext.fillStyle = color
      canvasContext.fillRect(displayX1 - 2, displayY1 - 2, 8, 8)
    }

    // 绘制标签背景
    let label = `${result.label || getDetectionLabel(result)} ${(result.confidence * 100).toFixed(1)}%`

    // 为不同状态的目标添加状态标识
    if (result.is_kept) {
      label += ' [保持]'
    } else if (result.isStable || result.is_stable) {
      label += ' [稳定]'
    }

    console.log(`🏷️ 绘制标签: ${label}`)

    canvasContext.font = 'bold 14px Arial'
    const textMetrics = canvasContext.measureText(label)
    const textWidth = textMetrics.width
    const textHeight = 18

    // 确保标签不会超出画布边界
    const labelX = Math.max(0, Math.min(displayX1, canvasWidth - textWidth - 10))
    const labelY = Math.max(textHeight, displayY1)

    canvasContext.fillStyle = color
    canvasContext.fillRect(labelX, labelY - textHeight, textWidth + 8, textHeight)

    // 绘制标签文字
    canvasContext.fillStyle = 'white'
    canvasContext.fillText(label, labelX + 4, labelY - 4)

    console.log(`✅ 检测框 ${idx + 1} 绘制完成`)
  })

  console.log('🎨 所有检测框绘制完成 为什么框没看到？')
}

// 测试检测框显示
const testDetectionBoxes = () => {
  if (!isStreaming.value) {
    ElMessage.warning('请先启动摄像头')
    return
  }

  // 获取当前视频尺寸，生成相对应的测试坐标
  const video = videoElement.value
  if (!video) return

  const videoWidth = video.videoWidth || 640
  const videoHeight = video.videoHeight || 480

  // 测试坐标基于当前缩放比例的图像尺寸
  const scaledWidth = videoWidth * currentImageScale
  const scaledHeight = videoHeight * currentImageScale

  const testResults = [
    {
      type: 'person',
      label: '测试人员',
      confidence: 0.95,
      bbox: [
        scaledWidth * 0.1,   // 左上X (10%)
        scaledHeight * 0.1,  // 左上Y (10%)
        scaledWidth * 0.4,   // 右下X (40%)
        scaledHeight * 0.7   // 右下Y (70%)
      ],
      timestamp: new Date()
    },
    {
      type: 'face',
      label: '测试人脸',
      confidence: 0.87,
      bbox: [
        scaledWidth * 0.15,  // 左上X (15%)
        scaledHeight * 0.15, // 左上Y (15%)
        scaledWidth * 0.35,  // 右下X (35%)
        scaledHeight * 0.4   // 右下Y (40%)
      ],
      timestamp: new Date()
    },
    {
      type: 'unknown_face',
      label: '未知人脸',
      confidence: 0.76,
      bbox: [
        scaledWidth * 0.6,   // 左上X (60%)
        scaledHeight * 0.2,  // 左上Y (20%)
        scaledWidth * 0.8,   // 右下X (80%)
        scaledHeight * 0.5   // 右下Y (50%)
      ],
      timestamp: new Date()
    },
    {
      type: 'fire_detection',
      label: '火焰',
      confidence: 0.92,
      bbox: [
        scaledWidth * 0.7,    // 左上X (70%)
        scaledHeight * 0.6,   // 左上Y (60%)
        scaledWidth * 0.9,    // 右下X (90%)
        scaledHeight * 0.8    // 右下Y (80%)
      ],
      timestamp: new Date()
    }
  ]

  console.log('测试检测框参数:', {
    videoSize: [videoWidth, videoHeight],
    scaledSize: [scaledWidth, scaledHeight],
    currentImageScale,
    testResults
  })

  drawDetectionResults(testResults)
  updateDetectionResults(testResults)

  ElMessage.success('测试检测框已显示')
}

// 强制绘制测试框（用于调试Canvas）
const forceDrawTestBox = () => {
  if (!isStreaming.value) {
    ElMessage.warning('请先启动摄像头')
    return
  }

  const video = videoElement.value
  if (!video) return

  const videoWidth = video.videoWidth || 640
  const videoHeight = video.videoHeight || 480

  const scaledWidth = videoWidth * currentImageScale
  const scaledHeight = videoHeight * currentImageScale

  const testResults = [
    {
      type: 'person',
      label: '测试人员',
      confidence: 0.95,
      bbox: [
        scaledWidth * 0.1,   // 左上X (10%)
        scaledHeight * 0.1,  // 左上Y (10%)
        scaledWidth * 0.4,   // 右下X (40%)
        scaledHeight * 0.7   // 右下Y (70%)
      ],
      timestamp: new Date()
    },
    {
      type: 'face',
      label: '测试人脸',
      confidence: 0.87,
      bbox: [
        scaledWidth * 0.15,  // 左上X (15%)
        scaledHeight * 0.15, // 左上Y (15%)
        scaledWidth * 0.35,  // 右下X (35%)
        scaledHeight * 0.4   // 右下Y (40%)
      ],
      timestamp: new Date()
    },
    {
      type: 'unknown_face',
      label: '未知人脸',
      confidence: 0.76,
      bbox: [
        scaledWidth * 0.6,   // 左上X (60%)
        scaledHeight * 0.2,  // 左上Y (20%)
        scaledWidth * 0.8,   // 右下X (80%)
        scaledHeight * 0.5   // 右下Y (50%)
      ],
      timestamp: new Date()
    },
    {
      type: 'fire_detection',
      label: '火焰',
      confidence: 0.92,
      bbox: [
        scaledWidth * 0.7,    // 左上X (70%)
        scaledHeight * 0.6,   // 左上Y (60%)
        scaledWidth * 0.9,    // 右下X (90%)
        scaledHeight * 0.8    // 右下Y (80%)
      ],
      timestamp: new Date()
    }
  ]

  drawDetectionResults(testResults)
  updateDetectionResults(testResults)

  ElMessage.success('强制绘制测试框已显示')
}

// 清除检测框
const clearDetectionBoxes = () => {
  if (!canvasContext || !overlayCanvas.value) return

  canvasContext.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height)
  detectionResults.value = []
  lastFrameDetections.value = [] // 清除缓存
  console.log('✅ 已清除所有检测框和缓存')
  ElMessage.info('检测框已清除')
}

// 重置AI检测缓存
const resetDetectionCache = async () => {
  try {
    const response = await requestWithRetry(aiService, {
      method: 'post',
      url: `/detection/cache/clear/${cameraId}`
    });

    // AI服务直接返回数据，不需要额外的data包装
    if (response.status === 'success') {
      // 同时清除前端缓存
      clearDetectionBoxes()
      console.log('🔄 已重置AI检测缓存')
      ElMessage.success('检测跟踪已重置')
    } else {
      console.error('重置缓存失败:', response.message || '未知错误')
      ElMessage.error('重置失败: ' + (response.message || '未知错误'))
    }
  } catch (error) {
    console.error('重置检测缓存失败:', error)
    ElMessage.error('重置缓存失败，请检查网络连接')
  }
}

// 获取检测类型对应的颜色
const getDetectionColor = (type) => {
  const colors = {
    person: '#409EFF',
    face: '#67C23A',
    unknown_face: '#F56C6C',
    object: '#E6A23C',
    fire_detection: '#F56C6C',  // 火焰检测使用红色
    fire: '#F56C6C'             // 火焰也使用红色
  }
  
  // 处理以fire开头的类型，确保火焰相关检测始终为红色
  if (type && (type.startsWith('fire') || type.includes('fire'))) {
    console.log(`检测到火焰相关类型: ${type}，使用红色`)
    return '#F56C6C'  // 统一使用红色
  }
  
  console.log(`获取颜色类型: ${type} -> ${colors[type] || '#909399'}`)
  return colors[type] || '#909399'
}

// 获取检测类型图标
const getDetectionIcon = (type) => {
  const icons = {
    person: '👤',
    face: '😊',
    unknown_face: '❓',
    object: '📦',
    fire_detection: '🔥',  // 火焰检测图标
    fire: '🔥'             // 火焰图标
  }
  
  // 处理fire相关类型
  if (type && (type.startsWith('fire') || type.includes('fire'))) {
    return '🔥'
  }
  
  return icons[type] || '🔍'
}

// 添加告警（带去重机制）
const addAlert = (alert) => {
  const now = Date.now()
  const alertKey = `${alert.type}_${alert.title}` // 基于类型和标题创建唯一key

  // 检查是否在冷却期内
  if (alertCooldowns.has(alertKey)) {
    const lastTime = alertCooldowns.get(alertKey)
    if (now - lastTime < ALERT_COOLDOWN) {
      return // 在冷却期内，跳过此次告警
    }
  }

  // 更新冷却时间
  alertCooldowns.set(alertKey, now)

  // 添加到告警列表
  realtimeAlerts.value.unshift({
    ...alert,
    id: now
  })

  // 限制告警数量
  if (realtimeAlerts.value.length > 10) {
    realtimeAlerts.value = realtimeAlerts.value.slice(0, 10)
  }

  // 显示桌面通知（仅重要告警）
  if (alert.type === 'warning' || alert.type === 'error') {
    ElNotification({
      title: alert.title,
      message: alert.description,
      type: alert.type,
      duration: 4000,
      showClose: true
    })
  }
}

// 移除告警
const removeAlert = (index) => {
  realtimeAlerts.value.splice(index, 1)
}

// 发送音频告警到AI服务
const sendAudioAlertToAI = async (audioLevel, eventType) => {
  try {
    const response = await requestWithRetry(aiService, {
      method: 'post',
      url: '/audio/frontend/alert/',
      data: {
        camera_id: cameraId,
        audio_level: audioLevel,
        event_type: eventType,
        timestamp: new Date().toISOString()
      }
    });

    const result = response.data
    if (result.status !== 'success') {
      console.error('发送音频告警失败:', result.message)
    }
  } catch (error) {
    console.error('发送音频告警到AI服务失败:', error)
  }
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

// 性能优化建议
const getPerformanceAdvice = () => {
  const delay = performanceStats.avgProcessTime
  if (delay > 500) {
    return {
      level: 'error',
      title: '延迟过高',
      advice: '建议降低检测频率或关闭人脸识别功能'
    }
  } else if (delay > 300) {
    return {
      level: 'warning',
      title: '延迟较高',
      advice: '系统已自动降低画质和分辨率'
    }
  } else if (delay > 150) {
    return {
      level: 'info',
      title: '性能良好',
      advice: '系统运行正常，已启用智能优化'
    }
  } else {
    return {
      level: 'success',
      title: '性能优秀',
      advice: '系统响应迅速，可适当提高检测频率'
    }
  }
}

// 视频加载完成
const onVideoLoaded = () => {
  console.log('📹 视频加载完成，开始初始化Canvas')

  nextTick(() => {
    if (overlayCanvas.value && videoElement.value) {
      // 获取视频元素的实际显示尺寸
      const rect = videoElement.value.getBoundingClientRect()
      console.log('📐 视频显示尺寸:', {
        width: rect.width,
        height: rect.height,
        videoWidth: videoElement.value.videoWidth,
        videoHeight: videoElement.value.videoHeight
      })

      overlayCanvas.value.width = rect.width
      overlayCanvas.value.height = rect.height
      canvasContext = overlayCanvas.value.getContext('2d')

      console.log('✅ Canvas初始化完成:', {
        canvasWidth: overlayCanvas.value.width,
        canvasHeight: overlayCanvas.value.height,
        hasContext: !!canvasContext
      })

      // 监听窗口大小变化，动态调整canvas尺寸
      window.addEventListener('resize', resizeCanvas)
    } else {
      console.error('❌ Canvas或Video元素未找到!')
    }
  })
}

// 调整Canvas尺寸以匹配视频显示尺寸
const resizeCanvas = () => {
  if (overlayCanvas.value && videoElement.value) {
    const rect = videoElement.value.getBoundingClientRect()
    overlayCanvas.value.width = rect.width
    overlayCanvas.value.height = rect.height
  }
}

// 格式化时间
const formatTime = (date) => {
  return new Date(date).toLocaleTimeString()
}

// 动态调整检测间隔以优化性能（全局函数）
const getDynamicInterval = () => {
  // 实时模式优先级更高
  if (aiSettings.realtimeMode) {
    if (performanceStats.avgProcessTime > 500) {
      return 150  // 实时模式下即使高延迟也保持较高频率
    } else if (performanceStats.avgProcessTime > 300) {
      return 100  // 实时模式中延迟
    } else {
      return 66   // 实时模式正常情况，约15fps
    }
  }

  // 非实时模式（原有逻辑，但略微优化）
  if (performanceStats.avgProcessTime > 400) {
    return 800   // 高延迟时降低频率（从1000ms优化到800ms）
  } else if (performanceStats.avgProcessTime > 300) {
    return 600   // 中高延迟
  } else if (performanceStats.avgProcessTime > 200) {
    return 400   // 中延迟（从600ms优化到400ms）
  } else {
    return Math.max(analysisInterval.value, 200)  // 正常情况使用用户设置或最小200ms
  }
}

// 实时模式状态监控
const logRealtimeStatus = () => {
  if (aiSettings.realtimeMode) {
    console.log(`🚀 实时模式状态:`, {
      interval: getDynamicInterval(),
      avgProcessTime: performanceStats.avgProcessTime,
      fps: performanceStats.fps,
      motionSkippedFrames: performanceStats.motionSkippedFrames,
      realtimeMode: aiSettings.realtimeMode
    })
  }
}

// 监听实时模式变化
watch(() => aiSettings.realtimeMode, (newVal) => {
  console.log(`实时模式${newVal ? '开启' : '关闭'}`)
  if (newVal) {
    ElMessage.success('🚀 实时模式已开启，检测频率提升至~15FPS')
    setInterval(logRealtimeStatus, 3000) // 每3秒打印一次状态
  } else {
    ElMessage.info('💡 已切换至节能模式，智能调频优化')
  }
})

// 监听声音检测开关变化
watch(() => aiSettings.soundDetection, async (newVal) => {
  console.log(`声音检测${newVal ? '开启' : '关闭'}`)

  if (newVal && isStreaming.value && mediaStream && mediaStream.getAudioTracks().length > 0) {
    // 开启声音检测
    try {
      await initAudioAnalysis(mediaStream)
      ElMessage.success('🎤 声音检测已开启')
    } catch (error) {
      console.error('启动声音检测失败:', error)
      ElMessage.error('启动声音检测失败')
    }
  } else {
    // 关闭声音检测
    stopAudioMonitoring()
    ElMessage.info('🔇 声音检测已关闭')
  }
})

// =============================================================================
// 危险区域管理功能
// =============================================================================

// 开始绘制危险区域
const startDrawingZone = () => {
  if (!isStreaming.value) {
    ElMessage.warning('请先启动摄像头')
    return
  }

  isDrawingZone.value = true
  currentZonePoints.value = []
  newZoneName.value = `区域${dangerZones.value.length + 1}`

  // 为Canvas添加点击事件监听器
  if (overlayCanvas.value) {
    overlayCanvas.value.style.pointerEvents = 'auto'
    overlayCanvas.value.addEventListener('click', handleCanvasClick)
    overlayCanvas.value.addEventListener('contextmenu', finishDrawing)
  }

  ElMessage.info('点击画面绘制区域顶点，右键完成绘制')
}

// 处理Canvas点击事件
const handleCanvasClick = (event) => {
  if (!isDrawingZone.value) return

  const rect = overlayCanvas.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  // 转换为相对于Canvas的坐标
  const canvasX = (x / rect.width) * overlayCanvas.value.width
  const canvasY = (y / rect.height) * overlayCanvas.value.height

  currentZonePoints.value.push([canvasX, canvasY])

  // 实时绘制当前区域
  drawDangerZones()

  console.log(`添加顶点: (${canvasX.toFixed(1)}, ${canvasY.toFixed(1)})`)
}

// 完成绘制
const finishDrawing = (event) => {
  event.preventDefault()

  if (currentZonePoints.value.length < 3) {
    ElMessage.warning('至少需要3个顶点才能构成区域')
    return
  }

  // 移除事件监听器
  if (overlayCanvas.value) {
    overlayCanvas.value.style.pointerEvents = 'none'
    overlayCanvas.value.removeEventListener('click', handleCanvasClick)
    overlayCanvas.value.removeEventListener('contextmenu', finishDrawing)
  }

  ElMessage.success(`区域绘制完成，共${currentZonePoints.value.length}个顶点`)
  showZoneManager.value = true
}

// 取消绘制
const cancelDrawing = () => {
  isDrawingZone.value = false
  currentZonePoints.value = []

  // 移除事件监听器
  if (overlayCanvas.value) {
    overlayCanvas.value.style.pointerEvents = 'none'
    overlayCanvas.value.removeEventListener('click', handleCanvasClick)
    overlayCanvas.value.removeEventListener('contextmenu', finishDrawing)
  }

  // 重新绘制已有区域
  drawDangerZones()
}

// 保存危险区域
const saveDangerZone = () => {
  if (!newZoneName.value.trim()) {
    ElMessage.error('请输入区域名称')
    return
  }

  if (currentZonePoints.value.length < 3) {
    ElMessage.error('区域至少需要3个顶点')
    return
  }

  const newZone = {
    name: newZoneName.value,
    coordinates: currentZonePoints.value,
    min_distance_threshold: newZoneMinDistance.value,
    time_in_area_threshold: newZoneDwellTime.value,
    is_active: true
  }

  dangerZones.value.push(newZone)

  // 重置绘制状态
  isDrawingZone.value = false
  currentZonePoints.value = []
  newZoneName.value = ''
  newZoneMinDistance.value = 50
  newZoneDwellTime.value = 10

  ElMessage.success(`危险区域 "${newZone.name}" 已保存`)
  drawDangerZones()
}

// 移除危险区域
const removeDangerZone = (index) => {
  const zone = dangerZones.value[index]
  dangerZones.value.splice(index, 1)
  ElMessage.success(`已删除危险区域 "${zone.name}"`)
  drawDangerZones()
}

// 绘制所有危险区域
const drawDangerZones = () => {
  if (!canvasContext || !overlayCanvas.value) return

  // 先清除Canvas，然后重新绘制检测结果
  canvasContext.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height)

  // 重新绘制检测框
  if (detectionResults.value && detectionResults.value.length > 0) {
    drawDetectionResults(detectionResults.value)
  }

  // 绘制已保存的危险区域
  dangerZones.value.forEach((zone, index) => {
    drawZone(zone.coordinates, `#f56c6c`, zone.name, true)
  })

  // 绘制正在绘制的区域
  if (currentZonePoints.value.length > 0) {
    drawZone(currentZonePoints.value, `#409EFF`, '新区域', false)
  }
}

// 绘制单个区域
const drawZone = (points, color, name, isComplete) => {
  if (!canvasContext || points.length === 0) return

  canvasContext.save()

  // 绘制区域边界
  canvasContext.strokeStyle = color
  canvasContext.lineWidth = 3
  canvasContext.setLineDash(isComplete ? [] : [8, 4])

  canvasContext.beginPath()
  canvasContext.moveTo(points[0][0], points[0][1])

  for (let i = 1; i < points.length; i++) {
    canvasContext.lineTo(points[i][0], points[i][1])
  }

  if (isComplete && points.length > 2) {
    canvasContext.closePath()

    // 填充半透明背景
    canvasContext.fillStyle = color + '20' // 添加透明度
    canvasContext.fill()
  }

  canvasContext.stroke()

  // 绘制顶点
  points.forEach((point, index) => {
    canvasContext.fillStyle = color
    canvasContext.beginPath()
    canvasContext.arc(point[0], point[1], 4, 0, 2 * Math.PI)
    canvasContext.fill()

    // 显示顶点序号
    canvasContext.fillStyle = '#ffffff'
    canvasContext.font = '12px Arial'
    canvasContext.textAlign = 'center'
    canvasContext.fillText(index + 1, point[0], point[1] + 4)
  })

  // 绘制区域名称
  if (points.length > 0) {
    const centerX = points.reduce((sum, point) => sum + point[0], 0) / points.length
    const centerY = points.reduce((sum, point) => sum + point[1], 0) / points.length

    canvasContext.fillStyle = color
    canvasContext.font = 'bold 14px Arial'
    canvasContext.textAlign = 'center'
    canvasContext.fillText(name, centerX, centerY)
  }

  canvasContext.restore()
}

// 同步危险区域到AI服务
const syncZonesToAI = async () => {
  try {
    // 转换坐标系：从Canvas坐标转换为发送给AI的图像坐标
    const convertedZones = dangerZones.value.map(zone => {
      // 使用实际发送给AI的图像尺寸进行坐标转换
      const lastSentSize = window.lastSentImageSize
      let targetWidth, targetHeight

      if (lastSentSize) {
        // 使用上次发送的实际图像尺寸
        targetWidth = lastSentSize.width
        targetHeight = lastSentSize.height
        console.log(`🎯 使用实际发送的图像尺寸: ${targetWidth}x${targetHeight}`)
      } else if (overlayCanvas.value && videoElement.value) {
        // 如果没有上次发送尺寸，计算当前的发送尺寸（与captureFrame逻辑一致）
        const video = videoElement.value

        // 获取当前性能状态的缩放比例（模拟captureFrame中的逻辑）
        let scale = 0.8 // 默认缩放比例
        if (performanceStats.avgProcessTime > 400) {
          scale = 0.3
        } else if (performanceStats.avgProcessTime > 300) {
          scale = 0.4
        } else if (performanceStats.avgProcessTime > 200) {
          scale = 0.5
        } else {
          scale = performanceStats.avgProcessTime > 100 ? 0.7 : 0.8
        }

        targetWidth = Math.floor(video.videoWidth * scale)
        targetHeight = Math.floor(video.videoHeight * scale)
        console.log(`📐 计算的发送图像尺寸: ${targetWidth}x${targetHeight} (scale=${scale})`)
      } else {
        // 备用方案
        targetWidth = 640
        targetHeight = 480
        console.log(`⚠️ 使用默认尺寸: ${targetWidth}x${targetHeight}`)
      }

      const scaleX = targetWidth / overlayCanvas.value.width
      const scaleY = targetHeight / overlayCanvas.value.height

      console.log(`🔄 坐标转换: Canvas(${overlayCanvas.value.width}x${overlayCanvas.value.height}) -> AI(${targetWidth}x${targetHeight})`)
      console.log(`📏 缩放比例: scaleX=${scaleX.toFixed(3)}, scaleY=${scaleY.toFixed(3)}`)

      const convertedCoordinates = zone.coordinates.map(([x, y]) => {
        const newX = x * scaleX
        const newY = y * scaleY
        console.log(`   点转换: (${x.toFixed(1)}, ${y.toFixed(1)}) -> (${newX.toFixed(1)}, ${newY.toFixed(1)})`)
        return [newX, newY]
      })

      return {
        ...zone,
        coordinates: convertedCoordinates
      }
    })

    const response = await requestWithRetry(aiService, {
      method: 'post',
      url: '/danger_zone/config/',
      data: {
        camera_id: cameraId,
        zones: convertedZones
      }
    })

    if (response && response.status === 'success') {
      ElMessage.success('危险区域配置已同步到AI服务')
    } else {
      ElMessage.error('同步失败: ' + (response?.message || '未知错误'))
    }
  } catch (error) {
    console.error('同步危险区域配置失败:', error)
    ElMessage.error('同步失败，请检查网络连接')
  }
}

// 生命周期
onMounted(async () => {
  await getVideoDevices()
})

onUnmounted(() => {
  stopCamera()
  // 移除窗口大小变化监听器
  window.removeEventListener('resize', resizeCanvas)
  // 清理危险区域绘制事件
  if (overlayCanvas.value) {
    overlayCanvas.value.removeEventListener('click', handleCanvasClick)
    overlayCanvas.value.removeEventListener('contextmenu', finishDrawing)
  }
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
.performance-panel,
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

.frequency-hint {
  margin-top: 5px;
  text-align: center;
}

.frequency-hint small {
  color: #909399;
  font-size: 11px;
}

.performance-stats {
  display: flex;
  justify-content: space-between;
  gap: 15px;
}

.stat-item {
  text-align: center;
  flex: 1;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 5px;
}

.stat-value {
  display: block;
  font-size: 18px;
  font-weight: 600;
  color: #409EFF;
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

/* 性能优化状态显示 */
.optimization-status {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.opt-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #67c23a;
}

.opt-item .el-icon {
  color: #67c23a;
}

/* 音频监控显示 */
.audio-monitor {
  width: 100%;
}

.audio-level-display {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.audio-text {
  font-size: 13px;
  color: #606266;
}

.audio-bar {
  width: 100%;
  height: 8px;
  background-color: #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.audio-level {
  height: 100%;
  border-radius: 4px;
  transition: all 0.3s ease;
  min-width: 2px;
}

/* 性能监控面板增强 */
.performance-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
  gap: 15px;
}

.stat-item {
  background-color: #f8f9fa;
  padding: 10px 8px;
  border-radius: 6px;
  text-align: center;
  border: 1px solid #e4e7ed;
}

.stat-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

/* 性能建议样式 */
.performance-advice {
  margin-top: 10px;
}

.performance-advice .el-alert {
  border-radius: 6px;
}

/* 优化状态动画 */
.opt-item {
  transition: all 0.3s ease;
}

.opt-item:hover {
  transform: translateX(2px);
}

/* 延迟状态颜色指示 */
.el-text {
  font-weight: 500;
}

/* 测试控制面板 */
.test-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.test-controls .el-button {
  width: 100%;
}

.test-controls .el-text {
  font-size: 11px;
  color: #909399;
}

/* 危险区域管理样式 */
.zone-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.zone-controls .el-button {
  width: 100%;
}

.zone-controls .el-text {
  font-size: 11px;
  color: #909399;
}

.zone-manager {
  max-height: 600px;
  overflow-y: auto;
}

.zone-list {
  margin-bottom: 20px;
}

.zone-list h4 {
  margin: 0 0 15px 0;
  color: #2c3e50;
  font-size: 16px;
}

.no-zones {
  text-align: center;
  padding: 40px 20px;
  color: #909399;
}

.no-zones .el-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.new-zone-form {
  background-color: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.new-zone-form h4 {
  margin: 0 0 15px 0;
  color: #2c3e50;
  font-size: 16px;
}

.new-zone-form .el-form-item {
  margin-bottom: 15px;
}

.new-zone-form small {
  display: block;
  margin-top: 5px;
  color: #909399;
  font-size: 12px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* Canvas绘制相关 */
.overlay-canvas {
  cursor: crosshair;
}

.overlay-canvas.drawing {
  cursor: crosshair !important;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .zone-manager {
    max-height: 400px;
  }

  .new-zone-form {
    padding: 15px;
  }

  .zone-controls .el-button {
    font-size: 12px;
    padding: 6px 12px;
  }
}
</style>
