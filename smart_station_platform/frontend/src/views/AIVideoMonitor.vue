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
                :type="localTrackingEnabled ? 'success' : 'info'"
                @click="toggleLocalTracking"
                size="small"
              >
                {{ localTrackingEnabled ? '本地跟踪已开启' : '启用本地跟踪' }}
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
                <div v-else class="video-player-wrapper" ref="videoPlayerWrapper">
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
                    ref="playerContainer"
                    class="dplayer-container"
                    style="width:100%;height:100%;min-height:400px;display:block !important;"
                  >
                    <div ref="videoRef" class="dplayer-box" style="width:100%;height:100%;"></div>
                  </div>
                  
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
                
                <!-- 隐藏的播放器容器，确保videoRef始终存在 -->
                <div style="display: none;">
                  <div ref="fallbackVideoRef" class="dplayer-box-hidden"></div>
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

            <!-- 危险区域设置面板 -->
            <el-card class="zone-panel" shadow="never" v-if="isStreaming">
              <template #header>
                <div class="card-header">
                  <span>⚠️ 危险区域设置</span>
                  <el-badge :value="dangerZones.length" class="badge" />
                </div>
              </template>

              <div class="zone-controls">
                <div v-if="!isDrawingZone">
                  <el-button type="primary" @click="startDrawingZone" :disabled="!isStreaming">
                    <el-icon><Plus /></el-icon> 添加区域
                  </el-button>
                </div>
                <div v-else class="drawing-controls">
                  <el-input v-model="zoneName" placeholder="区域名称" size="small" class="zone-name-input" />
                  <el-color-picker v-model="zoneColor" size="small" />
                  <div class="zone-buttons">
                    <el-button type="success" @click="finishDrawingZone" :disabled="currentZonePoints.length < 3">
                      完成区域
                    </el-button>
                    <el-button @click="cancelDrawingZone">
                      取消绘制
                    </el-button>
                  </div>
                </div>
              </div>

              <el-divider v-if="dangerZones.length > 0">已设置区域</el-divider>

              <div class="zones-list">
                <div v-for="zone in dangerZones" :key="zone.id" class="zone-item">
                  <div class="zone-color" :style="{backgroundColor: zone.color}"></div>
                  <div class="zone-info">
                    <div class="zone-name">{{zone.name}}</div>
                    <div class="zone-points">{{zone.points.length}}个顶点</div>
                  </div>
                  <el-button link type="danger" @click="deleteZone(zone.id)" class="zone-delete">
                    删除
                  </el-button>
                </div>
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

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useApi } from '@/api'
import { useWebSocket } from '@/composables/useWebSocket'
import AIAnalyzer from '@/components/AIAnalyzer.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, Cpu, VideoCamera, Plus, Search, Warning } from '@element-plus/icons-vue'
import flvjs from 'flv.js'
import DPlayer from 'dplayer'

// 初始化API服务
const api = useApi()

// 视频相关引用
const videoElement = ref(null)
const videoRef = ref(null)
const playerContainer = ref(null)
const videoPlayerWrapper = ref(null)
const aiAnalyzer = ref(null)
const video = ref(null)
const player = ref(null)
const isStreaming = ref(false)

// 视频源设置
const videoSource = ref('rtmp')
const streamUrl = ref('')
const selectedDeviceId = ref('')
const videoDevices = ref([])
const cameraId = ref(`camera_${Date.now()}`)

// AI分析设置
const aiAnalysisEnabled = ref(false)
const localTrackingEnabled = ref(false)
const aiSettings = reactive({
  faceRecognition: true,
  objectDetection: true,
  behaviorAnalysis: false,
  soundDetection: false,
  fireDetection: true,
  realtimeMode: true
})

// 检测结果和性能统计
const detectionResults = ref([])
const performanceStats = ref({
  fps: 0,
  avgProcessTime: 0,
  processedFrames: 0,
  skippedFrames: 0,
  errorCount: 0
})

// 实时告警列表
const realtimeAlerts = ref([])

// 危险区域设置
const dangerZones = ref([])
const currentZonePoints = ref([])
const isDrawingZone = ref(false)
const zoneColor = ref('#dc2626')
const zoneName = ref('危险区域')

// WebSocket连接
const wsUrl = import.meta.env.VITE_APP_WS_URL || 'ws://localhost:8000/ws/alerts/'
const {
  isConnected: wsConnected,
  connect: connectWebSocket,
  disconnect: disconnectWebSocket,
  messages: wsMessages
} = useWebSocket(`${wsUrl}${cameraId.value}/`)

// 监听WebSocket消息
watch(wsMessages, (newMessages) => {
  if (newMessages.length > 0) {
    const latestMessage = newMessages[newMessages.length - 1]

    // 处理不同类型的WebSocket消息
    if (latestMessage.type === 'detection') {
      // 更新检测结果
      detectionResults.value = latestMessage.detections || []
    } else if (latestMessage.type === 'alert') {
      // 添加到实时告警列表
      if (latestMessage.alert) {
        realtimeAlerts.value.push({
          id: `alert_${Date.now()}`,
          type: latestMessage.alert.type || 'warning',
          title: latestMessage.alert.title || '异常事件告警',
          description: latestMessage.message || latestMessage.alert.description || '检测到异常事件',
          timestamp: new Date()
        });

        // 限制告警数量，保持最新的20条
        if (realtimeAlerts.value.length > 20) {
          realtimeAlerts.value = realtimeAlerts.value.slice(-20);
        }
      }

      // 显示告警通知
      ElMessage({
        type: 'warning',
        message: latestMessage.message || '检测到异常事件',
        duration: 5000
      })
    }
  }
})

// 计算属性：是否可以开始流
const canStartStream = computed(() => {
  if (videoSource.value === 'local') {
    return !!selectedDeviceId.value
  } else {
    return !!streamUrl.value.trim()
  }
})

// 获取流地址占位符
const getStreamPlaceholder = () => {
  switch (videoSource.value) {
    case 'rtsp':
      return 'rtsp://username:password@ip:port/stream'
    case 'rtmp':
      return 'rtmp://localhost:1935/live/stream'
    case 'hls':
      return 'http://localhost:8080/hls/stream.m3u8'
    case 'flv':
      return 'http://localhost:8080/live/stream.flv'
    case 'webrtc':
      return 'webrtc://localhost/live/stream'
    case 'mp4':
      return 'http://localhost:8080/video.mp4'
    default:
      return '请输入流地址'
  }
}

// 处理视频源类型变化
const handleVideoSourceChange = () => {
  streamUrl.value = ''

  if (videoSource.value === 'local') {
    // 获取可用的摄像头设备
    getVideoDevices()
  }
}

// 获取可用的视频设备
const getVideoDevices = async () => {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    videoDevices.value = devices.filter(device => device.kind === 'videoinput')
    
    if (videoDevices.value.length > 0 && !selectedDeviceId.value) {
      selectedDeviceId.value = videoDevices.value[0].deviceId
    }
  } catch (error) {
    console.error('获取视频设备失败:', error)
    ElMessage.error('无法访问摄像头设备，请检查浏览器权限设置')
  }
}

// 开始视频流
const startStream = async () => {
  try {
    if (videoSource.value === 'local') {
      // 本地摄像头
      await startLocalCamera()
    } else {
      // 网络流
      await startNetworkStream()
    }

    // 连接WebSocket
    connectWebSocket()

    // 标记为流媒体已启动
    isStreaming.value = true

    // 通知AI服务开始处理
    if (aiAnalysisEnabled.value) {
      await startAIAnalysis()
    }
  } catch (error) {
    console.error('启动视频流失败:', error)
    ElMessage.error('启动视频流失败: ' + (error.message || '未知错误'))
  }
}

// 启动本地摄像头
const startLocalCamera = async () => {
  try {
    const constraints = {
      video: {
        deviceId: selectedDeviceId.value ? { exact: selectedDeviceId.value } : undefined,
        width: { ideal: 1280 },
        height: { ideal: 720 }
      },
      audio: false
    }

    const stream = await navigator.mediaDevices.getUserMedia(constraints)

    if (videoElement.value) {
      videoElement.value.srcObject = stream
      video.value = videoElement.value

      // 等待视频加载
      await new Promise((resolve) => {
      videoElement.value.onloadedmetadata = () => {
          videoElement.value.play()
        resolve()
        }
      })

      ElMessage.success('本地摄像头启动成功')
    }
        } catch (error) {
    console.error('启动本地摄像头失败:', error)
    throw new Error('启动本地摄像头失败: ' + (error.message || '未知错误'))
  }
}

// 确保播放器容器初始化
const ensurePlayerContainer = () => {
  // 首先检查是否有通过ref获取的容器
  if (playerContainer.value) {
    console.log('通过ref找到播放器容器');
    return playerContainer.value;
  }
  
  // 其次，尝试通过DOM查询找到容器
  let container = document.querySelector('.dplayer-container');
  if (container) {
    console.log('通过DOM查询找到播放器容器');
    playerContainer.value = container; // 更新ref
    return container;
  }
  
  // 如果还找不到，尝试创建新容器
  console.warn('找不到播放器容器，尝试创建新容器');
  
  // 首先检查是否有视频播放区域
  const wrapper = videoPlayerWrapper.value || document.querySelector('.video-player-wrapper');
  if (!wrapper) {
    console.error('无法找到视频播放区域，无法创建播放器容器');
    throw new Error('无法找到视频播放区域');
  }
  
  // 清空现有内容
  wrapper.innerHTML = '';
  
  // 创建新的播放器容器
  container = document.createElement('div');
  container.className = 'dplayer-container';
  container.style.width = '100%';
  container.style.height = '100%';
  container.style.minHeight = '400px';
  container.style.display = 'block';
  container.style.position = 'relative';
  
  // 创建播放器盒子
  const box = document.createElement('div');
  box.className = 'dplayer-box';
  box.style.width = '100%';
  box.style.height = '100%';
  
  // 添加到DOM
  container.appendChild(box);
  wrapper.appendChild(container);
  
  // 更新引用
  playerContainer.value = container;
  videoRef.value = box;
  globalPlayerContainer = container;
  
  console.log('成功创建新的播放器容器');
  return container;
}

// 在startNetworkStream方法中调用
const startNetworkStream = async () => {
  if (!streamUrl.value) {
    throw new Error('请输入有效的流地址')
  }

  try {
    console.log(`开始连接网络流: ${streamUrl.value}, 类型: ${videoSource.value}`)
    
    // 测试流连接
    const isStreamAvailable = await testStreamConnection()
    
    if (!isStreamAvailable) {
      throw new Error('无法连接到视频流，请检查流地址是否正确')
    }

    console.log('流连接测试成功，准备创建播放器')
    
    // 确保视频容器已渲染
    await nextTick()
    
    // 确保播放器容器初始化
    try {
      const container = ensurePlayerContainer()
      console.log('播放器容器已准备就绪:', container)
    } catch (error) {
      console.error('初始化播放器容器失败:', error)
      throw new Error('初始化播放器容器失败: ' + error.message)
    }
    
    // 创建播放器
    try {
      // 首先尝试使用DPlayer
      console.log('尝试使用DPlayer创建播放器')
      await createPlayer()
      console.log('DPlayer创建成功')
      ElMessage.success('网络流连接成功')
    } catch (dplayerError) {
      console.warn('DPlayer创建失败，尝试使用原生flv.js:', dplayerError)
      
      // 如果是RTMP或FLV流，尝试使用原生flv.js
      if (['rtmp', 'flv'].includes(videoSource.value)) {
        try {
          // 确保DOM已更新
          await nextTick()
          
          console.log('尝试使用原生flv.js创建播放器')
          await createFlvPlayer()
          console.log('flv.js播放器创建成功')
          ElMessage.success('使用原生flv.js播放器连接成功')
        } catch (flvError) {
          console.error('原生flv.js播放器也失败:', flvError)
          
          // 最后尝试直接创建video元素
          try {
            console.log('尝试直接创建video元素播放')
            await createNativeVideoPlayer()
            console.log('原生video元素播放器创建成功')
            ElMessage.success('使用原生video元素连接成功')
          } catch (videoError) {
            console.error('所有播放方式都失败:', videoError)
            throw new Error('无法初始化播放器: ' + videoError.message)
          }
        }
      } else {
        // 其他类型的流，直接抛出原始错误
        throw dplayerError
      }
    }
    
    return true
  } catch (error) {
    console.error('启动网络流失败:', error)
    throw error
  }
}

// 测试流连接
const testStreamConnection = async () => {
  try {
    ElMessage.info('正在测试流连接...')
    const response = await api.ai.testStream(streamUrl.value, videoSource.value)
    
    if (response && response.status === 'success') {
      ElMessage.success('流连接测试成功')
      return true // 流可用时返回 true
    } else {
      ElMessage.warning(response?.message || '流连接测试失败')
      return false // 流不可用时返回 false
    }
  } catch (error) {
    console.error('流连接测试失败:', error)
    ElMessage.error('流连接测试失败: ' + (error.message || '未知错误'))
    return false // 出错时返回 false
  }
}

// 创建播放器
const createPlayer = async () => {
  if (player.value) {
    player.value.destroy()
    player.value = null
  }

  return new Promise((resolve, reject) => {
    nextTick(() => {
      try {
        // 确保容器元素已经渲染
        let container;
        try {
          container = ensurePlayerContainer();
        } catch (error) {
          console.error('获取播放器容器失败:', error);
          reject(new Error('获取播放器容器失败: ' + error.message));
          return;
        }

        if (!container) {
          console.error('播放器容器不存在');
          reject(new Error('播放器容器不存在'));
          return;
        }

        // 清空容器
        container.innerHTML = '';
        
        // 创建新的div作为DPlayer容器
        const playerBox = document.createElement('div');
        playerBox.className = 'dplayer-box';
        playerBox.style.width = '100%';
        playerBox.style.height = '100%';
        container.appendChild(playerBox);
        
        // 更新引用
        videoRef.value = playerBox;

        console.log('创建播放器，容器元素:', playerBox);
        
        // 根据流类型选择不同的播放器配置
        const playerOptions = {
          container: playerBox,
          autoplay: true,
          theme: '#42b883',
          loop: false,
          lang: 'zh-cn',
          screenshot: false,
          hotkey: true,
          preload: 'auto',
          volume: 0.7,
          mutex: true,
          video: {
            url: streamUrl.value,
            type: getVideoType(),
            customType: {
              flv: function(video, player) {
                if (flvjs.isSupported()) {
                  const flvPlayer = flvjs.createPlayer({
                    type: 'flv',
                    url: video.src,
                    isLive: true  // 添加这个参数表明是直播流
                  })
                  flvPlayer.attachMediaElement(video)
                  flvPlayer.load()
                }
              }
            }
          }
        }

        // 创建播放器实例
        console.log('初始化DPlayer，配置:', playerOptions);
        player.value = new DPlayer(playerOptions);

        // 监听播放器事件
        player.value.on('loadedmetadata', () => {
          console.log('DPlayer loadedmetadata 事件触发');
          video.value = player.value.video;
          resolve();
        });

        player.value.on('error', (error) => {
          console.error('播放器错误:', error);
          reject(new Error('播放器加载失败: ' + error));
        });

        // 5秒后如果还没有加载完成，也认为成功（某些流可能不会触发loadedmetadata事件）
        setTimeout(() => {
          if (player.value && player.value.video) {
            console.log('DPlayer 5秒超时，但播放器已创建，视为成功');
            video.value = player.value.video;
            resolve();
          } else {
            console.warn('DPlayer 5秒超时，播放器未就绪');
            reject(new Error('播放器加载超时'));
          }
        }, 5000);
      } catch (error) {
        console.error('创建播放器失败:', error);
        reject(new Error('创建播放器失败: ' + (error.message || '未知错误')));
      }
    });
  });
}

// 使用原生flv.js创建播放器（备用方法）
const createFlvPlayer = async () => {
  if (!flvjs.isSupported()) {
    throw new Error('当前浏览器不支持FLV.js，无法播放RTMP/FLV流');
  }
  
  // 获取播放器容器
  let container;
  try {
    container = ensurePlayerContainer();
  } catch (error) {
    console.error('获取播放器容器失败:', error);
    throw new Error('获取播放器容器失败: ' + error.message);
  }
  
  if (!container) {
    console.error('找不到播放器容器');
    throw new Error('找不到播放器容器');
  }
  
  // 清空容器
  container.innerHTML = '';
  console.log('找到播放器容器:', container);
  
  // 创建video元素
  const videoElement = document.createElement('video');
  videoElement.className = 'video-element';
  videoElement.controls = true;
  videoElement.autoplay = true;
  videoElement.muted = false;
  videoElement.style.width = '100%';
  videoElement.style.height = '100%';
  
  // 添加到容器
  container.appendChild(videoElement);
  console.log('已创建video元素并添加到容器');
  
  // 创建flv播放器
  console.log('初始化flv.js播放器, 流地址:', streamUrl.value);
  const flvPlayer = flvjs.createPlayer({
    type: 'flv',
    url: streamUrl.value,
    isLive: true,
    hasAudio: true,
    hasVideo: true
  });
  
  // 保存flv.js实例到video元素，方便后续清理
  videoElement._flvjs = flvPlayer;
  
  flvPlayer.attachMediaElement(videoElement);
  flvPlayer.load();
  flvPlayer.play();
  
  // 返回promise
  return new Promise((resolve, reject) => {
    videoElement.addEventListener('loadedmetadata', () => {
      console.log('flv.js loadedmetadata 事件触发');
      video.value = videoElement;
      resolve(flvPlayer);
    });
    
    videoElement.addEventListener('error', (e) => {
      console.error('flv.js播放器错误:', e);
      reject(new Error('FLV播放器加载失败: ' + e));
    });
    
    // 5秒后如果还没有加载完成，也认为成功（某些流可能不会触发loadedmetadata事件）
    setTimeout(() => {
      if (videoElement.readyState > 0) {
        console.log('flv.js 5秒超时，但视频元素已创建，视为成功');
        video.value = videoElement;
        resolve(flvPlayer);
      } else {
        console.warn('flv.js 5秒超时，视频元素未就绪');
        reject(new Error('FLV播放器加载超时'));
      }
    }, 5000);
  });
}

// 创建原生video元素播放器（备用方法）
const createNativeVideoPlayer = async () => {
  // 获取播放器容器
  let container;
  try {
    container = ensurePlayerContainer();
  } catch (error) {
    console.error('获取播放器容器失败:', error);
    throw new Error('获取播放器容器失败: ' + error.message);
  }
  
  if (!container) {
    console.error('找不到播放器容器');
    throw new Error('找不到播放器容器');
  }

  // 清空容器
  container.innerHTML = '';
  console.log('找到播放器容器:', container);
  
  const videoEl = document.createElement('video');
  videoEl.className = 'video-element';
  videoEl.controls = true;
  videoEl.autoplay = true;
  videoEl.src = streamUrl.value;
  videoEl.style.width = '100%';
  videoEl.style.height = '100%';
  container.appendChild(videoEl);

  return new Promise((resolve, reject) => {
    videoEl.addEventListener('loadedmetadata', () => {
      console.log('原生video元素加载成功');
      video.value = videoEl;
      resolve();
    });

    videoEl.addEventListener('error', (e) => {
      console.error('原生video元素加载失败:', e);
      reject(new Error('视频加载失败'));
    });

    // 5秒后如果还没有加载完成，也认为成功
    setTimeout(() => {
      if (videoEl.readyState > 0) {
        console.log('原生video元素5秒超时，但已创建，视为成功');
        video.value = videoEl;
        resolve();
      } else {
        console.warn('原生video元素5秒超时，未就绪');
        reject(new Error('视频加载超时'));
      }
    }, 5000);
  });
}

// 获取视频类型
const getVideoType = () => {
  switch (videoSource.value) {
    case 'rtmp':
      return 'customFlv'  // RTMP 流需要使用 flv.js 处理
    case 'flv':
      return 'customFlv'
    case 'hls':
      return 'hls'
    case 'mp4':
      return 'auto'
    default:
      return 'auto'
  }
}

// 停止视频流
const stopStream = async () => {
  try {
    // 停止AI分析
    if (aiAnalysisEnabled.value) {
      await stopAIAnalysis()
    }

    // 断开WebSocket连接
    disconnectWebSocket()

    // 停止本地摄像头
    if (videoSource.value === 'local' && videoElement.value && videoElement.value.srcObject) {
      const tracks = videoElement.value.srcObject.getTracks()
      tracks.forEach(track => track.stop())
      videoElement.value.srcObject = null
    }

    // 销毁播放器
    if (player.value) {
      // 检查是否有DPlayer实例
      player.value.destroy()
      player.value = null
    } else if (video.value) {
      // 检查是否有原生flv.js播放器
      const flvPlayer = video.value._flvjs
      if (flvPlayer) {
        flvPlayer.pause()
        flvPlayer.unload()
        flvPlayer.detachMediaElement()
        flvPlayer.destroy()
      }
      
      // 清理video元素
      if (videoRef.value) {
        videoRef.value.innerHTML = ''
      }
    }

    // 重置视频引用
    video.value = null

    // 标记为流媒体已停止
    isStreaming.value = false

    // 重置检测结果
    detectionResults.value = []

    ElMessage.success('视频流已停止')
  } catch (error) {
    console.error('停止视频流失败:', error)
    ElMessage.error('停止视频流失败: ' + (error.message || '未知错误'))
  }
}

// 启动AI分析
const startAIAnalysis = async () => {
  try {
    // 通知AI服务开始处理
    const response = await api.ai.startStream({
      camera_id: cameraId.value,
      stream_url: videoSource.value === 'local' ? 'webcam://' + selectedDeviceId.value : streamUrl.value,
      enable_face_recognition: aiSettings.faceRecognition,
      enable_object_detection: aiSettings.objectDetection,
      enable_behavior_detection: aiSettings.behaviorAnalysis,
      enable_fire_detection: aiSettings.fireDetection
    })

    if (response && response.status === 'success') {
      aiAnalysisEnabled.value = true
      ElMessage.success('AI分析已启动')
    } else {
      throw new Error(response?.message || 'AI分析启动失败')
    }
  } catch (error) {
    console.error('启动AI分析失败:', error)
    ElMessage.error('启动AI分析失败: ' + (error.message || '未知错误'))
    aiAnalysisEnabled.value = false
  }
}

// 停止AI分析
const stopAIAnalysis = async () => {
  try {
    // 通知AI服务停止处理
    const response = await api.ai.stopStream(cameraId.value)

    if (response && response.status === 'success') {
      ElMessage.success('AI分析已停止')
    } else {
      console.warn('AI分析停止响应异常:', response)
    }
  } catch (error) {
    console.error('停止AI分析失败:', error)
    ElMessage.warning('停止AI分析失败，但视频流已关闭')
  } finally {
    aiAnalysisEnabled.value = false
  }
}

// 切换AI分析状态
const toggleAIAnalysis = async () => {
  if (aiAnalysisEnabled.value) {
    await stopAIAnalysis()
  } else {
    await startAIAnalysis()
  }
}

// 更新AI设置
const updateAISettings = async () => {
  if (!aiAnalysisEnabled.value || !isStreaming.value) return

  try {
    const response = await api.ai.updateSettings(cameraId.value, aiSettings)
    if (response && response.status === 'success') {
      ElMessage.success('AI设置已更新')
    } else {
      console.warn('更新AI设置响应异常:', response)
    }
  } catch (error) {
    console.error('更新AI设置失败:', error)
    ElMessage.error('更新AI设置失败: ' + (error.message || '未知错误'))
  }
}

// 切换本地跟踪状态
const toggleLocalTracking = () => {
  localTrackingEnabled.value = !localTrackingEnabled.value

        if (aiAnalyzer.value) {
        nextTick(() => {
      ElMessage.info(localTrackingEnabled.value ? '本地跟踪已启用' : '本地跟踪已禁用')
    })
  }
}



// 处理视频加载事件
const onVideoLoaded = () => {
  if (videoElement.value) {
    console.log('视频已加载:', {
      width: videoElement.value.videoWidth,
      height: videoElement.value.videoHeight
    })
  }
}

// 处理检测结果
const handleDetectionResults = (results) => {
  detectionResults.value = results.detections || []
}

// 处理性能统计
const handlePerformanceStats = (stats) => {
  performanceStats.value = stats
}

// 处理Canvas点击
const handleCanvasClick = (event) => {
  if (isDrawingZone.value) {
    // 添加点到当前区域
    currentZonePoints.value.push({
      x: event.x,
      y: event.y
    })

    ElMessage.info(`已添加点 (${event.x.toFixed(2)}, ${event.y.toFixed(2)})`)
  }
}

// 开始绘制区域
const startDrawingZone = () => {
  isDrawingZone.value = true
  currentZonePoints.value = []
  ElMessage.info('请在视频上点击添加区域顶点，完成后点击"完成区域"')
}

// 完成区域绘制
const finishDrawingZone = () => {
  if (currentZonePoints.value.length < 3) {
    ElMessage.warning('请至少添加3个点以形成有效区域')
    return
  }

  // 添加新区域
  dangerZones.value.push({
    id: `zone_${Date.now()}`,
    name: zoneName.value,
    color: zoneColor.value,
    points: [...currentZonePoints.value]
  })
  
  // 重置当前绘制状态
  isDrawingZone.value = false
  currentZonePoints.value = []

  ElMessage.success('危险区域已添加')
}

// 取消区域绘制
const cancelDrawingZone = () => {
  isDrawingZone.value = false
  currentZonePoints.value = []
  ElMessage.info('已取消区域绘制')
}

// 从告警列表中移除告警
const removeAlert = (index) => {
  if (index >= 0 && index < realtimeAlerts.value.length) {
    realtimeAlerts.value.splice(index, 1)
  }
}

// 删除区域
const deleteZone = (zoneId) => {
  ElMessageBox.confirm('确定要删除此区域吗?', '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    dangerZones.value = dangerZones.value.filter(zone => zone.id !== zoneId)
    ElMessage.success('区域已删除')
  }).catch(() => {})
}

// 获取告警图标
const getAlertIcon = (type) => {
  const iconMap = {
    danger: '⚠️',
    warning: '⚠️',
    info: 'ℹ️',
    success: '✅',
    error: '❌',
    fire: '🔥',
    person: '👤',
    face: '👤',
    sound: '🔊',
    behavior: '🏃',
    default: '⚡'
  }
  return iconMap[type] || iconMap.default
}

// 获取检测图标
const getDetectionIcon = (type) => {
  const iconMap = {
    person: '👤',
    face: '👤',
    face_unknown: '👤',
    car: '🚗',
    truck: '🚚',
    bicycle: '🚲',
    motorcycle: '🏍️',
    bus: '🚌',
    fire: '🔥',
    smoke: '💨',
    default: '📦'
  }
  return iconMap[type] || iconMap.default
}

// 格式化时间
const formatTime = (timestamp) => {
  if (!timestamp) return ''
  
  const date = new Date(timestamp)
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const seconds = date.getSeconds().toString().padStart(2, '0')
  
  return `${hours}:${minutes}:${seconds}`
}

// 全局变量，用于在任何情况下都能找到播放器容器
let globalPlayerContainer = null

// 组件挂载时初始化
onMounted(() => {
  // 检查flv.js支持
  if (flvjs.isSupported()) {
    console.log('flv.js 支持已检测到')
  } else {
    console.warn('flv.js 不受支持，RTMP和FLV流可能无法播放')
  }
  
  // 获取可用的视频设备
  if (videoSource.value === 'local') {
    getVideoDevices()
  }
  
  // 测试AI服务连接
  api.ai.testConnection().then(response => {
    console.log('AI服务连接测试成功:', response)
  }).catch(error => {
    console.warn('AI服务连接初始化测试失败:', error)
  })

  // 连接WebSocket
  if (import.meta.env.VITE_APP_ENABLE_WS !== 'false') {
    connectWebSocket()
  }
  
  // 初始化全局播放器容器引用
  nextTick(() => {
    // 确保播放器容器引用始终存在
    try {
      // 如果videoPlayerWrapper已渲染，则初始化播放器容器
      if (videoPlayerWrapper.value) {
        const container = ensurePlayerContainer();
        console.log('全局播放器容器引用已初始化:', container);
      } else {
        console.log('视频播放区域尚未渲染，将在需要时初始化播放器容器');
      }
    } catch (error) {
      console.warn('初始化播放器容器失败，将在需要时重试:', error);
    }
  })
})

// 组件卸载时清理资源
onUnmounted(() => {
  // 停止流媒体播放
  if (isStreaming.value) {
    stopStream()
  }
  
  // 断开WebSocket连接
  disconnectWebSocket()
  
  // 清理播放器实例
  if (player.value) {
    try {
      player.value.destroy()
      player.value = null
    } catch (error) {
      console.warn('清理播放器实例失败:', error)
    }
  }
  
  // 清理视频元素
  if (video.value) {
    try {
      if (video.value._flvjs) {
        video.value._flvjs.unload()
        video.value._flvjs.detachMediaElement()
        video.value._flvjs.destroy()
      }
      video.value.src = ''
      video.value = null
    } catch (error) {
      console.warn('清理视频元素失败:', error)
    }
  }
  
  // 清理全局引用
  globalPlayerContainer = null
})
</script>

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
  min-height: 400px;
  background-color: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 4px;
}

.video-element {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* 确保播放器容器在所有情况下都正确显示 */
.video-player-wrapper:empty::before {
  content: "准备播放视频...";
  color: #fff;
  font-size: 16px;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.dplayer-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 400px;
  display: block !important; /* 确保始终可见 */
  z-index: 1;
  background-color: #000;
}

.dplayer-box {
  width: 100%;
  height: 100%;
}

.dplayer-box-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
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

/* DPlayer 相关样式 */
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

/* 控制面板样式 */
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

/* 检测结果列表样式 */
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

.detection-details, .detection-time {
  font-size: 12px;
  color: #909399;
}

.no-results {
  text-align: center;
  padding: 20px;
  color: #909399;
}

/* 告警面板样式 */
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

/* 告警类型样式 */
.alert-danger { border-left-color: #f56c6c; background-color: #fef0f0; }
.alert-warning { border-left-color: #e6a23c; background-color: #fdf6ec; }
.alert-info { border-left-color: #409eff; background-color: #ecf5ff; }
.alert-success { border-left-color: #67c23a; background-color: #f0f9ff; }

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

/* 危险区域设置面板样式 */
.zone-panel {
  margin-bottom: 20px;
}

.zone-controls {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 10px;
}

.drawing-controls {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 6px;
}

.zone-name-input {
  margin-bottom: 8px;
}

.zone-buttons {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}

.zones-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.zone-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 6px;
  background-color: #f8f9fa;
  border: 1px solid #ebeef5;
}

.zone-color {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  margin-right: 10px;
  flex-shrink: 0;
}

.zone-info {
  flex: 1;
  margin-right: 10px;
}

.zone-name {
  font-weight: bold;
  font-size: 14px;
  color: #303133;
}

.zone-points {
  font-size: 12px;
  color: #909399;
}

.zone-delete {
  flex-shrink: 0;
}
</style>
