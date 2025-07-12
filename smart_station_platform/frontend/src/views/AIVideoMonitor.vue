<template>
  <div class="video-monitor">
    <el-container>
      <!-- 顶部控制栏 -->
      <el-header height="80px">
        <div class="header-content">
          <h2>🤖 AI智能视频监控</h2>
          <div class="header-controls">
            <el-button-group>
              <el-button
                type="danger"
                :disabled="!isStreaming"
                @click="stopStream"
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
              <el-button
                type="primary"
                :disabled="!isStreaming"
                @click="testDetectionBoxes"
                size="small"
              >
                测试检测框
              </el-button>
              <el-button
                type="info"
                @click="debugCanvas"
                size="small"
              >
                调试Canvas
              </el-button>
              <el-button
                type="warning"
                @click="testAIConnection"
                size="small"
              >
                测试AI连接
              </el-button>
            </el-button-group>
            
            <!-- WebSocket连接状态指示器 -->
            <div class="connection-status">
              <el-tag 
                :type="wsConnected ? 'success' : 'danger'" 
                size="small"
                effect="dark"
              >
                <el-icon>
                  <component :is="wsConnected ? 'SuccessFilled' : 'CircleCloseFilled'" />
                </el-icon>
                {{ wsConnected ? '实时监控在线' : '监控离线' }}
              </el-tag>
            </div>
          </div>
        </div>
      </el-header>

      <el-main>
        <el-row :gutter="20">
          <el-col :span="16">
            <el-card class="video-card">
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

              <!-- 视频播放器容器 -->
              <div class="video-container">
                <!-- 视频源选择界面 -->
                <div v-if="!isStreaming" class="camera-placeholder">
                  <el-icon class="placeholder-icon"><VideoCamera /></el-icon>
                  <p>选择视频源开始智能监控</p>

                  <el-form class="source-selection" label-width="80px">
                    <el-form-item label="视频源">
                      <el-select v-model="videoSource" placeholder="选择视频源类型" @change="handleVideoSourceChange">
                        <el-option label="本地摄像头" value="local" />
                        <el-option label="RTSP流" value="rtsp" />
                        <el-option label="HLS流" value="hls" />
                        <el-option label="RTMP流" value="rtmp" />
                        <el-option label="HTTP-FLV流" value="flv" />
                        <el-option label="WebRTC流" value="webrtc" />
                        <el-option label="MP4文件" value="mp4" />
                      </el-select>
                    </el-form-item>

                    <!-- 本地摄像头选择 -->
                    <el-form-item v-if="videoSource === 'local'" label="设备">
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
                    </el-form-item>

                    <!-- 流地址输入 -->
                    <el-form-item v-if="videoSource !== 'local'" label="流地址">
                      <el-input
                        v-model="streamUrl"
                        :placeholder="getStreamPlaceholder()"
                        clearable
                      >
                        <template #append>
                          <el-button @click="testStreamConnection" :disabled="!streamUrl.trim()">测试连接</el-button>
                        </template>
                      </el-input>
                      <div class="input-help">
                        <el-text size="small" type="info">
                          💡 提示：请确保流媒体服务器运行正常，地址格式正确
                        </el-text>
                      </div>
                    </el-form-item>
                  </el-form>

                  <el-button 
                    type="primary" 
                    @click="startStream" 
                    :disabled="!canStartStream"
                    size="large"
                  >
                    <el-icon><VideoCamera /></el-icon>
                    开始监控
                  </el-button>
                </div>
                
                <!-- 视频播放区域 -->
                <div v-else class="video-player-wrapper">
                  <!-- 本地摄像头视频 -->
                  <video
                    v-if="videoSource === 'local'"
                    ref="videoElement"
                    class="video-element"
                    autoplay
                    muted
                    playsinline
                    @loadedmetadata="onVideoLoaded"
                  ></video>
                  
                  <!-- 网络流播放器容器 -->
                  <div
                    v-else
                    ref="videoRef"
                    class="dplayer-container"
                  ></div>
                  
                  <!-- AI分析器组件 -->
                  <AIAnalyzer
                    v-if="isStreaming"
                    ref="aiAnalyzer"
                    :video="video"
                    :camera-id="cameraId"
                    :enabled="aiAnalysisEnabled"
                    :realtime-mode="aiSettings.realtimeMode"
                    :danger-zones="dangerZones"
                    :current-zone-points="currentZonePoints"
                    :detection-results="detectionResults"
                    @detection-results="handleDetectionResults"
                    @performance-stats="handlePerformanceStats"
                    @canvas-click="handleCanvasClick"
                  />
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
                    <div class="setting-description">
                      识别视频中的人脸，并与已知人脸库进行匹配。可用于访客识别和权限控制。
                    </div>
                  </el-form-item>
                  <el-form-item label="目标检测">
                    <el-switch
                      v-model="aiSettings.objectDetection"
                      :disabled="!isStreaming"
                      @change="updateAISettings"
                    />
                    <div class="setting-description">
                      检测视频中的人员、车辆、包裹等常见目标，支持多目标同时跟踪。
                    </div>
                  </el-form-item>
                  <el-form-item label="行为分析">
                    <el-switch
                      v-model="aiSettings.behaviorAnalysis"
                      :disabled="!isStreaming"
                      @change="updateAISettings"
                    />
                    <div class="setting-description">
                      分析人员行为，如跌倒、奔跑、聚集等异常行为，及时发出预警。
                    </div>
                  </el-form-item>
                  <el-form-item label="声音检测">
                    <el-switch
                      v-model="aiSettings.soundDetection"
                      :disabled="!isStreaming"
                      @change="updateAISettings"
                    />
                    <div class="setting-description">
                      监测环境声音，检测异常噪音、尖叫等声音事件，提供声音告警。
                    </div>
                  </el-form-item>
                  <el-form-item label="火焰检测">
                    <el-switch
                      v-model="aiSettings.fireDetection"
                      :disabled="!isStreaming"
                      @change="updateAISettings"
                    />
                    <div class="setting-description">
                      检测视频中的火焰和烟雾，用于及早发现火灾隐患，保障安全。
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
                    <div class="setting-description">
                      高频检测模式下可达到15FPS的检测速率，但会增加系统负载；节能模式下智能调节检测频率，平衡性能和效果。
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
                    v-for="result in detectionResults"
                    :key="result.timestamp"
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

            <!-- 实时告警面板 -->
            <el-card class="alerts-panel" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>🚨 实时告警</span>
                  <el-badge :value="realtimeAlerts.length" class="badge" :max="99" />
                </div>
              </template>

              <el-scrollbar height="250px">
                <div class="alerts-list">
                  <div
                    v-for="(alert, index) in realtimeAlerts"
                    :key="alert.id"
                    class="alert-item"
                    :class="`alert-${alert.type}`"
                  >
                    <div class="alert-icon">
                      {{ getAlertIcon(alert.type) }}
                    </div>
                    <div class="alert-content">
                      <div class="alert-title">{{ alert.title }}</div>
                      <div class="alert-description">{{ alert.description }}</div>
                      <div class="alert-time">
                        {{ formatTime(alert.timestamp) }}
                      </div>
                    </div>
                    <el-button
                      link
                      size="small"
                      @click="removeAlert(index)"
                      class="alert-remove"
                    >
                      ×
                    </el-button>
                  </div>

                  <div v-if="realtimeAlerts.length === 0" class="no-alerts">
                    <el-icon><Warning /></el-icon>
                    <p>暂无告警信息</p>
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

<style scoped>
.video-monitor {
  height: 100%;
  padding: 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 15px;
}

.connection-status {
  display: flex;
  align-items: center;
}

.video-container {
  width: 100%;
  height: 480px;
  background-color: #000;
  position: relative;
  border-radius: 4px;
  overflow: hidden;
}

.video-player-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.video-element {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dplayer-container {
  width: 100%;
  height: 100%;
}

.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 10;
}

.camera-placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #fff;
  width: 80%;
  z-index: 5;
}

.placeholder-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.source-selection {
  margin: 20px auto;
  max-width: 400px;
  background: rgba(0, 0, 0, 0.5);
  padding: 20px;
  border-radius: 8px;
}

/* 确保 DPlayer 控件显示正确 */
:deep(.dplayer) {
  width: 100%;
  height: 100%;
}

:deep(.dplayer-video-wrap) {
  height: 100%;
}

:deep(.el-form-item__label) {
  color: #fff !important;
}

.control-panel {
  margin-bottom: 20px;
}

.analysis-settings {
  padding: 10px;
}

.setting-description {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
  padding-right: 10px;
}

.detection-list {
  padding: 10px;
}

.detection-item {
  display: flex;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid #eee;
}

.detection-icon {
  font-size: 24px;
  margin-right: 10px;
}

.detection-info {
  flex: 1;
}

.detection-name {
  font-weight: bold;
}

.detection-details {
  font-size: 12px;
  color: #909399;
}

.detection-time {
  font-size: 12px;
  color: #909399;
}

.no-results {
  text-align: center;
  padding: 20px;
  color: #909399;
}

/* 实时告警面板样式 */
.alerts-panel {
  margin-bottom: 20px;
}

.alerts-list {
  padding: 10px;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  border-left: 4px solid;
  background-color: #f8f9fa;
  transition: all 0.3s ease;
  position: relative;
}

.alert-item:hover {
  transform: translateX(3px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.alert-danger {
  border-left-color: #f56c6c;
  background-color: #fef0f0;
}

.alert-warning {
  border-left-color: #e6a23c;
  background-color: #fdf6ec;
}

.alert-info {
  border-left-color: #409eff;
  background-color: #ecf5ff;
}

.alert-success {
  border-left-color: #67c23a;
  background-color: #f0f9ff;
}

.alert-icon {
  font-size: 20px;
  margin-right: 12px;
  margin-top: 2px;
}

.alert-content {
  flex: 1;
  min-width: 0;
}

.alert-title {
  font-weight: bold;
  font-size: 14px;
  margin-bottom: 4px;
  color: #303133;
}

.alert-description {
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
  margin-bottom: 4px;
}

.alert-time {
  font-size: 11px;
  color: #909399;
}

.alert-remove {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 16px;
  line-height: 1;
  padding: 0;
  color: #909399;
}

.alert-remove:hover {
  background-color: #f56c6c;
  color: white;
}

.no-alerts {
  text-align: center;
  padding: 30px 20px;
  color: #909399;
}

.no-alerts .el-icon {
  font-size: 32px;
  margin-bottom: 10px;
}

/* 输入帮助样式 */
.input-help {
  margin-top: 4px;
  padding: 4px 8px;
  background-color: #f0f9ff;
  border-radius: 4px;
  border-left: 3px solid #409eff;
}
</style>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, watch, computed, onBeforeUnmount } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { VideoCamera, Close, Cpu, Search, SuccessFilled, Refresh, Edit, Location, CircleCloseFilled, Warning } from '@element-plus/icons-vue'
import { useApi } from '@/api'
import Flv from 'flv.js'
import 'video.js/dist/video-js.css'
import VideoJS from 'video.js'
import HLS from 'hls.js'
import DPlayer from 'dplayer'
import flvjs from 'flv.js'
import AIAnalyzer from '@/components/AIAnalyzer.vue'

const api = useApi()

// AI服务实例
const aiService = api.ai

// 请求重试函数
const requestWithRetry = async (service, config, maxRetries = 3) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await service(config)
      return response
    } catch (error) {
      if (i === maxRetries - 1) throw error
      console.warn(`请求失败，重试 ${i + 1}/${maxRetries}:`, error.message)
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)))
    }
  }
}

// 移除 CSS 导入，改用本地样式
const loadDPlayerCSS = () => {
  // 检查是否已加载CSS
  if (document.querySelector('#dplayer-styles')) {
    return Promise.resolve()
  }
  
  // 直接使用本地样式，避免网络依赖
  console.log('Loading DPlayer styles locally')
  addFallbackStyles()
  return Promise.resolve()
}

// 添加完整的DPlayer样式
const addFallbackStyles = () => {
  const style = document.createElement('style')
  style.id = 'dplayer-styles'
  style.textContent = `
    .dplayer {
      position: relative;
      width: 100%;
      height: 100%;
      background: #000;
      font-size: 14px;
      line-height: 1.5;
      user-select: none;
      border-radius: 8px;
      overflow: hidden;
    }
    .dplayer-video-wrap {
      position: relative;
      width: 100%;
      height: 100%;
      overflow: hidden;
    }
    .dplayer-video {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
      background: #000;
    }
    .dplayer-controller {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 41px;
      background: linear-gradient(transparent, rgba(0, 0, 0, 0.8));
      opacity: 0;
      transition: opacity 0.3s ease;
      z-index: 1;
      display: flex;
      align-items: center;
      padding: 0 20px;
    }
    .dplayer:hover .dplayer-controller {
      opacity: 1;
    }
    .dplayer-controller-mask {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 98px;
      pointer-events: none;
      background: linear-gradient(rgba(0,0,0,0), rgba(0,0,0,0.8));
    }
    .dplayer-loading {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      color: white;
      z-index: 2;
      font-size: 16px;
    }
    .dplayer-loading:after {
      content: '';
      display: inline-block;
      width: 20px;
      height: 20px;
      border: 2px solid #fff;
      border-radius: 50%;
      border-top-color: transparent;
      animation: dplayer-rotate 1s linear infinite;
      margin-left: 10px;
    }
    .dplayer-mask {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      z-index: 3;
      font-size: 16px;
    }
    .dplayer-bezel {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      color: white;
      z-index: 2;
      background: rgba(0, 0, 0, 0.5);
      padding: 10px 15px;
      border-radius: 4px;
      font-size: 14px;
      opacity: 0;
      transition: opacity 0.3s;
    }
    .dplayer-bezel.dplayer-bezel-transition {
      animation: dplayer-bezel 0.5s ease-in-out;
    }
    .dplayer-danmaku {
      position: absolute;
      left: 0;
      right: 0;
      top: 0;
      bottom: 0;
      font-size: 22px;
      color: #fff;
      pointer-events: none;
      z-index: 0;
    }
    .dplayer-subtitle {
      position: absolute;
      bottom: 40px;
      width: 90%;
      left: 5%;
      text-align: center;
      color: #fff;
      text-shadow: 0.5px 0.5px 0.5px rgba(0, 0, 0, 0.5);
      font-size: 20px;
      z-index: 2;
    }
    .dplayer-menu {
      position: absolute;
      width: 170px;
      border-radius: 2px;
      background: rgba(28, 28, 28, 0.85);
      padding: 5px 0;
      overflow: hidden;
      z-index: 3;
      display: none;
    }
    .dplayer-menu.dplayer-menu-show {
      display: block;
    }
    .dplayer-menu .dplayer-menu-item {
      height: 30px;
      box-sizing: border-box;
      cursor: pointer;
      position: relative;
      color: #eee;
      padding: 5px 10px;
      font-size: 13px;
      line-height: 20px;
    }
    .dplayer-menu .dplayer-menu-item:hover {
      background-color: rgba(255, 255, 255, 0.1);
    }
    @keyframes dplayer-rotate {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    @keyframes dplayer-bezel {
      0% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); }
      50% { opacity: 1; transform: translate(-50%, -50%) scale(1.1); }
      100% { opacity: 0; transform: translate(-50%, -50%) scale(1); }
    }
  `
  document.head.appendChild(style)
  console.log('✅ DPlayer本地样式已加载')
}

// 响应式数据
const videoElement = ref(null)
const videoRef = ref(null)
const video = ref(null)  // 传递给AIAnalyzer的video对象
const aiAnalyzer = ref(null)
const isStreaming = ref(false)
const aiAnalysisEnabled = ref(false)
const selectedDeviceId = ref('')
const videoDevices = ref([])
const analysisInterval = ref(1000)  // 增加到1秒间隔，减少AI服务负载
const videoSource = ref('local')  // 默认选择本地摄像头
const streamUrl = ref('')
const cameraId = ref('')

// AI设置
const aiSettings = reactive({
  faceRecognition: true,
  objectDetection: true,
  behaviorAnalysis: true,
  soundDetection: true,
  fireDetection: true,
  realtimeMode: false
})

// 检测结果
const detectionResults = ref([])
const lastFrameDetections = ref([])

// 内部变量
let mediaStream = null
let analysisTimer = null
let player = null
let wsConnection = null  // WebSocket连接

// 性能监控
const performanceStats = reactive({
  fps: 0,
  avgProcessTime: 0,
  processedFrames: 0,
  skippedFrames: 0,
  audioLevel: 0
})

// 告警去重机制
const alertCooldowns = new Map()
const ALERT_COOLDOWN = 5000
let isProcessingFrame = false

// 音频相关
let audioContext = null
let audioAnalyser = null
let audioDataArray = null
let audioMonitoringActive = false
let audioMonitoringId = null

// 性能优化相关
let lastFrameData = null
let consecutiveSlowFrames = 0
let currentImageScale = 1
let frameProcessTimes = []
let lastStatsUpdate = Date.now()
const MOTION_THRESHOLD = 0.015

// 实时告警列表
const realtimeAlerts = ref([])

// WebSocket连接状态
const wsConnected = ref(false)

// 危险区域管理
const dangerZones = ref([])
const currentZonePoints = ref([])
const isDrawingZone = ref(false)
const showZoneManager = ref(false)
const newZoneName = ref('')
const newZoneMinDistance = ref(50)
const newZoneDwellTime = ref(10)

// 视频源控制
const canStartStream = computed(() => {
  if (videoSource.value === 'local') {
    return selectedDeviceId.value;
  } else {
    return streamUrl.value.trim() !== '';
  }
});

// 获取流地址占位符文本
const getStreamPlaceholder = () => {
  const placeholders = {
    rtsp: 'rtsp://username:password@ip:port/path\n示例: rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4',
    hls: 'http://ip:port/path/stream.m3u8\n示例: https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8',
    rtmp: 'rtmp://ip:port/live/stream_name\n示例: rtmp://localhost:1935/live/test',
    flv: 'http://ip:port/live/stream.flv\n示例: http://localhost:8080/live/test.flv',
    webrtc: 'webrtc://ip:port/path\n示例: webrtc://localhost:8080/live/test',
    mp4: 'http://ip:port/path/video.mp4\n示例: https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4'
  }
  return placeholders[videoSource.value] || '请输入有效的视频流地址'
}

// 处理视频源变更
const handleVideoSourceChange = async () => {
  if (isStreaming.value) {
    stopStream();
  }
  
  // 根据视频源类型设置默认的流地址和配置
  switch (videoSource.value) {
    case 'rtsp':
      streamUrl.value = 'rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4';
      break;
    case 'rtmp':
      streamUrl.value = 'rtmp://localhost:1935/live/test';
      // 检查nginx RTMP服务器状态
      setTimeout(async () => {
        const nginxRunning = await checkNginxStatus()
        if (!nginxRunning) {
          ElMessage.warning('⚠️ 检测到您选择了RTMP格式，但nginx RTMP服务器似乎未运行。请确保启动nginx服务器。')
        }
      }, 500)
      break;
    case 'hls':
      streamUrl.value = 'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8';
      break;
    case 'flv':
      streamUrl.value = 'http://localhost:8080/live/test.flv';
      break;
    case 'webrtc':
      streamUrl.value = 'webrtc://localhost:1985/live/test';
      break;
    case 'mp4':
      streamUrl.value = 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4';
      break;
    default:
      streamUrl.value = '';
  }
  
  ElMessage.info(`已切换到 ${getVideoSourceName(videoSource.value)} 模式`);
};

// 获取视频源名称
const getVideoSourceName = (source) => {
  const names = {
    local: '本地摄像头',
    rtsp: 'RTSP流',
    rtmp: 'RTMP流',
    hls: 'HLS流',
    flv: 'HTTP-FLV流',
    webrtc: 'WebRTC流',
    mp4: 'MP4文件'
  };
  return names[source] || '未知格式';
};

// 综合流连接诊断
const testStreamConnection = async () => {
  try {
    ElMessage.info('🔍 正在进行综合诊断...');
    
    console.log('📊 开始综合流连接诊断')
    console.log('流地址:', streamUrl.value)
    console.log('流类型:', videoSource.value)
    
    // 1. 检查服务器状态
    const results = {
      aiService: false,
      nginxService: false,
      streamTest: false,
      fallbackTest: false
    }
    
    console.log('🔧 1. 检查AI服务状态...')
    results.aiService = await checkAIService()
    
    if (videoSource.value === 'rtmp' || videoSource.value === 'hls' || videoSource.value === 'flv') {
      console.log('🔧 2. 检查nginx服务状态...')
      results.nginxService = await checkNginxStatus()
    } else {
      results.nginxService = true // 非nginx依赖的格式
    }
    
    // 3. 测试原始流
    console.log('🔧 3. 测试原始流地址...')
    try {
      const response = await api.ai.testStreamConnection({
        url: streamUrl.value,
        type: videoSource.value,
        camera_id: `test_${Date.now()}`
      });
      results.streamTest = response.status === 'success'
      console.log('原始流测试结果:', results.streamTest)
    } catch (error) {
      console.warn('原始流测试失败:', error.message)
      results.streamTest = false
    }
    
    // 4. 测试智能回退流
    if (!results.streamTest && videoSource.value !== 'local') {
      console.log('🔧 4. 测试智能回退流...')
      try {
        const fallbacks = await generateFallbackStreams(streamUrl.value)
        for (const fallback of fallbacks.slice(1, 3)) { // 测试前2个回退选项
          const testResult = await testUrl(fallback.url)
          if (testResult) {
            results.fallbackTest = true
            console.log('找到可用回退流:', fallback)
            break
          }
        }
      } catch (error) {
        console.warn('回退流测试失败:', error)
      }
    }
    
          // 生成诊断报告
    const generateDiagnosticReport = () => {
      let report = '📋 诊断报告：\n\n'
      
      // AI服务状态
      report += `🤖 AI服务: ${results.aiService ? '✅ 正常' : '❌ 异常'}\n`
      
      // nginx服务状态
      if (videoSource.value === 'rtmp' || videoSource.value === 'hls' || videoSource.value === 'flv') {
        report += `🌐 nginx服务: ${results.nginxService ? '✅ 正常' : '❌ 异常'}\n`
      }
      
      // 流测试结果
      report += `📺 原始流: ${results.streamTest ? '✅ 可用' : '❌ 不可用'}\n`
      
      if (!results.streamTest) {
        report += `🔄 回退流: ${results.fallbackTest ? '✅ 找到可用选项' : '❌ 均不可用'}\n`
      }
      
      report += '\n💡 建议：\n'
      
      if (!results.aiService) {
        report += '• 请检查AI服务是否正常运行（端口8001）\n'
        report += '• 运行命令: python smart_station_platform/ai_service/app.py\n'
      }
      
      if (!results.nginxService && (videoSource.value === 'rtmp' || videoSource.value === 'hls' || videoSource.value === 'flv')) {
        report += '• 请启动nginx RTMP服务器\n'
        report += '• 检查nginx配置文件\n'
        report += '• 确认端口8080和1935未被占用\n'
      }
      
      if (!results.streamTest && !results.fallbackTest) {
        if (results.nginxService && (videoSource.value === 'rtmp' || videoSource.value === 'hls')) {
          report += '• nginx服务器运行正常，但没有检测到推流\n'
          report += '• 请运行测试推流: python test_rtmp_push.py\n'
          report += '• 或检查外部推流设备是否正常推送到 rtmp://localhost:1935/live/test\n'
        }
        report += '• 检查流地址是否正确\n'
        report += '• 确认流源是否正在推送\n'
        report += '• 检查网络连接\n'
      } else if (results.fallbackTest) {
        report += '• 系统将自动使用回退流\n'
      }
      
      return report
    }
    
    const report = generateDiagnosticReport()
    console.log('📋 诊断完成:\n', report)
    
    // 显示结果
    if (results.streamTest) {
      ElMessage.success('✅ 流连接测试成功！所有服务正常')
    } else if (results.fallbackTest) {
      ElMessage.warning('⚠️ 原始流不可用，但找到可用的回退选项')
    } else {
      ElMessage.error('❌ 流连接测试失败，请查看控制台诊断报告')
    }
    
  } catch (error) {
    console.error('综合诊断失败:', error);
    ElMessage.error('诊断过程失败：' + error.message);
  }
};

// 在组件销毁前清理播放器
onBeforeUnmount(() => {
  if (player) {
    try {
      player.destroy()
    } catch (e) {
      console.warn('清理播放器时发生错误:', e)
    }
    player = null
  }
})

// 启动视频播放器
const startVideoPlayer = async () => {
  try {
    console.log('正在启动视频播放器...')
    
    // 验证流地址
    if (videoSource.value !== 'local' && !streamUrl.value.trim()) {
      throw new Error('请先输入有效的视频流地址')
    }
    
    // 检查是否为测试地址
    if (streamUrl.value.includes('localhost') || streamUrl.value.includes('127.0.0.1')) {
      console.warn('⚠️  检测到本地测试地址，请确保相关服务已启动')
    }
    
    // 确保DOM已更新
    await nextTick()
    
    // 等待一小段时间确保DOM完全渲染
    await new Promise(resolve => setTimeout(resolve, 100))
    
    // 检查视频容器是否存在
    if (!videoRef.value) {
      console.error('videoRef.value 为空，DOM可能还没有准备好')
      console.log('当前视频源类型:', videoSource.value)
      console.log('当前isStreaming状态:', isStreaming.value)
      
      // 再次等待并检查
      for (let i = 0; i < 5; i++) {
        await new Promise(resolve => setTimeout(resolve, 200))
        if (videoRef.value) {
          console.log(`DOM元素在第${i+1}次检查后找到`)
          break
        }
      }
      
      if (!videoRef.value) {
        console.error('详细DOM状态检查:')
        console.log('document.querySelector(".dplayer-container"):', document.querySelector('.dplayer-container'))
        console.log('videoSource.value:', videoSource.value)
        console.log('isStreaming.value:', isStreaming.value)
        throw new Error('视频容器元素未找到，可能是DOM渲染问题或视频源选择错误')
      }
    }

    console.log('✅ 视频容器找到，开始创建播放器')

    // 销毁现有播放器
    if (player) {
      try {
        player.destroy()
      } catch (e) {
        console.warn('销毁播放器时发生错误:', e)
      }
      player = null
    }

    // 智能选择播放器配置
    console.log('🎯 获取智能视频配置...')
    let videoConfig = await getOptimalVideoConfig(streamUrl.value, videoSource.value)
    console.log('✅ 智能配置获取完成:', videoConfig)

    // 使用智能配置创建播放器
    await startVideoPlayerWithConfig(videoConfig)
    
    console.log('🎉 网络流播放器启动成功')

  } catch (error) {
    console.error('启动视频播放器时发生错误:', error)
    ElMessage.error('启动视频播放器失败：' + error.message)
    throw error
  }
}

// 停止视频播放器
const stopVideoPlayer = async () => {
  try {
    if (player) {
      try {
        // 先移除所有事件监听器，防止销毁后触发回调
        const tempPlayer = player
        player = null // 立即设置为null，防止事件回调中访问
        
        // 清除当前播放器标记
        if (window.currentPlayer === tempPlayer) {
          window.currentPlayer = null
        }
        
        // 暂停播放
        if (tempPlayer.video) {
          tempPlayer.video.pause()
          tempPlayer.video.src = '' // 清除视频源
        }
        
        // 销毁播放器
        tempPlayer.destroy()
        console.log('播放器已销毁')
      } catch (e) {
        console.warn('销毁播放器时发生错误:', e)
        player = null // 确保设置为null
        // 确保清除标记
        if (window.currentPlayer) {
          window.currentPlayer = null
        }
      }
    }
    
    // 注意：不清除videoElement.value，因为本地摄像头可能还在使用
    
  } catch (error) {
    console.error('停止视频播放器时发生错误:', error)
    player = null; // 错误时也要确保player为null
  }
}

// 重试视频播放
const retryVideoPlayer = async () => {
  // 防止并发重试
  if (retryVideoPlayer._isRetrying) {
    console.warn('重试已在进行中，跳过重复调用')
    return false
  }
  retryVideoPlayer._isRetrying = true
  
  try {
    console.log('🔄 尝试重新连接视频流...')
    
    // 检查流媒体状态是否仍然有效
    if (!isStreaming.value) {
      console.log('流媒体已停止，取消重连')
      return false
    }
    
    await stopVideoPlayer()
    await new Promise(resolve => setTimeout(resolve, 3000))
    
    // 重置播放器状态
    if (player) {
      player.retryCount = 0
      player._lastErrorTime = null
    }
    
    // 尝试当前流地址
    try {
      await startVideoPlayer()
      console.log('✅ 视频流重连成功')
      ElMessage.success('视频流重连成功')
      return true
    } catch (error) {
      console.error('当前流地址重连失败:', error)
      // 不在重试中调用回退，避免无限循环
      ElMessage.error('视频流重连失败，请手动重新启动')
      stopStream()
      return false
    }
  } catch (error) {
    console.error('重新连接视频流失败:', error)
    ElMessage.error('重新连接视频流失败：' + error.message)
    stopStream()
    return false
  } finally {
    retryVideoPlayer._isRetrying = false
  }
}

// 停止所有流媒体
const stopStream = async () => {
  try {
    // 停止播放器
    await stopVideoPlayer()

    // 停止AI分析
    if (cameraId.value) {
      try {
        await api.ai.stopStream(cameraId.value)
      } catch (error) {
        console.warn('停止AI流失败:', error)
      }
    }

    // 清理状态
    isStreaming.value = false
    aiAnalysisEnabled.value = false
    stopAIAnalysis()
    cameraId.value = ''
    detectionResults.value = []
    realtimeAlerts.value = []  // 清空实时告警
    
    // 重置回退状态
    resetFallbackState()
    
    // 清理Canvas
    if (canvasContext && overlayCanvas.value) {
      canvasContext.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height)
    }

    ElMessage.success('已停止所有流媒体播放')
  } catch (error) {
    console.error('停止流媒体失败:', error)
    ElMessage.error('停止流媒体失败：' + error.message)
  }
}

// 动态加载所需的播放器库
const loadVideoJS = async () => {
  if (window.videojs) return

  // 加载video.js CSS
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = 'https://vjs.zencdn.net/7.20.3/video-js.css'
  document.head.appendChild(link)

  // 加载video.js脚本
  await new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://vjs.zencdn.net/7.20.3/video.min.js'
    script.onload = resolve
    script.onerror = reject
    document.body.appendChild(script)
  })
}

// 停止摄像头和视频流
const stopCamera = async () => {
  try {
    // 如果存在videoPlayer，先销毁它
    if (videoPlayer.value) {
      videoPlayer.value.dispose();
      videoPlayer.value = null;
    }

    // 如果存在媒体流，停止所有轨道
    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      mediaStream = null;
    }

    // 停止音频监控
    stopAudioMonitoring();

    // 停止AI分析
    if (aiAnalysisEnabled.value) {
      await stopAIStream();
    }

    // 停止视频流
    try {
      if (cameraId.value) {
        await api.ai.stopStream(cameraId.value);
      }
    } catch (error) {
      console.warn('停止AI流失败:', error);
    }

    // 清理状态
    isStreaming.value = false;
    cameraId.value = '';

    ElMessage.success('已停止监控');
  } catch (error) {
    console.error('停止监控失败:', error);
    ElMessage.error('停止监控失败：' + error.message);
  }
}

// 组件卸载时清理
onUnmounted(() => {
  // 停止摄像头和流媒体
  stopCamera()
  
  // 停止音频监控
  stopAudioMonitoring()
  
  // 清理定时器
  if (analysisTimer) {
    clearTimeout(analysisTimer)
    analysisTimer = null
  }
  
  // 移除事件监听器
  window.removeEventListener('resize', resizeCanvas)
  
  // 清理媒体流
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop())
    mediaStream = null
  }
  
  // 清理音频上下文
  if (audioContext) {
    audioContext.close()
    audioContext = null
  }
  
  console.log('组件清理完成')
})

// 获取可用摄像头设备
const getVideoDevices = async () => {
  try {
    // 首先请求摄像头权限，这样才能获取设备标签
    try {
      const tempStream = await navigator.mediaDevices.getUserMedia({ video: true })
      tempStream.getTracks().forEach(track => track.stop()) // 立即停止临时流
    } catch (permissionError) {
      console.warn('摄像头权限请求失败，设备列表可能不完整:', permissionError)
      ElMessage.warning('需要摄像头权限才能获取完整设备列表')
    }
    
    const devices = await navigator.mediaDevices.enumerateDevices()
    videoDevices.value = devices.filter(device => device.kind === 'videoinput')
    
    console.log('📷 可用摄像头设备:', videoDevices.value)
    
    if (videoDevices.value.length > 0 && !selectedDeviceId.value) {
      selectedDeviceId.value = videoDevices.value[0].deviceId
    }
    
    if (videoDevices.value.length === 0) {
      ElMessage.warning('未检测到摄像头设备')
    }
  } catch (error) {
    console.error('获取摄像头设备失败:', error)
    ElMessage.error('无法获取摄像头设备列表：' + error.message)
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
// let audioMonitoringActive = false  // 删除这行重复声明
// let audioMonitoringId = null       // 删除这行重复声明

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
    console.log('🎥 开始启动本地摄像头...')
    console.log('当前videoSource:', videoSource.value)
    console.log('当前isStreaming:', isStreaming.value)
    
    // 先设置isStreaming状态，触发DOM更新显示video元素
    isStreaming.value = true
    
    // 等待DOM更新完成
    await nextTick()
    
    // 再等一下确保DOM完全渲染
    await new Promise(resolve => setTimeout(resolve, 500))
    
    const constraints = {
      video: {
        deviceId: selectedDeviceId.value ? { exact: selectedDeviceId.value } : undefined,
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: 'user'
      },
      audio: aiSettings.soundDetection
    }

    console.log('📝 请求摄像头权限，约束条件:', constraints)
    mediaStream = await navigator.mediaDevices.getUserMedia(constraints)
    console.log('✅ 成功获取摄像头媒体流')
    
    // 等待DOM更新，确保video元素已渲染
    await nextTick()
    
    // 增强的DOM元素检查
    console.log('🔍 检查video元素是否存在...')
    console.log('videoElement.value:', videoElement.value)
    
    if (!videoElement.value) {
      console.warn('❌ videoElement为null，等待DOM完全渲染...')
      // 等待更长时间确保DOM完全更新
      for (let i = 0; i < 10; i++) {
        await new Promise(resolve => setTimeout(resolve, 200))
        console.log(`第${i+1}次检查videoElement:`, videoElement.value)
        if (videoElement.value) {
          console.log(`✅ videoElement在第${i+1}次检查后找到`)
          break
        }
        
        // 强制重新触发DOM更新
        if (i === 3) {
          console.log('强制重新触发DOM更新...')
          isStreaming.value = false
          await nextTick()
          isStreaming.value = true
          await nextTick()
        }
      }
      
      if (!videoElement.value) {
        console.error('❌ DOM状态详细检查:')
        console.log('- document.querySelector("video.video-element"):', document.querySelector('video.video-element'))
        console.log('- videoSource.value:', videoSource.value)
        console.log('- isStreaming.value:', isStreaming.value)
        console.log('- 所有video元素:', document.querySelectorAll('video'))
        
        // 最后尝试：直接通过DOM查找video元素
        const videoEl = document.querySelector('video.video-element')
        if (videoEl) {
          console.log('✅ 通过DOM查找找到video元素，手动赋值')
          videoElement.value = videoEl
        } else {
          // 释放媒体流
          if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop())
            mediaStream = null
          }
          throw new Error('视频元素未找到，可能是DOM渲染问题。请刷新页面重试。')
        }
      }
    }
    
    console.log('✅ video元素已找到，开始设置媒体流')
    videoElement.value.srcObject = mediaStream
    
    // 等待视频元数据加载
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('视频加载超时'))
      }, 5000)
      
      videoElement.value.onloadedmetadata = () => {
        clearTimeout(timeout)
        console.log('✅ 视频元数据加载完成')
        resolve()
      }
      
      videoElement.value.onerror = (error) => {
        clearTimeout(timeout)
        console.error('❌ 视频加载失败:', error)
        reject(new Error('视频加载失败'))
             }
     })
     
     cameraId.value = selectedDeviceId.value || 'default'
    
    console.log('✅ 本地摄像头启动成功，cameraId:', cameraId.value)

    // 如果启用了声音检测，初始化音频分析
    if (aiSettings.soundDetection && mediaStream.getAudioTracks().length > 0) {
      console.log('🔊 初始化音频分析...')
      await initAudioAnalysis(mediaStream)
    }

    ElMessage.success('摄像头启动成功！')
    
    // 立即设置video对象
    video.value = videoElement.value
    console.log('🎯 立即设置video对象:', video.value)
    
    // 触发视频加载完成事件
    onVideoLoaded()
    
    // 向AI服务注册本地摄像头流
    try {
      const response = await api.ai.startStream({
        camera_id: cameraId.value,
        stream_url: 'local_camera',  // 标识本地摄像头
        enable_face_recognition: aiSettings.faceRecognition,
        enable_object_detection: aiSettings.objectDetection,
        enable_behavior_detection: aiSettings.behaviorAnalysis,
        enable_fire_detection: aiSettings.fireDetection
      })
      console.log('AI服务本地摄像头注册响应:', response)
    } catch (apiError) {
      console.warn('AI服务本地摄像头注册失败，但摄像头已启动:', apiError)
    }
    
    // 自动启动AI分析
    setTimeout(async () => {
      if (isStreaming.value && !aiAnalysisEnabled.value) {
        console.log('🚀 自动启动AI分析...')
        aiAnalysisEnabled.value = true
        try {
          await startFrameCapture()
          ElMessage.success('AI分析已自动启动')
        } catch (error) {
          console.error('自动启动AI分析失败:', error)
          aiAnalysisEnabled.value = false
        }
      }
    }, 1000) // 等待1秒后自动启动

  } catch (error) {
    console.error('启动摄像头失败:', error)
    
         // 清理资源
     if (mediaStream) {
       mediaStream.getTracks().forEach(track => track.stop())
       mediaStream = null
     }
     // 注意：不在这里重置isStreaming，让startStream函数处理
    
    ElMessage.error('启动摄像头失败：' + error.message)
    throw error
  }
}

// ... existing code ...

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
    if (!isStreaming.value || !aiAnalysisEnabled.value || isProcessingFrame) {
      return
    }

    // 获取正确的视频元素
    let video = null
    if (videoSource.value === 'local') {
      video = videoElement.value
    } else {
      video = player?.video
    }

    if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
      console.warn('视频元素未找到或尚未加载完成，跳过此帧')
      return
    }

    try {
      isProcessingFrame = true
      const startTime = performance.now()

      // 创建画布并捕获当前帧
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')

      // 动态分辨率调整 - 更保守的设置
      let scale = 0.4  // 默认使用较小的分辨率
      if (performanceStats.avgProcessTime > 8000) {
        scale = 0.2  // 处理时间超过8秒时使用最小分辨率
      } else if (performanceStats.avgProcessTime > 5000) {
        scale = 0.25  // 处理时间超过5秒时使用小分辨率
      } else if (performanceStats.avgProcessTime > 2000) {
        scale = 0.3  // 处理时间超过2秒时使用中等分辨率
      }

      // 设置画布尺寸
      canvas.width = Math.floor(video.videoWidth * scale)
      canvas.height = Math.floor(video.videoHeight * scale)
      
      // 绘制当前帧
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

      // 运动检测（可选）
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
      if (!aiSettings.realtimeMode && !hasSignificantMotion(imageData.data, lastFrameData)) {
        performanceStats.motionSkippedFrames++
        return
      }
      lastFrameData = imageData.data.slice()

      // 记录发送给AI的图像尺寸
      window.lastSentImageSize = {
        width: canvas.width,
        height: canvas.height
      }

      // 转换为Blob并发送到AI服务
      canvas.toBlob(async (blob) => {
        if (!blob) {
          return
        }
        
        try {
          const formData = new FormData()
          formData.append('frame', blob)
          formData.append('camera_id', cameraId.value)
          formData.append('timestamp', new Date().toISOString())
          formData.append('performance_mode', 'fast')  // 使用快速模式

          const response = await api.ai.analyzeFrame(formData)
          
          console.log('🔍 AI分析响应:', response)

          // 处理分析结果 - 适配AI服务的响应格式
          let detections = []
          if (response && response.status === 'success' && response.results && response.results.detections) {
            // AI服务标准格式: {status: "success", results: {detections: [...]}}
            detections = response.results.detections
            console.log('🔍 AI服务响应格式: success/results/detections')
          } else if (response && response.data && response.data.detections) {
            // 格式2: {data: {detections: [...]}}
            detections = response.data.detections
            console.log('🔍 响应格式: data/detections')
          } else if (response && response.detections) {
            // 格式3: {detections: [...]}
            detections = response.detections
            console.log('🔍 响应格式: 直接detections')
          } else if (Array.isArray(response)) {
            // 格式4: 直接返回数组
            detections = response
            console.log('🔍 响应格式: 数组')
          }

          if (detections && detections.length > 0) {
            console.log('📊 原始检测数据:', detections)
            
            const processedDetections = detections.map((detection, index) => {
              console.log(`🎯 处理检测 ${index + 1}:`, detection)
              
              const result = {
                type: detection.type || 'unknown',
                label: getDetectionLabel(detection),
                confidence: detection.confidence || 0,
                bbox: detection.bbox || [0, 0, 100, 100],
                timestamp: new Date(),
                tracking_id: detection.tracking_id || null
              }
              
              console.log(`✅ 转换后的检测 ${index + 1}:`, result)
              return result
            })
            
            console.log('🎨 准备更新检测结果，数量:', processedDetections.length)
            updateDetectionResults(processedDetections)
            
            // 立即触发重绘
            if (aiAnalyzer.value) {
              nextTick(() => {
                console.log('🎨 立即触发检测框重绘')
                aiAnalyzer.value.drawDangerZones()
              })
            }
          } else {
            console.log('ℹ️ 本帧未检测到目标，清除检测框')
            updateDetectionResults([])
          }

          // 更新性能统计
          const endTime = performance.now()
          const processTime = endTime - startTime
          performanceStats.avgProcessTime = (performanceStats.avgProcessTime * 0.9) + (processTime * 0.1)
          performanceStats.fps = Math.round(1000 / processTime)
        } catch (error) {
          console.error('AI分析失败:', error)
          performanceStats.errorCount++
        }
      }, 'image/jpeg', 0.6)  // 降低图像质量以减少传输时间

    } catch (error) {
      console.error('帧捕获失败:', error)
      performanceStats.errorCount++
    } finally {
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
    formData.append('camera_id', cameraId.value)
    formData.append('enable_face_recognition', aiSettings.faceRecognition)
    formData.append('enable_object_detection', aiSettings.objectDetection)
    formData.append('enable_behavior_detection', aiSettings.behaviorAnalysis)
    formData.append('enable_fire_detection', aiSettings.fireDetection)
    formData.append('performance_mode', 'fast') // 使用快速模式减少处理时间

    const response = await api.ai.analyzeFrame(formData);

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
  results.detections.forEach((detection, index) => {
    console.log(`🎯 处理检测 ${index + 1}:`, detection)

    const processedDetection = {
      type: detection.type,
      label: getDetectionLabel(detection),
      confidence: detection.confidence,
      bbox: detection.bbox,
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
    return detection.class_name || '目标'
  } else if (detection.type === 'face') {
    if (detection.known === true) {
      return detection.name || '已知人脸'
    } else {
      return '未知人脸'
    }
  } else if (detection.type === 'fire_detection') {
    return detection.detection_type === 'fire' ? '火焰' :
           detection.detection_type === 'smoke' ? '烟雾' :
           detection.class_name || '火灾风险'
  }
  return detection.class_name || detection.name || '未知'
}

// 获取告警标题
const getAlertTitle = (eventType) => {
  const titles = {
    'stranger_intrusion': '陌生人入侵',
    'person_fall': '人员跌倒',
    'fire_smoke': '火灾烟雾',
    'abnormal_sound': '异常声音',
    'unknown_face_detected': '未知人员',
    'object_person_detected': '人员检测',
    'fire_detection_fire': '火焰检测',
    'fire_detection_smoke': '烟雾检测',
    'danger_zone_intrusion': '危险区域入侵'
  }
  return titles[eventType] || '未知告警'
}

// 获取告警类型
const getAlertType = (eventType) => {
  if (!eventType) return 'info' // 添加空值检查
  
  if (eventType.includes('fire') || eventType.includes('danger') || eventType.includes('fall')) {
    return 'danger'
  } else if (eventType.includes('stranger') || eventType.includes('unknown')) {
    return 'warning'
  } else {
    return 'info'
  }
}

// 获取告警图标
const getAlertIcon = (type) => {
  const icons = {
    danger: '🔥',
    warning: '⚠️',
    info: 'ℹ️',
    success: '✅'
  }
  return icons[type] || '🔔'
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
  console.log('🔄 更新检测结果, 输入数量:', results.length)
  
  if (!results || results.length === 0) {
    // 清空检测结果
    detectionResults.value = []
    lastFrameDetections.value = []
    console.log('🧹 清空检测结果')
    return
  }
  
  // 对检测结果进行平滑处理
  const smoothedResults = smoothDetections(results, lastFrameDetections.value)
  console.log('🎯 平滑处理后数量:', smoothedResults.length)

  // 更新当前帧结果
  detectionResults.value = smoothedResults.slice(0, 20) // 仅显示最新的20个检测结果
  console.log('📊 最终检测结果数量:', detectionResults.value.length)

  // 缓存当前帧结果供下一帧使用
  lastFrameDetections.value = smoothedResults.slice()
  
  // 确保AIAnalyzer组件能接收到最新的检测结果
  console.log('🎨 检测结果已更新，等待Canvas重绘')
}

// 在视频上绘制检测结果 - 已移至AIAnalyzer组件
const drawDetectionResults = (results) => {
  // 绘制功能已移至AIAnalyzer组件，这里不再需要
  console.log('🎨 检测结果通过AIAnalyzer组件自动绘制')
}

// 测试检测框显示
const testDetectionBoxes = () => {
  if (!isStreaming.value) {
    ElMessage.warning('请先启动摄像头')
    return
  }

  // 获取Canvas尺寸用于测试坐标
  const canvas = aiAnalyzer.value?.getCanvas()
  if (!canvas) {
    ElMessage.error('Canvas未初始化，请稍后重试')
    console.error('❌ Canvas调试信息:')
    console.log('aiAnalyzer.value:', aiAnalyzer.value)
    console.log('canvas:', canvas)
    return
  }

  const canvasWidth = canvas.width || 640
  const canvasHeight = canvas.height || 480

  console.log('🧪 Canvas调试信息:', {
    canvas: canvas,
    width: canvasWidth,
    height: canvasHeight,
    style: {
      width: canvas.style.width,
      height: canvas.style.height,
      position: canvas.style.position,
      zIndex: canvas.style.zIndex
    }
  })

  const testResults = [
    {
      type: 'person',
      label: '测试人员',
      confidence: 0.95,
      bbox: [
        canvasWidth * 0.1,   // 左上X (10%)
        canvasHeight * 0.1,  // 左上Y (10%)
        canvasWidth * 0.4,   // 右下X (40%)
        canvasHeight * 0.7   // 右下Y (70%)
      ],
      timestamp: new Date()
    },
    {
      type: 'face',
      label: '测试人脸',
      confidence: 0.87,
      bbox: [
        canvasWidth * 0.15,  // 左上X (15%)
        canvasHeight * 0.15, // 左上Y (15%)
        canvasWidth * 0.35,  // 右下X (35%)
        canvasHeight * 0.4   // 右下Y (40%)
      ],
      timestamp: new Date()
    },
    {
      type: 'unknown_face',
      label: '未知人脸',
      confidence: 0.76,
      bbox: [
        canvasWidth * 0.6,   // 左上X (60%)
        canvasHeight * 0.2,  // 左上Y (20%)
        canvasWidth * 0.8,   // 右下X (80%)
        canvasHeight * 0.5   // 右下Y (50%)
      ],
      timestamp: new Date()
    },
    {
      type: 'fire_detection',
      label: '火焰',
      confidence: 0.92,
      bbox: [
        canvasWidth * 0.7,    // 左上X (70%)
        canvasHeight * 0.6,   // 左上Y (60%)
        canvasWidth * 0.9,    // 右下X (90%)
        canvasHeight * 0.8    // 右下Y (80%)
      ],
      timestamp: new Date()
    }
  ]

  console.log('🧪 测试检测框参数:', {
    canvasSize: [canvasWidth, canvasHeight],
    testResults
  })

  // 更新检测结果并触发重绘
  updateDetectionResults(testResults)
  
  // 确保立即重绘
  if (aiAnalyzer.value) {
    nextTick(() => {
      console.log('🎨 执行测试检测框重绘')
      aiAnalyzer.value.drawDangerZones()
    })
  }

  ElMessage.success('测试检测框已显示')
}

// 调试Canvas状态
const debugCanvas = () => {
  console.log('🔍 Canvas调试信息:')
  console.log('isStreaming:', isStreaming.value)
  console.log('aiAnalysisEnabled:', aiAnalysisEnabled.value)
  console.log('aiAnalyzer组件:', aiAnalyzer.value)
  
  if (aiAnalyzer.value) {
    const canvas = aiAnalyzer.value.getCanvas()
    const context = aiAnalyzer.value.getContext()
    console.log('Canvas元素:', canvas)
    console.log('Canvas上下文:', context)
    
    if (canvas) {
      console.log('Canvas尺寸:', {
        width: canvas.width,
        height: canvas.height,
        clientWidth: canvas.clientWidth,
        clientHeight: canvas.clientHeight
      })
      console.log('Canvas样式:', {
        position: canvas.style.position,
        top: canvas.style.top,
        left: canvas.style.left,
        zIndex: canvas.style.zIndex,
        pointerEvents: canvas.style.pointerEvents
      })
      console.log('Canvas父元素:', canvas.parentElement)
      
      // 检查Canvas是否可见
      const rect = canvas.getBoundingClientRect()
      console.log('Canvas位置信息:', rect)
      
      // 测试直接在Canvas上绘制一个红色矩形
      if (context) {
        context.save()
        context.strokeStyle = '#FF0000'
        context.lineWidth = 5
        context.strokeRect(50, 50, 200, 100)
        context.fillStyle = '#FF0000'
        context.font = 'bold 20px Arial'
        context.fillText('调试测试', 60, 110)
        context.restore()
        console.log('✅ 已在Canvas上绘制红色测试框')
        ElMessage.success('调试测试框已绘制，检查控制台输出')
      }
    } else {
      console.error('❌ Canvas元素未找到')
      ElMessage.error('Canvas元素未找到')
    }
  } else {
    console.error('❌ AIAnalyzer组件未找到')
    ElMessage.error('AIAnalyzer组件未找到')
  }
  
  // 检查视频元素
  const video = videoSource.value === 'local' ? videoElement.value : player?.video
  if (video) {
    console.log('视频元素:', video)
    console.log('视频尺寸:', {
      videoWidth: video.videoWidth,
      videoHeight: video.videoHeight,
      clientWidth: video.clientWidth,
      clientHeight: video.clientHeight
    })
    const videoRect = video.getBoundingClientRect()
    console.log('视频位置信息:', videoRect)
  } else {
    console.error('❌ 视频元素未找到')
  }
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
    const response = await requestWithRetry(() =>
      fetch(`/api/ai/detection/cache/clear/${cameraId.value}`, {
        method: 'POST'
      }).then(res => res.json())
    );

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
  return colors[type] || '#909399'
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
    const response = await api.aiService.post('/audio/frontend/alert/', {
      camera_id: cameraId.value,
      audio_level: audioLevel,
      event_type: eventType,
      timestamp: new Date().toISOString()
    });

    if (response.status !== 'success') {
      console.error('发送音频告警失败:', response.message)
    }
  } catch (error) {
    console.error('发送音频告警到AI服务失败:', error)
  }
}

// 切换AI分析
const toggleAIAnalysis = async () => {
  if (!isStreaming.value) {
    ElMessage.warning('请先启动摄像头')
    return
  }

  aiAnalysisEnabled.value = !aiAnalysisEnabled.value
  
  if (aiAnalysisEnabled.value) {
    try {
      console.log('🚀 启动AI分析...')
      await startFrameCapture()
      ElMessage.success('AI分析已启动')
    } catch (error) {
      console.error('启动AI分析失败:', error)
      ElMessage.error('启动AI分析失败：' + error.message)
      aiAnalysisEnabled.value = false
    }
  } else {
    try {
      console.log('⏹️ 停止AI分析...')
      if (analysisTimer) {
        clearTimeout(analysisTimer)
        analysisTimer = null
      }
      ElMessage.info('AI分析已停止')
    } catch (error) {
      console.error('停止AI分析失败:', error)
      ElMessage.error('停止AI分析失败：' + error.message)
    }
  }
}

// 更新AI设置
const updateAISettings = () => {
  if (aiAnalysisEnabled.value) {
    // 发送设置到AI服务
    // TODO: 实现设置更新逻辑
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
  console.log('📹 视频加载完成')

  nextTick(() => {
    let videoEl = null
    
    if (videoSource.value === 'local') {
      // 本地摄像头
      videoEl = videoElement.value
    } else {
      // 网络流 - 获取DPlayer的视频元素
      videoEl = player?.video
    }
    
    if (videoEl) {
      // 设置video对象供AIAnalyzer使用
      video.value = videoEl
      
      // 获取视频元素的实际显示尺寸
      const rect = videoEl.getBoundingClientRect()
      console.log('📐 视频显示尺寸:', {
        width: rect.width,
        height: rect.height,
        videoWidth: videoEl.videoWidth,
        videoHeight: videoEl.videoHeight
      })

      console.log('✅ 视频初始化完成，video对象已设置')

      // 立即触发AIAnalyzer组件更新
      nextTick(() => {
        if (aiAnalyzer.value) {
          console.log('🔄 立即触发AIAnalyzer Canvas调整')
          aiAnalyzer.value.resizeCanvas()
        }
      })

      // 监听视频尺寸变化
      videoEl.addEventListener('loadedmetadata', () => {
        console.log('视频元数据加载完成')
        // 重新设置video对象以触发AIAnalyzer更新
        video.value = videoEl
        nextTick(() => {
          if (aiAnalyzer.value) {
            console.log('🔄 元数据加载完成后触发Canvas调整')
            aiAnalyzer.value.resizeCanvas()
          }
        })
      })
    } else {
      console.error('❌ 无法获取视频元素!')
      video.value = null
    }
  })
}

// Canvas功能已移至AIAnalyzer组件
// const resizeCanvas = () => {
//   // 已移除：Canvas功能现在由AIAnalyzer组件处理
// }

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

  // 启用Canvas交互
  if (aiAnalyzer.value) {
    aiAnalyzer.value.setCanvasInteractive(true)
  }

  ElMessage.info('点击画面绘制区域顶点，右键完成绘制')
}

// 处理Canvas点击事件
const handleCanvasClick = ({ x, y, originalEvent }) => {
  if (!isDrawingZone.value) return

  // 右键完成绘制
  if (originalEvent.button === 2) {
    finishDrawing(originalEvent)
    return
  }

  // 左键添加顶点
  currentZonePoints.value.push([x, y])
  console.log(`添加顶点: (${x.toFixed(1)}, ${y.toFixed(1)})`)
}

// 完成绘制
const finishDrawing = (event) => {
  event.preventDefault()

  if (currentZonePoints.value.length < 3) {
    ElMessage.warning('至少需要3个顶点才能构成区域')
    return
  }

  // 禁用Canvas交互
  if (aiAnalyzer.value) {
    aiAnalyzer.value.setCanvasInteractive(false)
  }

  ElMessage.success(`区域绘制完成，共${currentZonePoints.value.length}个顶点`)
  showZoneManager.value = true
}

// 取消绘制
const cancelDrawing = () => {
  isDrawingZone.value = false
  currentZonePoints.value = []

  // 禁用Canvas交互
  if (aiAnalyzer.value) {
    aiAnalyzer.value.setCanvasInteractive(false)
  }
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
  if (aiAnalyzer.value) {
    aiAnalyzer.value.drawDangerZones()
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
      } else if (aiAnalyzer.value && videoElement.value) {
        // 如果没有上次发送尺寸，计算当前的发送尺寸（与captureFrame逻辑一致）
        const video = videoElement.value
        const canvas = aiAnalyzer.value.getCanvas()

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

      // 转换坐标
      const canvas = aiAnalyzer.value?.getCanvas()
      if (!canvas) {
        console.error('无法获取Canvas元素')
        return
      }
      
      const scaleX = targetWidth / canvas.width
      const scaleY = targetHeight / canvas.height

      return {
        ...zone,
        coordinates: zone.coordinates.map(point => [
          Math.round(point[0] * scaleX),
          Math.round(point[1] * scaleY)
        ])
      }
    })

    // 发送到AI服务
    const response = await api.ai.updateDangerZones({
      camera_id: cameraId.value,
      zones: convertedZones
    })

    if (response.status === 'success') {
      ElMessage.success('危险区域已同步到AI服务')
    } else {
      throw new Error(response.message || '同步失败')
    }
  } catch (error) {
    console.error('同步危险区域失败:', error)
    ElMessage.error('同步失败: ' + error.message)
  }
}

// 检查AI服务状态
const checkAIService = async () => {
  try {
    console.log('🔍 检查AI服务状态...')
    const response = await api.ai.getStreamStatus()
    console.log('✅ AI服务状态:', response)
    return true
  } catch (error) {
    console.warn('⚠️ AI服务响应异常:', error.response?.status || error.message)
    if (error.response?.status === 404) {
      console.warn('🔧 AI服务接口不存在，可能服务未启动或接口路径有误')
    }
    console.warn('💡 提示：请确保AI服务已启动在端口8001上')
    return false
  }
}

// 检查nginx RTMP服务器状态
const checkNginxStatus = async () => {
  const endpoints = [
    'http://localhost:8080/stat',      // nginx统计页面
    'http://localhost:8080/control',   // nginx控制页面
    'http://127.0.0.1:8080/stat',
    'http://127.0.0.1:8080/control'
  ]
  
  console.log('🔍 检查nginx RTMP服务器状态...')
  
  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint, {
        method: 'GET',
        mode: 'no-cors',
        timeout: 2000
      })
      console.log(`✅ nginx端点可访问: ${endpoint}`)
      return true
    } catch (error) {
      console.warn(`❌ nginx端点不可访问: ${endpoint}`)
    }
  }
  
  console.warn('⚠️ nginx RTMP服务器似乎未运行，RTMP流可能无法正常工作')
  ElMessage.warning('nginx RTMP服务器未检测到，建议检查服务器状态')
  return false
}

// 组件挂载时初始化
onMounted(async () => {
  await getVideoDevices()
  await loadDPlayerCSS()  // 确保CSS加载完成
  window.flvjs = flvjs  // 将 flvjs 添加到全局作用域
  
  // 检查服务状态
  await checkAIService()
  await checkNginxStatus()
  
  // 启动WebSocket连接
  connectWebSocket()
  startHeartbeat()
})

// 组件卸载时清理
onUnmounted(() => {
  stopCamera()
  disconnectWebSocket()  // 断开WebSocket连接
  window.removeEventListener('resize', resizeCanvas)
})

// 启动流媒体播放
const startStream = async () => {
  try {
    console.log('开始启动流媒体播放...')
    
    // 输入验证
    if (videoSource.value === 'local') {
      if (!selectedDeviceId.value) {
        ElMessage.error('请先选择摄像头设备')
        return
      }
    } else {
      if (!streamUrl.value || !streamUrl.value.trim()) {
        ElMessage.error('请先输入有效的视频流地址')
        return
      }
      
      // 增强的URL格式验证
      const urlPattern = /^(rtsp|rtmp|https?):\/\/.+/i
      if (!urlPattern.test(streamUrl.value.trim())) {
        ElMessage.error('视频流地址格式不正确，请输入以 rtsp://, rtmp://, http:// 或 https:// 开头的地址')
        return
      }
      
      // 检查常见的流格式问题
      const url = streamUrl.value.trim().toLowerCase()
      if (url.includes('rtmp://') && !url.includes(':1935')) {
        console.warn('⚠️ RTMP流未使用标准端口1935，可能需要确认端口设置')
      }
      if (url.includes('rtsp://') && !url.includes(':554') && !url.includes(':8554')) {
        console.warn('⚠️ RTSP流未使用常见端口(554/8554)，请确认端口设置')
      }
    }
    
    // 重置回退状态和重试计数
    resetFallbackState()
    
    // 生成唯一的摄像头ID
    cameraId.value = `${videoSource.value}_${Date.now()}`
    
    console.log('🚀 开始启动视频流:', {
      videoSource: videoSource.value,
      cameraId: cameraId.value,
      selectedDeviceId: selectedDeviceId.value,
      streamUrl: streamUrl.value
    })

    if (videoSource.value === 'local') {
      // 启动本地摄像头（在这里面会设置isStreaming和video对象）
      await startLocalCamera()
    } else {
      // 提示用户我们即将开始
      ElMessage.info('正在连接视频流，请稍候...')
      
      // 生成智能回退流地址列表
      streamFallbacks.value = await generateFallbackStreams(streamUrl.value.trim())
      console.log('📋 生成的智能回退流地址:', streamFallbacks.value)
      
      // 测试流连接性
      console.log(`正在测试视频流连接: ${streamUrl.value.trim()} (类型: ${videoSource.value})`)
      const testResult = await testStreamConnectivity(streamUrl.value.trim())
      if (!testResult.success) {
        console.warn(`⚠️ 流连接测试失败: ${testResult.error}，但仍会尝试播放`)
      } else {
        console.log('✅ 流连接测试成功')
      }
      
      // 先设置isStreaming状态，触发DOM更新
      isStreaming.value = true
      
      // 等待DOM更新完成
      await nextTick()
      
      // 再等一下确保DOM完全渲染
      await new Promise(resolve => setTimeout(resolve, 300))
      
      // 启动网络流
      await startVideoPlayer()
      
      // 启动AI服务的视频流处理
      try {
        const response = await api.ai.startStream({
          camera_id: cameraId.value,
          stream_url: streamUrl.value.trim(),
          enable_face_recognition: aiSettings.faceRecognition,
          enable_object_detection: aiSettings.objectDetection,
          enable_behavior_detection: aiSettings.behaviorAnalysis,
          enable_fire_detection: aiSettings.fireDetection
        })

        console.log('AI服务启动响应:', response)
      } catch (apiError) {
        console.warn('AI服务启动失败，但视频播放器已启动:', apiError)
      }
    }
    
    ElMessage.success('视频流启动成功')
  } catch (error) {
    console.error('启动流媒体失败:', error)
    
    // 如果是本地摄像头失败，直接清理状态
    if (videoSource.value === 'local') {
      ElMessage.error('启动本地摄像头失败：' + error.message)
      // 清理状态
      isStreaming.value = false
      cameraId.value = ''
      // 清理媒体流
      if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop())
        mediaStream = null
      }
    } 
    // 如果主流失败且有回退选项，尝试回退
    else if (streamFallbacks.value && streamFallbacks.value.length > 1) {
      console.log('主流启动失败，尝试回退流...')
      const success = await tryNextFallback()
      if (!success) {
        ElMessage.error('所有视频流地址都无法连接，请检查：\n1. 网络连接\n2. 流媒体服务器状态\n3. 视频流地址是否正确')
        // 清理状态
        isStreaming.value = false
        cameraId.value = ''
      }
    } else {
      ElMessage.error('启动流媒体失败：' + error.message)
      // 清理状态
      isStreaming.value = false
      cameraId.value = ''
    }
  }
}

// 重连机制
const reconnectPlayer = async () => {
  try {
    // 确保完全停止当前播放器
    await stopVideoPlayer()
    // 增加等待时间，确保资源完全释放
    await new Promise(resolve => setTimeout(resolve, 2000))
    // 重新创建播放器
    await startVideoPlayer()
  } catch (error) {
    console.error('重连失败:', error)
  }
}

// 开始AI分析
const startAIAnalysis = async () => {
  try {
    // TODO: 实现AI分析启动逻辑
    console.log('开始AI分析')
  } catch (error) {
    console.error('启动AI分析失败:', error)
    ElMessage.error('启动AI分析失败')
  }
}

// 停止AI分析
const stopAIAnalysis = () => {
  try {
    // TODO: 实现AI分析停止逻辑
    console.log('停止AI分析')
  } catch (error) {
    console.error('停止AI分析失败:', error)
  }
}

// WebSocket连接管理
const connectWebSocket = () => {
  try {
    // 连接告警WebSocket
    wsConnection = new WebSocket('ws://localhost:8000/ws/alerts/')
    
    wsConnection.onopen = () => {
      console.log('✅ AI监控WebSocket已连接')
      wsConnected.value = true
      ElMessage.success('实时监控已启动')
    }
    
    wsConnection.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleWebSocketMessage(data)
      } catch (error) {
        console.error('解析WebSocket消息失败:', error)
      }
    }
    
    wsConnection.onclose = () => {
      console.log('❌ AI监控WebSocket连接断开')
      wsConnected.value = false
      
      // 自动重连
      setTimeout(() => {
        if (isStreaming.value) {
          console.log('🔄 尝试重连WebSocket...')
          connectWebSocket()
        }
      }, 3000)
    }
    
    wsConnection.onerror = (error) => {
      console.error('WebSocket连接错误:', error)
      wsConnected.value = false
    }
    
  } catch (error) {
    console.error('创建WebSocket连接失败:', error)
    ElMessage.error('无法建立实时监控连接')
  }
}

// 断开WebSocket连接
const disconnectWebSocket = () => {
  if (wsConnection) {
    wsConnection.close()
    wsConnection = null
    wsConnected.value = false
    console.log('📡 WebSocket连接已关闭')
  }
}

// 处理WebSocket消息
const handleWebSocketMessage = (data) => {
  console.log('📨 收到WebSocket消息:', data)
  
  switch (data.type) {
    case 'new_alert':
      handleNewAlert(data.data)
      break
    case 'alert_update':
      handleAlertUpdate(data.data)
      break
    case 'detection_result':
      handleDetectionResult(data.data)
      break
    case 'pong':
      // 心跳响应
      break
    default:
      console.log('未处理的消息类型:', data.type)
  }
}

// 处理新告警
const handleNewAlert = (alertData) => {
  console.log('🚨 收到新告警:', alertData)
  
  const alert = {
    id: alertData.id,
    title: getAlertTitle(alertData.event_type),
    description: `摄像头: ${alertData.camera?.name || alertData.camera_id}, 置信度: ${(alertData.confidence * 100).toFixed(1)}%`,
    type: getAlertType(alertData.event_type),
    timestamp: new Date(alertData.timestamp),
    camera_id: alertData.camera_id,
    confidence: alertData.confidence,
    location: alertData.location
  }
  
  addAlert(alert)
  
  // 如果是当前摄像头的告警，可以在视频上显示特殊标记
  if (alertData.camera_id === cameraId.value) {
    highlightAlertOnVideo(alertData)
  }
}

// 处理告警更新
const handleAlertUpdate = (alertData) => {
  console.log('🔄 告警状态更新:', alertData)
  // 可以根据需要更新UI中的告警状态
}

// 处理检测结果
const handleDetectionResult = (resultData) => {
  console.log('🎯 收到检测结果:', resultData)
  
  if (resultData.camera_id === cameraId.value) {
    // 如果是当前摄像头的检测结果，直接更新显示
    if (resultData.detections) {
      const detections = resultData.detections.map(detection => ({
        type: detection.type,
        label: getDetectionLabel(detection),
        confidence: detection.confidence,
        bbox: detection.bbox,
        timestamp: new Date(detection.timestamp || Date.now())
      }))
      
      updateDetectionResults(detections)
      drawDetectionResults(detections)
    }
  }
}

// 在视频上高亮显示告警位置
const highlightAlertOnVideo = (alertData) => {
  if (!canvasContext || !overlayCanvas.value) return
  
  // 在告警位置绘制闪烁的红色边框
  const highlightBox = () => {
    if (alertData.location && alertData.location.box) {
      const [x1, y1, x2, y2] = alertData.location.box
      
      canvasContext.save()
      canvasContext.strokeStyle = '#FF4444'
      canvasContext.lineWidth = 4
      canvasContext.setLineDash([10, 5])
      canvasContext.strokeRect(x1, y1, x2 - x1, y2 - y1)
      canvasContext.restore()
    }
  }
  
  // 闪烁效果
  let count = 0
  const blink = setInterval(() => {
    highlightBox()
    count++
    if (count >= 6) {  // 闪烁3次
      clearInterval(blink)
    }
  }, 500)
}

// 发送心跳
const sendHeartbeat = () => {
  if (wsConnection && wsConnected.value) {
    wsConnection.send(JSON.stringify({
      type: 'ping',
      timestamp: new Date().toISOString()
    }))
  }
}

// 启动心跳
const startHeartbeat = () => {
  setInterval(sendHeartbeat, 30000)  // 每30秒发送一次心跳
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
  return icons[type] || '🔍'
}

// 视频流回退配置
const streamFallbacks = ref([])
let currentFallbackIndex = 0

// 生成智能回退流地址列表
const generateFallbackStreams = async (originalUrl) => {
  console.log('🔄 生成智能回退流列表，原始URL:', originalUrl)
  
  const fallbacks = []
  
  try {
    if (videoSource.value === 'rtmp') {
      // RTMP智能回退
      const streamName = originalUrl.split('/').pop()
      fallbacks.push(
        // 首选：HLS转换（最兼容）
        { url: `http://localhost:8080/hls/${streamName}.m3u8`, type: 'hls', priority: 1 },
        { url: `http://127.0.0.1:8080/hls/${streamName}.m3u8`, type: 'hls', priority: 2 },
        // 次选：HTTP-FLV（低延迟）
        { url: `http://localhost:8080/live/${streamName}.flv`, type: 'flv', priority: 3 },
        { url: `http://127.0.0.1:8080/live/${streamName}.flv`, type: 'flv', priority: 4 },
        // 最后：直接RTMP（可能不支持）
        { url: originalUrl, type: 'auto', priority: 5 }
      )
    } else if (videoSource.value === 'hls') {
      // HLS回退选项
      fallbacks.push(
        { url: originalUrl, type: 'hls', priority: 1 },
        { url: originalUrl.replace('http://', 'https://'), type: 'hls', priority: 2 },
        { url: originalUrl.replace(':8080', ':8081'), type: 'hls', priority: 3 },
        { url: originalUrl.replace('.m3u8', '_backup.m3u8'), type: 'hls', priority: 4 }
      )
    } else if (videoSource.value === 'rtsp') {
      // RTSP智能回退（需要转换）
      const streamId = originalUrl.replace(/[^\w]/g, '_')
      fallbacks.push(
        { url: `http://localhost:8080/hls/${streamId}.m3u8`, type: 'hls', priority: 1 },
        { url: `http://localhost:8080/live/${streamId}.flv`, type: 'flv', priority: 2 },
        { url: originalUrl.replace('rtsp://', 'rtsps://'), type: 'auto', priority: 3 },
        { url: originalUrl.replace(':554', ':8554'), type: 'auto', priority: 4 }
      )
    } else if (videoSource.value === 'flv') {
      // FLV回退选项
      fallbacks.push(
        { url: originalUrl, type: 'flv', priority: 1 },
        { url: originalUrl.replace('http://', 'https://'), type: 'flv', priority: 2 },
        { url: originalUrl.replace(':8080', ':8081'), type: 'flv', priority: 3 }
      )
    } else {
      // 其他格式使用原始URL
      fallbacks.push({ url: originalUrl, type: 'auto', priority: 1 })
    }
    
    // 去重并按优先级排序
    const uniqueFallbacks = []
    const seenUrls = new Set()
    
    fallbacks
      .sort((a, b) => a.priority - b.priority)
      .forEach(fallback => {
        if (!seenUrls.has(fallback.url)) {
          seenUrls.add(fallback.url)
          uniqueFallbacks.push(fallback)
        }
      })
    
    console.log('✅ 生成的智能回退列表:', uniqueFallbacks)
    return uniqueFallbacks
    
  } catch (error) {
    console.error('生成回退流失败:', error)
    // 返回基本回退
    return [{ url: originalUrl, type: 'auto', priority: 1 }]
  }
}

// 尝试下一个智能回退流
const tryNextFallback = async () => {
  // 防止并发调用
  if (tryNextFallback._isRunning) {
    console.warn('tryNextFallback已在运行中，跳过重复调用')
    return false
  }
  tryNextFallback._isRunning = true
  
  let fallbackConfig = null
  let fallbackUrl = ''
  let fallbackType = ''
  
  try {
    if (!streamFallbacks.value || currentFallbackIndex >= streamFallbacks.value.length - 1) {
      console.error('没有更多回退选项可尝试')
      ElMessage.error('所有视频流地址都无法连接，请检查网络和流媒体服务器状态')
      stopStream()
      return false
    }
    
    currentFallbackIndex++
    fallbackConfig = streamFallbacks.value[currentFallbackIndex]
    fallbackUrl = fallbackConfig.url
    fallbackType = fallbackConfig.type
    
    console.log(`🔄 尝试回退流 ${currentFallbackIndex + 1}/${streamFallbacks.value.length}: ${fallbackUrl} (${fallbackType})`)
    ElMessage.info(`尝试备用流地址 ${currentFallbackIndex + 1}/${streamFallbacks.value.length}: ${fallbackUrl}`)
    
    // 临时更新流地址和类型
    streamUrl.value = fallbackUrl
    
    // 重置播放器重试计数
    if (player) {
      player.retryCount = 0
      player._lastErrorTime = null
    }
    
    // 重新启动播放器
    await stopVideoPlayer()
    await new Promise(resolve => setTimeout(resolve, 1500))
    
    // 使用回退配置直接创建播放器
    await startVideoPlayerWithConfig(fallbackConfig)
    
    console.log(`✅ 成功连接到备用视频流: ${fallbackUrl}`)
    ElMessage.success(`✅ 成功连接到备用视频流`)
    return true
    
  } catch (error) {
    console.error(`❌ 回退流 ${fallbackUrl} 失败: ${error.message}`)
    
    // 如果还有更多回退选项，递归尝试（但避免无限循环）
    if (currentFallbackIndex < streamFallbacks.value.length - 1) {
      console.log(`还有 ${streamFallbacks.value.length - 1 - currentFallbackIndex} 个回退选项可尝试`)
      await new Promise(resolve => setTimeout(resolve, 2000)) // 增加延迟
      return await tryNextFallback()
    } else {
      console.error('所有回退选项都已尝试完毕')
      ElMessage.error('所有备用视频流都无法连接，请检查网络连接和流地址')
      stopStream()
      return false
    }
  } finally {
    // 确保无论如何都会重置运行状态
    setTimeout(() => {
      tryNextFallback._isRunning = false
    }, 100)
  }
}

// 使用指定配置启动播放器
const startVideoPlayerWithConfig = async (config) => {
  console.log('🎯 使用指定配置启动播放器:', config)
  
  try {
    // 确保DOM已更新
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))
    
    // 检查视频容器
    if (!videoRef.value) {
      throw new Error('视频容器元素未找到')
    }
    
        // 销毁现有播放器
    if (player) {
      try {
        // 清除当前播放器标记
        if (window.currentPlayer === player) {
          window.currentPlayer = null
        }
        player.destroy()
      } catch (e) {
        console.warn('销毁播放器时发生错误:', e)
      }
      player = null
    }

    // 使用传入的配置
    const options = {
      container: videoRef.value,
      video: config,
      autoplay: true,
      live: true,
      danmaku: false,
      screenshot: false,
      hotkey: false,
      preload: 'auto',
      theme: '#409EFF',
      loop: false,
      lang: 'zh-cn',
      volume: 0.7,
      mutex: true,
      // 针对不同格式的优化
      pluginOptions: {
        hls: {
          enableWorker: true,
          lowLatencyMode: true,
          backBufferLength: 90
        },
        flv: {
          mediaDataSource: {
            isLive: true,
            cors: true,
            withCredentials: false
          },
          config: {
            enableWorker: false,
            enableStashBuffer: false,
            stashInitialSize: 128
          }
        }
      }
    }
    
    console.log('📺 创建回退播放器，配置:', options)
    
    // 创建新的播放器实例
    player = new DPlayer(options)
    
    // 标记为当前活跃的播放器实例
    window.currentPlayer = player
    
    // 添加事件监听器（复用原有逻辑）
    setupPlayerEvents()
    
    console.log('✅ 回退播放器创建成功')
    
  } catch (error) {
    console.error('❌ 使用指定配置启动播放器失败:', error)
    throw error
  }
}

// 设置播放器事件监听器（抽取出来复用）
const setupPlayerEvents = () => {
  if (!player) return
  
  // 防止重复绑定事件
  if (player._eventsSetup) {
    console.log('播放器事件已设置，跳过重复绑定')
    return
  }
  player._eventsSetup = true
  
  // 错误处理
  player.on('error', (err) => {
    console.error('播放器发生错误:', err)
    
    // 检查播放器和流状态
    if (!player || !isStreaming.value || player !== window.currentPlayer) {
      console.warn('播放器已被销毁或流已停止，忽略错误事件')
      return
    }
    
    // 标记当前播放器实例
    window.currentPlayer = player
    
    // 初始化重试计数和错误时间
    if (!player.retryCount) player.retryCount = 0
    if (!player._lastErrorTime) player._lastErrorTime = 0
    
    // 防止快速重复错误 - 增加到5秒间隔
    const now = Date.now()
    if (player._lastErrorTime && (now - player._lastErrorTime) < 5000) {
      console.warn('错误事件触发过于频繁，跳过此次处理')
      return
    }
    player._lastErrorTime = now
    
    let errorMessage = '视频播放失败'
    let errorCode = 'UNKNOWN'
    
    if (err && err.target && err.target.error) {
      errorCode = err.target.error.code
      switch(errorCode) {
        case MediaError.MEDIA_ERR_ABORTED:
          errorMessage = '视频播放被中止'
          break
        case MediaError.MEDIA_ERR_NETWORK:
          errorMessage = '网络错误，无法获取视频'
          break
        case MediaError.MEDIA_ERR_DECODE:
          errorMessage = '视频解码错误'
          break
        case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
          errorMessage = '视频格式不支持或地址无效'
          break
        default:
          errorMessage = '未知的播放错误'
      }
    }
    
    console.warn(`播放器错误: ${errorMessage} (代码: ${errorCode})`)
    
    player.retryCount++
    
    // 达到最大重试次数
    if (player.retryCount > 3) {
      console.error('播放器达到最大重试次数，停止尝试')
      ElMessage.error('播放器多次尝试失败，请检查视频源或网络连接')
      stopStream()
      return
    }
    
    // 根据错误类型决定处理策略
    if (errorCode === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED) {
      // 只有在有回退选项时才尝试回退
      if (streamFallbacks.value && currentFallbackIndex < streamFallbacks.value.length - 1) {
        ElMessage.warning(`${errorMessage}，正在尝试其他格式... (${player.retryCount}/3)`)
        // 防止并发调用
        if (!tryNextFallback._isRunning) {
          setTimeout(() => {
            if (isStreaming.value && player && player.retryCount <= 3) {
              tryNextFallback().catch(err => {
                console.error('回退失败:', err)
                if (isStreaming.value) {
                  stopStream()
                }
              })
            }
          }, 3000)
        }
      } else {
        ElMessage.error('视频格式不支持且无可用的备用流')
        stopStream()
      }
    } else {
      ElMessage.error(`${errorMessage}，正在尝试重连... (${player.retryCount}/3)`)
      // 防止并发调用
      if (!retryVideoPlayer._isRetrying) {
        setTimeout(() => {
          if (isStreaming.value && player && player.retryCount <= 3) {
            console.log('尝试自动重连...')
            retryVideoPlayer().catch(err => {
              console.error('重连失败:', err)
              if (isStreaming.value) {
                stopStream()
              }
            })
          }
        }, 8000) // 增加重连延迟到8秒
      }
    }
  })
  
  // 其他事件
  player.on('loadstart', () => {
    console.log('开始加载视频流')
    ElMessage.info('正在加载视频流...')
  })
  
  player.on('canplay', () => {
    console.log('视频可以播放')
    ElMessage.success('视频流连接成功')
    
    // 设置video对象供AIAnalyzer使用
    if (player && player.video) {
      video.value = player.video
      console.log('🎯 网络流video对象已设置:', video.value)
    }
    
    onVideoLoaded()
  })
  
  player.on('waiting', () => console.log('视频缓冲中...'))
  player.on('stalled', () => console.warn('视频流停滞，可能网络问题'))
  player.on('abort', () => console.warn('视频加载被中止'))
  
  player.on('ended', () => {
    console.log('视频播放结束')
    if (videoSource.value !== 'local') {
      setTimeout(() => {
        if (isStreaming.value && player) {
          retryVideoPlayer()
        }
      }, 2000)
    }
  })
  
  // 添加播放器质量监控
  startPlaybackMonitoring()
}

// 播放器质量监控
const startPlaybackMonitoring = () => {
  if (!player) return
  
  let lastTime = Date.now()
  let frameCount = 0
  
  const monitorPlayback = () => {
    if (player && player.video) {
      const now = Date.now()
      if (now - lastTime >= 1000) {
        const currentFrameCount = Math.floor(player.video.currentTime)
        const actualFps = (currentFrameCount - frameCount) / ((now - lastTime) / 1000)
        
        if (actualFps < 5 && isStreaming.value) {
          console.warn('⚠️ 检测到低帧率，可能需要重连')
        }
        
        frameCount = currentFrameCount
        lastTime = now
      }
    }
    
    if (isStreaming.value && player) {
      setTimeout(monitorPlayback, 1000)
    }
  }
  
  setTimeout(monitorPlayback, 2000)
}

// 重置回退状态
const resetFallbackState = () => {
  currentFallbackIndex = 0
  streamFallbacks.value = []
}

// 智能获取最优视频配置
const getOptimalVideoConfig = async (url, sourceType) => {
  console.log(`🎯 为 ${sourceType} 类型的流 ${url} 选择最优配置`)
  
  try {
    switch (sourceType) {
      case 'rtmp':
        return await getRtmpConfig(url)
      case 'hls':
        return await getHlsConfig(url)
      case 'rtsp':
        return await getRtspConfig(url)
      case 'flv':
        return await getFlvConfig(url)
      case 'mp4':
        return { url, type: 'normal' }
      case 'webrtc':
        ElMessage.warning('WebRTC格式正在开发中，建议使用HLS或RTMP格式')
        return { url, type: 'auto' }
      default:
        return { url, type: 'auto' }
    }
  } catch (error) {
    console.error('获取视频配置失败:', error)
    // 回退到原始配置
    return { url, type: 'auto' }
  }
}

// RTMP流配置（转换为Web兼容格式）
const getRtmpConfig = async (rtmpUrl) => {
  console.log('🔄 处理RTMP流:', rtmpUrl)
  
  // 提取流名称
  const streamName = rtmpUrl.split('/').pop()
  console.log('📺 流名称:', streamName)
  
  // 生成可能的转换URL列表
  const candidates = [
    // HLS格式 (最兼容)
    `http://localhost:8080/hls/${streamName}.m3u8`,
    `http://127.0.0.1:8080/hls/${streamName}.m3u8`,
    // HTTP-FLV格式 (低延迟)
    `http://localhost:8080/live/${streamName}.flv`,
    `http://127.0.0.1:8080/live/${streamName}.flv`,
    // 直接尝试原始RTMP (某些播放器可能支持)
    rtmpUrl
  ]
  
  console.log('🎯 RTMP候选URL列表:', candidates)
  
  // 测试每个候选URL
  for (const candidate of candidates) {
    try {
      console.log(`🔍 测试 ${candidate}`)
      const isAvailable = await testUrl(candidate)
      if (isAvailable) {
        const type = candidate.includes('.m3u8') ? 'hls' : 
                    candidate.includes('.flv') ? 'flv' : 'auto'
        console.log(`✅ 找到可用URL: ${candidate} (类型: ${type})`)
        return { url: candidate, type }
      }
    } catch (error) {
      console.warn(`❌ ${candidate} 不可用:`, error.message)
    }
  }
  
  // 如果所有都失败，返回HLS作为默认选项
  console.warn('⚠️ 所有RTMP转换URL都不可用，使用默认HLS配置')
  return { 
    url: `http://localhost:8080/hls/${streamName}.m3u8`, 
    type: 'hls' 
  }
}

// HLS流配置
const getHlsConfig = async (hlsUrl) => {
  console.log('🎵 处理HLS流:', hlsUrl)
  
  const isAvailable = await testUrl(hlsUrl)
  if (isAvailable) {
    return { url: hlsUrl, type: 'hls' }
  } else {
    throw new Error('HLS流不可用')
  }
}

// RTSP流配置（转换为Web兼容格式）
const getRtspConfig = async (rtspUrl) => {
  console.log('📡 处理RTSP流:', rtspUrl)
  
  // RTSP需要后端转换，生成候选URL
  const streamId = rtspUrl.replace(/[^\w]/g, '_')
  const candidates = [
    `http://localhost:8080/hls/${streamId}.m3u8`,
    `http://localhost:8080/live/${streamId}.flv`
  ]
  
  for (const candidate of candidates) {
    try {
      const isAvailable = await testUrl(candidate)
      if (isAvailable) {
        const type = candidate.includes('.m3u8') ? 'hls' : 'flv'
        console.log(`✅ RTSP转换URL可用: ${candidate}`)
        return { url: candidate, type }
      }
    } catch (error) {
      console.warn(`❌ RTSP转换失败: ${candidate}`)
    }
  }
  
  // 如果转换不可用，尝试通过AI服务处理
  ElMessage.warning('RTSP流需要后端转换服务，请确保相关服务已启动')
  return { url: candidates[0], type: 'hls' }
}

// FLV流配置
const getFlvConfig = async (flvUrl) => {
  console.log('📹 处理FLV流:', flvUrl)
  
  const isAvailable = await testUrl(flvUrl)
  if (isAvailable) {
    return { url: flvUrl, type: 'flv' }
  } else {
    throw new Error('FLV流不可用')
  }
}

// 测试URL可用性
const testUrl = async (url) => {
  return new Promise((resolve) => {
    const timeout = 3000
    let resolved = false
    
    const resolveOnce = (result) => {
      if (!resolved) {
        resolved = true
        resolve(result)
      }
    }
    
    // 超时处理
    setTimeout(() => resolveOnce(false), timeout)
    
    if (url.includes('rtmp://')) {
      // RTMP通过AI服务测试
      api.ai.testStreamConnection({ url: url, type: 'rtmp', camera_id: cameraId.value || 'test' })
        .then(() => resolveOnce(true))
        .catch(() => resolveOnce(false))
    } else {
      // HTTP URL通过fetch测试
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), timeout - 100)
      
      fetch(url, { 
        method: 'HEAD',
        signal: controller.signal,
        mode: 'no-cors'
      })
      .then(() => {
        clearTimeout(timeoutId)
        resolveOnce(true)
      })
      .catch(() => {
        clearTimeout(timeoutId)
        resolveOnce(false)
      })
    }
  })
}

// 测试流连接性（保留原函数供其他地方使用）
const testStreamConnectivity = async (url) => {
  return new Promise((resolve) => {
    const timeout = 5000 // 5秒超时
    let resolved = false
    
    const resolveOnce = (result) => {
      if (!resolved) {
        resolved = true
        resolve(result)
      }
    }
    
    try {
      if (url.toLowerCase().includes('rtmp://')) {
        // RTMP流通过AI服务测试
        api.ai.testStreamConnection({ url: url, type: 'rtmp', camera_id: cameraId.value || 'test' })
          .then(() => resolveOnce({ success: true }))
          .catch((error) => resolveOnce({ success: false, error: error.message }))
      } else if (url.toLowerCase().includes('http')) {
        // HTTP/HLS流通过fetch测试
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), timeout)
        
        fetch(url, { 
          method: 'HEAD',
          signal: controller.signal,
          mode: 'no-cors' // 避免CORS问题
        })
        .then(() => {
          clearTimeout(timeoutId)
          resolveOnce({ success: true })
        })
        .catch((error) => {
          clearTimeout(timeoutId)
          resolveOnce({ success: false, error: error.message })
        })
      } else {
        // RTSP或其他协议，返回假设成功
        resolveOnce({ success: true })
      }
      
      // 超时处理
      setTimeout(() => {
        resolveOnce({ success: false, error: '连接测试超时' })
      }, timeout)
      
    } catch (error) {
      resolveOnce({ success: false, error: error.message })
    }
  })
}

// 处理AI检测结果
const handleDetectionResults = (detections) => {
  console.log('🎯 处理AI检测结果:', detections)
  updateDetectionResults(detections)
  
  // 确保AIAnalyzer组件立即更新绘制
  if (aiAnalyzer.value) {
    nextTick(() => {
      console.log('🎨 触发重绘检测框')
      aiAnalyzer.value.drawDangerZones()
    })
  }
}

// 处理性能统计
const handlePerformanceStats = (stats) => {
  performanceStats.value = {
    ...performanceStats.value,
    ...stats
  }
}

// 测试AI服务连接
const testAIConnection = async () => {
  try {
    console.log('🔍 测试AI服务连接...')
    ElMessage.info('正在测试AI服务连接...')
    
    const response = await api.ai.getSystemStatus()
    console.log('🔍 AI服务状态响应:', response)
    
    if (response && (response.status === 'healthy' || response.status === 'running')) {
      ElMessage.success('AI服务连接正常')
      console.log('✅ AI服务状态正常')
    } else {
      ElMessage.warning('AI服务状态异常: ' + JSON.stringify(response))
      console.warn('⚠️ AI服务状态异常:', response)
    }
  } catch (error) {
    console.error('❌ AI服务连接测试失败:', error)
    ElMessage.error('AI服务连接失败: ' + error.message)
  }
}
</script>