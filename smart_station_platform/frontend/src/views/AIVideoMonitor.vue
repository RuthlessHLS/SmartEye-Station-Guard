<template>
  <div class="video-monitor">
    <el-container>
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

              <div class="video-container">
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

                    <el-form-item v-if="videoSource !== 'local'" label="流地址">
                      <el-input
                        v-model="rawInputStreamUrl" :placeholder="getStreamPlaceholder()"
                        clearable
                      >
                        <template #append>
                          <el-button @click="testStreamConnection" :disabled="!rawInputStreamUrl.trim()">测试连接</el-button> </template>
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

                <div v-else class="video-player-wrapper">
                  <video
                    v-if="videoSource === 'local'"
                    ref="videoElement"
                    class="video-element"
                    autoplay
                    muted
                    playsinline
                    @loadedmetadata="onVideoLoaded"
                  ></video>

                  <div
                    v-else
                    ref="videoRef"
                    class="dplayer-container"
                  ></div>

                  <AIAnalyzer
                    v-if="isStreaming"
                    ref="aiAnalyzer"
                    :video="video"
                    :camera-id="cameraId"
                    :enabled="aiAnalysisEnabled"
                    :local-tracking-enabled="localTrackingEnabled"
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

          <el-col :span="8">
            <el-card class="control-panel" shadow="never">
              <template #header>
                <span>🎯 AI分析设置</span>
              </template>

              <div class="analysis-settings">
                <el-form label-width="100px">
                  <el-form-item label="人脸识别">
                    <el-switch
                      v-model="aiSettings.faceRecognition"
                      :disabled="!isStreaming || !aiAnalysisEnabled"
                      @change="() => updateAISettings('faceRecognition')"
                    />
                    <div class="setting-description">
                      识别视频中的人脸，并与已知人脸库进行匹配。可用于访客识别和权限控制。
                    </div>
                  </el-form-item>
                  <el-form-item label="目标检测">
                    <el-switch
                      v-model="aiSettings.objectDetection"
                      :disabled="!isStreaming || !aiAnalysisEnabled"
                      @change="() => updateAISettings('objectDetection')"
                    />
                    <div class="setting-description">
                      检测视频中的人员、车辆、包裹等常见目标，支持多目标同时跟踪。
                    </div>
                  </el-form-item>
                  <el-form-item label="行为分析">
                    <el-switch
                      v-model="aiSettings.behaviorAnalysis"
                      :disabled="!isStreaming || !aiAnalysisEnabled"
                      @change="() => updateAISettings('behaviorAnalysis')"
                    />
                    <div class="setting-description">
                      分析人员行为，如跌倒、奔跑、聚集等异常行为，及时发出预警。
                    </div>
                  </el-form-item>
                  <el-form-item label="声音检测">
                    <el-switch
                      v-model="aiSettings.soundDetection"
                      :disabled="!isStreaming || !aiAnalysisEnabled"
                      @change="() => updateAISettings('soundDetection')"
                    />
                    <div class="setting-description">
                      监测环境声音，检测异常噪音、尖叫等声音事件，提供声音告警。
                    </div>
                  </el-form-item>
                  <el-form-item label="火焰检测">
                    <el-switch
                      v-model="aiSettings.fireDetection"
                      :disabled="!isStreaming || !aiAnalysisEnabled"
                      @change="() => updateAISettings('fireDetection')"
                    />
                    <div class="setting-description">
                      检测视频中的火焰和烟雾，用于及早发现火灾隐患，保障安全。
                    </div>
                  </el-form-item>
                  <el-form-item label="实时模式">
                    <el-switch
                      v-model="aiSettings.realtimeMode"
                      :disabled="!isStreaming || !aiAnalysisEnabled"
                      active-text="高频检测"
                      inactive-text="节能模式"
                      @change="() => updateAISettings('realtimeMode')"
                    />
                    <div class="setting-description">
                      高频检测模式下可达到15FPS的检测速率，但会增加系统负载；节能模式下智能调节检测频率，平衡性能和效果。
                    </div>
                  </el-form-item>
                </el-form>
              </div>
            </el-card>

            <el-card class="results-panel" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>🔍 检测结果</span>
                  <el-badge :value="detectionResults?.length || 0" class="badge" />
                </div>
              </template>

              <el-scrollbar height="300px">
                <div class="detection-list">
                  <div
                    v-for="(result, index) in detectionResults || []"
                    :key="`${result.tracking_id || result.type}_${index}`"
                    class="detection-item"
                    :class="`type-${result.type}`"
                  >
                    <div class="detection-icon">
                      {{ getDetectionIcon(result.type) }}
                    </div>
                    <div class="detection-info">
                      <div class="detection-name">
                        {{ result.identity ? (result.identity.name || '未知人员') : result.class_name }}
                      </div>
                      <div class="detection-details">
                        置信度: {{ (result.confidence * 100).toFixed(1) }}%
                      </div>
                      <div class="detection-time">
                        {{ formatTime(result.timestamp) }}
                      </div>
                    </div>
                  </div>

                  <div v-if="(detectionResults || []).length === 0" class="no-results">
                    <el-icon><Search /></el-icon>
                    <p>暂无检测结果</p>
                  </div>
                </div>
              </el-scrollbar>
            </el-card>

            <el-card class="alerts-panel" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>🚨 实时告警</span>
                  <el-badge :value="(realtimeAlerts || []).length" class="badge" :max="99" />
                </div>
              </template>

              <el-scrollbar height="250px">
                <div class="alerts-list">
                  <div
                    v-for="(alert, index) in realtimeAlerts || []"
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

                  <div v-if="(realtimeAlerts || []).length === 0" class="no-alerts">
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
import { ref, reactive, onMounted, onUnmounted, computed, nextTick, watch } from 'vue';
import { useApi } from '@/api';
import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'vue-router';
import AIAnalyzer from '@/components/AIAnalyzer.vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Close, Cpu, VideoCamera, Warning, Search, SuccessFilled, CircleCloseFilled } from '@element-plus/icons-vue';
import flvjs from 'flv.js';
import DPlayer from 'dplayer';
import Hls from 'hls.js';

// --- State and Refs ---
const api = useApi();
const router = useRouter();
const authStore = useAuthStore();
const videoElement = ref(null);
const videoRef = ref(null);
const aiAnalyzer = ref(null);
const video = ref(null);
const player = ref(null);
const isStreaming = ref(false);
const videoSource = ref('rtmp');
const rawInputStreamUrl = ref('');
const playbackUrl = ref('');
const selectedDeviceId = ref('');
const videoDevices = ref([]);
const cameraId = ref(`camera_${Date.now()}`);
const aiAnalysisEnabled = ref(false);
const localTrackingEnabled = ref(false);
const aiSettings = reactive({
  faceRecognition: true,
  objectDetection: true,
  behaviorAnalysis: false,
  soundDetection: false,
  fireDetection: true,
  realtimeMode: true,
});
const detectionResults = ref([]);
const performanceStats = ref({});
const realtimeAlerts = ref([]);
const dangerZones = ref([]);
const currentZonePoints = ref([]);
const isDrawingZone = ref(false);
const wsConnected = ref(false);
let ws = null;
const wsUrl = import.meta.env.VITE_APP_WS_URL || 'ws://localhost:8000/ws/alerts/';

// 【新增】一个可重用的函数来根据当前设置过滤检测结果
const filterResults = (results) => {
  if (!results || results.length === 0) {
    return [];
  }

  return results.filter(det => {
    const { type, class_name } = det;

    // 人脸识别
    if (type === 'face' || class_name === 'face') {
      return aiSettings.faceRecognition;
    }

    // 火焰/烟雾检测
    if (type === 'fire' || type === 'smoke' || class_name === 'fire' || class_name === 'smoke') {
      return aiSettings.fireDetection;
    }

    // 目标检测 (涵盖常见物体: 人员、车辆、包裹等)
    const objectTypes = ['person', 'car', 'bicycle', 'motorcycle', 'bus', 'truck', 'backpack', 'handbag', 'suitcase'];
    if (objectTypes.includes(type) || objectTypes.includes(class_name)) {
      return aiSettings.objectDetection;
    }

    // 行为分析和声音检测通常不会有独立的检测框，除非后端有特定实现
    // 默认情况下，如果类型不匹配任何受控类别，则显示
    return true;
  });
};


// --- WebSocket Logic ---
const disconnectWebSocket = () => {
  if (ws) {
    ws.onclose = null;
    ws.onerror = null;
    ws.onmessage = null;
    ws.onopen = null;
    ws.close();
    ws = null;
    wsConnected.value = false;
  }
};

const connectWebSocket = () => {
  disconnectWebSocket();

  const fullWsUrl = `${wsUrl}${cameraId.value}/`;
  console.log(`[WebSocket] 正在创建新的 WebSocket 连接: ${fullWsUrl}`);
  ws = new WebSocket(fullWsUrl);

  ws.onopen = () => {
    wsConnected.value = true;
    console.log('[WebSocket] ✅ 新的连接已建立！');
  };

  ws.onmessage = (event) => {
    console.log('[WebSocket] 📩 收到原始消息:', event.data);
    try {
      const messageData = JSON.parse(event.data);

      // 【修改点】确保这段逻辑存在且正确
      if (messageData.type === 'stream_initialized') {
        const resolution = messageData.data.resolution;
        console.log('[父组件] 收到视频流初始化消息，分辨率为:', resolution);
        if (aiAnalyzer.value && resolution) {
          // 调用子组件的方法来设置AI处理分辨率
          aiAnalyzer.value.setAiImageSize(resolution);
        }
      }
      // 保留您原有的其他消息处理逻辑
      else if (messageData.type === 'detection_result' && messageData.data && messageData.data.detections) {
        // 格式化检测结果
        let detections = [];
        if (Array.isArray(messageData.data.detections)) {
          detections = messageData.data.detections;
        } else if (messageData.data.detections.detections) {
          detections = messageData.data.detections.detections;
        } else {
          detections = Array.isArray(messageData.data.detections) ?
            messageData.data.detections : [messageData.data.detections];
        }

        // 【新增】从消息中获取时间戳
        const timestamp = messageData.data.timestamp || Date.now();
        const frameId = messageData.data.frame_id || `frame_${timestamp}`;

        // 【新增】记录当前视频时间
        const currentVideoTime = video.value ? video.value.currentTime : 0;

        // 【新增】将时间戳信息添加到检测结果中
        detections.forEach(detection => {
          detection.frame_timestamp = timestamp;
          detection.frame_id = frameId;
          detection.video_time = currentVideoTime;
        });

        console.log(`[检测结果] 收到数据 (帧ID: ${frameId}, 视频时间: ${currentVideoTime.toFixed(2)}s):`, detections);

        // 更新检测结果，并根据AI设置进行过滤
        detectionResults.value = filterResults(detections);

        // 强制重新渲染Canvas
        if (aiAnalyzer.value) {
          // 延迟执行，确保DOM已更新
          nextTick(() => {
            try {
              // 清空画布后重新渲染
              aiAnalyzer.value.clearCanvas();
              aiAnalyzer.value.renderDetections(detectionResults.value);

              // 【新增】在画布上显示时间戳和帧ID，并检查同步状态
              if (aiAnalyzer.value.drawTimestamp) {
                // 检查视频时间和检测结果时间是否匹配
                const videoTimeFromDetection = detections[0]?.video_time;
                const isSynchronized = videoTimeFromDetection ? Math.abs(currentVideoTime - videoTimeFromDetection) < 0.5 : true;
                const timeDifference = videoTimeFromDetection ? Math.abs(currentVideoTime - videoTimeFromDetection) : 0;

                aiAnalyzer.value.drawTimestamp(frameId, currentVideoTime, isSynchronized, timeDifference);
              }
            } catch (error) {
              console.error('[Canvas渲染错误]', error);
            }
          });
        }
      } else if (messageData.type === 'alert') {
        ElMessage({ type: 'warning', message: messageData.message || '检测到异常事件' });
        if (messageData.data) {
          realtimeAlerts.value.unshift({
            id: `alert_${Date.now()}`,
            type: messageData.alert_type || 'warning',
            title: messageData.message || '检测到异常事件',
            description: messageData.description || messageData.data.details || '请注意查看监控画面',
            timestamp: Date.now(),
          });
          if (realtimeAlerts.value.length > 20) {
            realtimeAlerts.value.pop();
          }
        }
      }
    } catch (error) {
      console.error('WebSocket 消息解析错误:', error);
    }
  };
  ws.onerror = (error) => console.error('WebSocket 发生错误:', error);
  ws.onclose = () => {
    wsConnected.value = false;
    ws = null;
  };
};
// --- Stream and Player Logic ---
const stopStream = async () => {
  if (aiAnalysisEnabled.value) {
    await stopAIAnalysis();
  }
  disconnectWebSocket();
  if (player.value) {
    player.value.destroy();
    player.value = null;
  }
  if (videoElement.value && videoElement.value.srcObject) {
    videoElement.value.srcObject.getTracks().forEach((track) => track.stop());
    videoElement.value.srcObject = null;
  }
  isStreaming.value = false;
  detectionResults.value = [];
};

const startStream = async () => {
  await stopStream();
  try {
    isStreaming.value = true;
    await nextTick();

    if (videoSource.value === 'local') {
      await startLocalCamera();
    } else {
      if (videoSource.value === 'rtmp') {
        const rtmpMatch = rawInputStreamUrl.value.match(/\/([a-zA-Z0-9_-]+)$/);
        if (!rtmpMatch || !rtmpMatch[1]) throw new Error('RTMP流地址格式不正确');
        playbackUrl.value = `http://localhost:8080/hls/${rtmpMatch[1]}.m3u8`;
      } else {
        playbackUrl.value = rawInputStreamUrl.value;
      }
      await startNetworkStream();
    }

    connectWebSocket();

    if (aiAnalysisEnabled.value) {
      await startAIAnalysis();
    }
  } catch (error) {
    ElMessage.error(`启动视频流失败: ${error.message}`);
    isStreaming.value = false;
  }
};

// --- 在组件挂载和更新时调用 ---

// 当视频流启动成功时，自动获取当前AI设置
watch(() => isStreaming.value, async (newValue) => {
  if (newValue) {
    // 视频流已启动，获取AI设置
    await fetchAISettings();
  }
});

// 当AI分析状态改变时，更新设置状态
watch(() => aiAnalysisEnabled.value, (newValue) => {
  if (!newValue) {
    // 如果AI分析已关闭，禁用所有设置
    console.log('[AI设置] AI分析已关闭，设置选项已禁用');
  } else {
    // 如果AI分析已开启，获取最新设置
    fetchAISettings();
  }
});

const startLocalCamera = async () => {
  const constraints = { video: { deviceId: { exact: selectedDeviceId.value }, width: 1280, height: 720 } };
  const stream = await navigator.mediaDevices.getUserMedia(constraints);
  if (videoElement.value) {
    videoElement.value.srcObject = stream;
    video.value = videoElement.value;
    videoElement.value.play();
  }
};

const startNetworkStream = async () => {
  await testStreamConnection();
  await createPlayer();
};

const testStreamConnection = async () => {
  try {
    const response = await api.ai.testStream(rawInputStreamUrl.value, videoSource.value);
    if (response?.status !== 'success') {
      throw new Error(response?.message || '无效的后端响应');
    }
  } catch (error) {
    handleApiError(error);
    throw error;
  }
};

const createPlayer = () => {
  if (player.value) player.value.destroy();
  if (!videoRef.value) throw new Error("播放器容器不存在");

  player.value = new DPlayer({
    container: videoRef.value,
    autoplay: true,
    video: {
      url: playbackUrl.value,
      type: getVideoType(),
      customType: {
        flv: (video) => {
          const flvPlayer = flvjs.createPlayer({ type: 'flv', url: video.src });
          flvPlayer.attachMediaElement(video);
          flvPlayer.load();
        },
        hls: (video) => {
          if (Hls.isSupported()) {
            const hls = new Hls();
            hls.loadSource(video.src);
            hls.attachMedia(video);
          } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            // eslint-disable-next-line no-self-assign
            video.src = video.src;
          }
        },
      },
    },
  });
  video.value = player.value.video;

  // 添加事件监听，确保视频加载后记录尺寸信息
  video.value.addEventListener('loadedmetadata', () => {
    console.log('[播放器] 视频元数据已加载，视频尺寸:', video.value.videoWidth, 'x', video.value.videoHeight);
    onVideoLoaded();
  });

  // 添加播放准备就绪事件
  player.value.on('playing', () => {
    console.log('[播放器] 视频开始播放');

    // 视频播放时多次尝试调整Canvas，确保能正确捕获视频尺寸
    // 第一次调整 - 立即调整
    if (aiAnalyzer.value && typeof aiAnalyzer.value.resizeCanvas === 'function') {
      console.log('[播放器] 视频播放开始，立即调整Canvas');
      aiAnalyzer.value.resizeCanvas();
    }

    // 第二次调整 - 300ms后，视频刚开始渲染
    setTimeout(() => {
      if (aiAnalyzer.value && typeof aiAnalyzer.value.resizeCanvas === 'function') {
        console.log('[播放器] 视频播放300ms后，再次调整Canvas');
        aiAnalyzer.value.resizeCanvas();
      }
    }, 300);

    // 第三次调整 - 1秒后，视频已完全渲染
    setTimeout(() => {
      if (aiAnalyzer.value && typeof aiAnalyzer.value.resizeCanvas === 'function') {
        console.log('[播放器] 视频播放1秒后，最终调整Canvas');
        aiAnalyzer.value.resizeCanvas();
      }
    }, 1000);

    // 第四次调整 - 3秒后，确保视频稳定后Canvas位置正确
    setTimeout(() => {
      if (aiAnalyzer.value && typeof aiAnalyzer.value.resizeCanvas === 'function') {
        console.log('[播放器] 视频播放3秒后，稳定性检查');
        aiAnalyzer.value.resizeCanvas();
      }
    }, 3000);
  });

  // 播放进度变化时再次检查Canvas尺寸
  player.value.on('timeupdate', () => {
    // 每10秒检查一次Canvas位置
    const currentTime = player.value.video.currentTime;
    if (currentTime > 0 && Math.floor(currentTime) % 10 === 0) {
      if (aiAnalyzer.value && typeof aiAnalyzer.value.resizeCanvas === 'function') {
        console.log(`[播放器] 播放进度${currentTime.toFixed(0)}秒，检查Canvas位置`);
        aiAnalyzer.value.resizeCanvas();
      }
    }
  });

  // 监听视频调整尺寸事件
  player.value.on('resize', () => {
    console.log('[播放器] 视频尺寸已调整');
    if (aiAnalyzer.value && typeof aiAnalyzer.value.resizeCanvas === 'function') {
      aiAnalyzer.value.resizeCanvas();
    }
  });

  // 监听全屏变化
  player.value.on('fullscreen', () => {
    console.log('[播放器] 视频全屏状态已变化');
    setTimeout(() => {
      if (aiAnalyzer.value && typeof aiAnalyzer.value.resizeCanvas === 'function') {
        aiAnalyzer.value.resizeCanvas();
      }
    }, 300);
  });

  console.log('[播放器] 播放器创建完成，当前视频元素:', video.value);
};

// --- AI Logic ---
// 新增：前端设置项到后端API参数的映射
const settingToApiMapping = {
  faceRecognition: 'enable_face_recognition',
  objectDetection: 'enable_object_detection',
  behaviorAnalysis: 'enable_behavior_detection',
  soundDetection: 'enable_sound_detection',
  fireDetection: 'enable_fire_detection',
  realtimeMode: 'realtime_mode'
};

    // 请将此函数复制，并替换掉 AIVideoMonitor.vue 中的同名函数

    const updateAISettings = async (settingName = '') => {
      // 确保 settingName 有效
      if (!settingName) return;

      // 【优化】实现乐观更新（Optimistic Update）
      // 1. 立即更新UI，不等网络响应
      // Vue的v-model已经同步更新了aiSettings的状态，所以我们可以立即过滤
      console.log(`[AI设置 - 乐观更新] 立即过滤 '${settingName}' 的检测框`);
      detectionResults.value = filterResults(detectionResults.value);

      // 记住更新前的状态，以便在API请求失败时回滚
      const previousValue = !aiSettings[settingName];

      try {
        const settingsPayload = {};
        const apiKey = settingToApiMapping[settingName];

        // 确保找到了对应的API key
        if (apiKey) {
          settingsPayload[apiKey] = aiSettings[settingName];
        } else {
          console.warn(`[AI设置] 未找到 '${settingName}' 的API映射`);
          return;
        }

        console.log('[AI设置] 正在向后端发送负载:', settingsPayload);
        const response = await api.ai.updateSettings(cameraId.value, settingsPayload);

        // 检查后端是否明确返回失败
        if (response?.status !== 'success') {
          throw new Error(response?.message || '后端更新明确失败');
        }

        // 2. 更新成功，后端状态与前端一致，显示成功消息
        ElMessage({
          message: `${translateSettingName(settingName)} 已${aiSettings[settingName] ? '启用' : '禁用'}`,
          type: 'success',
          duration: 2000
        });

      } catch (error) {
        // 3. 如果API请求失败，则回滚UI状态
        console.error(`[AI设置 - 乐观更新] 更新 '${settingName}' 失败，正在回滚UI...`);

        // a. 将开关的状态恢复到之前的值
        aiSettings[settingName] = previousValue;

        // b. 重新过滤检测框，恢复到之前的显示状态
        detectionResults.value = filterResults(detectionResults.value);

        // c. 向用户显示错误提示
        const errorMessage = error.response?.data?.detail || error.message || '未知错误';
        ElMessage.error(`更新失败，已恢复设置: ${errorMessage}`);
      }
    };
// 设置名称翻译函数
const translateSettingName = (settingName) => {
  const translations = {
    faceRecognition: '人脸识别',
    objectDetection: '目标检测',
    behaviorAnalysis: '行为分析',
    soundDetection: '声音检测',
    fireDetection: '火焰检测',
    realtimeMode: '实时模式'
  };
  return translations[settingName] || settingName;
};

// 获取当前AI设置的函数
const fetchAISettings = async () => {
  if (!cameraId.value || !isStreaming.value) return;

  try {
    const response = await api.ai.updateSettings(cameraId.value, {});
    if (response?.settings) {
      // 将后端返回的设置映射回前端格式
      const mappedSettings = {};
      const reverseMapping = {
        'face_recognition': 'faceRecognition',
        'object_detection': 'objectDetection',
        'behavior_analysis': 'behaviorAnalysis',
        'sound_detection': 'soundDetection',
        'fire_detection': 'fireDetection',
        'realtime_mode': 'realtimeMode'
      };

      Object.keys(response.settings).forEach(key => {
        const frontendKey = reverseMapping[key] || key;
        mappedSettings[frontendKey] = response.settings[key];
      });

      // 更新到本地状态
      Object.assign(aiSettings, mappedSettings);
      console.log('[AI设置] 已从服务器获取最新设置并映射:', mappedSettings);
    }
  } catch (error) {
    console.error('[AI设置] 获取设置失败:', error);
  }
};

const startAIAnalysis = async () => {
  try {
    const streamUrlForAI = (videoSource.value === 'local') ? `webcam://${selectedDeviceId.value}` : rawInputStreamUrl.value;
    const payload = {
      camera_id: cameraId.value,
      stream_url: streamUrlForAI,
      enable_face_recognition: aiSettings.faceRecognition,
      enable_object_detection: aiSettings.objectDetection,
      enable_behavior_detection: aiSettings.behaviorAnalysis,
      enable_sound_detection: aiSettings.soundDetection,
      enable_fire_detection: aiSettings.fireDetection,
      realtime_mode: aiSettings.realtimeMode, // 补全实时模式参数
    };
    const response = await api.ai.startStream(payload);
    if (response?.status !== 'success') {
      throw new Error(response?.message || response?.detail || 'AI分析启动失败');
    }

    // 启动成功后，获取最新设置
    aiAnalysisEnabled.value = true;
    await fetchAISettings();

  } catch (error) {
    const errorMessage = error.response?.data?.detail || error.message || '未知错误';
    ElMessage.error(`启动AI分析失败: ${errorMessage}`);
    aiAnalysisEnabled.value = false;
  }
};

const stopAIAnalysis = async () => {
  try {
    await api.ai.stopStream(cameraId.value);
  } catch (error) {
    handleApiError(error);
  } finally {
    aiAnalysisEnabled.value = false;
  }
};

const toggleAIAnalysis = async () => {
  if (aiAnalysisEnabled.value) {
    await stopAIAnalysis();
  } else {
    await startAIAnalysis();
  }
};

// 修改AI设置单项开关状态
const toggleAIFeature = (featureName) => {
  if (!isStreaming.value || !aiAnalysisEnabled.value) return;

  // 切换特定功能的状态
  aiSettings[featureName] = !aiSettings[featureName];

  // 更新设置到服务器
  updateAISettings(featureName);
};


// --- Helper Functions and Lifecycle ---
const canStartStream = computed(() => {
  if (videoSource.value === 'local') {
    return !!selectedDeviceId.value;
  }
  return !!rawInputStreamUrl.value.trim();
});

// 新增函数：记录视频元素信息
const logVideoElementInfo = () => {
  if (!video.value) {
    console.warn('[视频检查] 视频元素不存在');
    return;
  }

  const videoWidth = video.value.videoWidth;
  const videoHeight = video.value.videoHeight;
  console.log('[视频检查] 当前视频元素尺寸:', videoWidth, 'x', videoHeight);
  console.log('[视频检查] 当前Canvas尺寸:',
    aiAnalyzer.value ?
    `${aiAnalyzer.value.$el.querySelector('canvas').width} x ${aiAnalyzer.value.$el.querySelector('canvas').height}` :
    '无法获取Canvas尺寸');
};

const getStreamPlaceholder = () => {
  const placeholders = {
    rtsp: 'rtsp://username:password@ip:port/stream',
    rtmp: 'rtmp://localhost:1935/live/stream_name',
    hls: 'http://localhost:8080/hls/stream.m3u8',
    flv: 'http://localhost:8080/live/stream.flv',
    webrtc: 'webrtc://localhost/live/stream',
    mp4: 'http://localhost:8080/video.mp4',
  };
  return placeholders[videoSource.value] || '请输入流地址';
};

const handleVideoSourceChange = () => {
  rawInputStreamUrl.value = '';
  playbackUrl.value = '';
  if (videoSource.value === 'local') {
    getVideoDevices();
  }
};

const getVideoType = () => {
  if (playbackUrl.value.includes('.m3u8')) return 'hls';
  if (playbackUrl.value.includes('.flv')) return 'customFlv';
  return 'auto';
};

const toggleLocalTracking = () => {
  localTrackingEnabled.value = !localTrackingEnabled.value;
};

const onVideoLoaded = () => {
  if (!video.value) {
    console.warn('[视频] 视频元素尚未加载');
    return;
  }

  console.log('[视频] 视频已加载，当前尺寸:',
    `${video.value.videoWidth}x${video.value.videoHeight}`);

  // 如果AIAnalyzer组件已加载，通知其调整Canvas大小
  if (aiAnalyzer.value && typeof aiAnalyzer.value.resizeCanvas === 'function') {
    console.log('[视频] 通知AIAnalyzer调整Canvas尺寸');
    aiAnalyzer.value.resizeCanvas();

    // 如果已知视频原始分辨率，同时更新AI处理分辨率
    if (video.value.videoWidth && video.value.videoHeight) {
      aiAnalyzer.value.setAiImageSize({
        width: video.value.videoWidth,
        height: video.value.videoHeight
      });
    }
  }

  // 创建多次调整Canvas的计划，确保在不同加载阶段都能正确调整
  [100, 500, 1000, 3000].forEach(delay => {
    setTimeout(() => {
      if (aiAnalyzer.value && typeof aiAnalyzer.value.resizeCanvas === 'function') {
        console.log(`[视频] 视频加载后${delay}ms调整Canvas`);
        aiAnalyzer.value.resizeCanvas();
      }
    }, delay);
  });
};
const handleDetectionResults = (results) => {
  detectionResults.value = results?.detections || [];
};
const handlePerformanceStats = (stats) => {
  performanceStats.value = stats;
};
const handleCanvasClick = (event) => {
  if (isDrawingZone.value) {
    currentZonePoints.value.push({ x: event.x, y: event.y });
  }
};
const removeAlert = (index) => {
  realtimeAlerts.value.splice(index, 1);
};

const getDetectionIcon = (type) => {
  const icons = {
    person: '👤', car: '🚗', fire: '🔥', face: '😀', smoke: '💨', animal: '🐕',
  };
  return icons[type] || '📦';
};
const getAlertIcon = (type) => {
  const icons = {
    danger: '⛔', warning: '⚠️', info: 'ℹ️', success: '✅',
  };
  return icons[type] || '🚨';
};
const formatTime = (timestamp) => (timestamp ? new Date(timestamp).toLocaleTimeString() : '');

const handleApiError = (error) => {
  if (error.response?.status === 401) {
    authStore.logout();
    router.push('/login');
  }
};

onMounted(() => {
  if (!authStore.isAuthenticated) {
    router.push('/login');
    return;
  }
  if (videoSource.value === 'local') {
    getVideoDevices();
  }
});

onUnmounted(() => {
  stopStream();
});

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
  min-height: 480px;
  background-color: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.video-element, .dplayer-container {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* 确保DPlayer可以正确全屏 */
:deep(.dplayer-fulled) {
  z-index: 9999 !important;
  position: fixed !important;
  width: 100% !important;
  height: 100% !important;
  left: 0 !important;
  top: 0 !important;
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

:deep(.dplayer) {
  width: 100% !important;
  height: 100% !important;
  position: relative !important;
  z-index: 1 !important;
}

/* 确保DPlayer视频元素不会覆盖AIAnalyzer */
:deep(.dplayer-video-wrap) {
  z-index: 1 !important;
}

/* 确保全屏按钮可见并正常工作 */
:deep(.dplayer-controller) {
  z-index: 100 !important;
}

:deep(.dplayer-controller .dplayer-icons .dplayer-icon) {
  pointer-events: auto !important;
}

:deep(.dplayer-controller .dplayer-icons .dplayer-full) {
  display: block !important;
}

/* 确保DPlayer控制栏不会覆盖AIAnalyzer */
:deep(.dplayer-controller) {
  z-index: 90 !important;
}

:deep(.el-form-item__label) {
  color: #fff !important;
}

.control-panel, .results-panel, .alerts-panel {
  margin-bottom: 20px;
}

.setting-description {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}

.detection-list, .alerts-list {
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

.no-results, .no-alerts {
  text-align: center;
  padding: 20px;
  color: #909399;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  border-left: 4px solid;
  background-color: #f8f9fa;
  position: relative;
}

.alert-danger { border-left-color: #f56c6c; background-color: #fef0f0; }
.alert-warning { border-left-color: #e6a23c; background-color: #fdf6ec; }
.alert-info { border-left-color: #409eff; background-color: #ecf5ff; }
.alert-success { border-left-color: #67c23a; background-color: #f0f9ff; }

.alert-icon {
  font-size: 20px;
  margin-right: 12px;
}

.alert-content {
  flex: 1;
}

.alert-title {
  font-weight: bold;
}

.alert-description, .alert-time {
  font-size: 12px;
  color: #606266;
}

.alert-remove {
  position: absolute;
  top: 8px;
  right: 8px;
  cursor: pointer;
}

.input-help {
  margin-top: 4px;
  font-size: 12px;
}
</style>
