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
              <!-- 添加调试按钮 -->
              <el-button
                type="warning"
                size="small"
                @click="checkWebRTCStatus"
              >
                检查WebRTC状态
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

                <div v-else class="video-player-wrapper" :class="{
  'webrtc-mode': videoSource === 'webrtc',
  'local-mode': videoSource === 'local',
  'non-webrtc-mode': videoSource !== 'webrtc' && videoSource !== 'local'
}">
                  <!-- 修改视频元素，确保始终可见 -->
                  <video
                    ref="videoElement"
                    class="video-element"
                    autoplay
                    muted
                    playsinline
                    controls
                    @loadedmetadata="onVideoLoaded"
                    @error="onVideoError"
                    @playing="onVideoPlaying"
                    style="width: 100%; height: 100%; object-fit: contain; display: block; background-color: #000; z-index: 5; position: absolute; top: 0; left: 0;"
                  ></video>

                  <div
                    v-if="videoSource !== 'local' && videoSource !== 'webrtc'"
                    ref="videoRef"
                    class="dplayer-container"
                  ></div>

                  <!-- AIAnalyzer component removed -->
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
                      v-model="aiSettings.face_recognition"
                      :disabled="!isStreaming || !aiAnalysisEnabled"
                      @change="() => updateAISettings('face_recognition')"
                    />
                    <div class="setting-description">
                      识别视频中的人脸，并与已知人脸库进行匹配。可用于访客识别和权限控制。
                    </div>
                  </el-form-item>
                  <el-form-item label="目标检测">
                    <el-switch
                      v-model="aiSettings.object_detection"
                      :disabled="!isStreaming || !aiAnalysisEnabled"
                      @change="() => updateAISettings('object_detection')"
                    />
                    <div class="setting-description">
                      检测视频中的人员、车辆、包裹等常见目标，支持多目标同时跟踪。
                    </div>
                  </el-form-item>
                  <el-form-item label="行为分析">
                    <el-switch
                      v-model="aiSettings.behavior_analysis"
                      :disabled="!isStreaming || !aiAnalysisEnabled"
                      @change="() => updateAISettings('behavior_analysis')"
                    />
                    <div class="setting-description">
                      分析人员行为，如跌倒、奔跑、聚集等异常行为，及时发出预警。
                    </div>
                  </el-form-item>
                  <el-form-item label="声音检测">
                    <el-switch
                      v-model="aiSettings.sound_detection"
                      :disabled="!isStreaming || !aiAnalysisEnabled"
                      @change="() => updateAISettings('sound_detection')"
                    />
                    <div class="setting-description">
                      监测环境声音，检测异常噪音、尖叫等声音事件，提供声音告警。
                    </div>
                  </el-form-item>
                  <el-form-item label="火焰检测">
                    <el-switch
                      v-model="aiSettings.fire_detection"
                      :disabled="!isStreaming || !aiAnalysisEnabled"
                      @change="() => updateAISettings('fire_detection')"
                    />
                    <div class="setting-description">
                      检测视频中的火焰和烟雾，用于及早发现火灾隐患，保障安全。
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
                  <div class="header-actions">
                    <el-button
                      size="small"
                      type="danger"
                      plain
                      icon="Delete"
                      circle
                      @click="clearAllAlerts"
                      title="清空所有告警"
                      v-if="realtimeAlerts && realtimeAlerts.length > 0"
                    />
                    <el-button
                      size="small"
                      type="info"
                      plain
                      icon="Setting"
                      circle
                      @click="data.showAlertSettings = true"
                      title="告警设置"
                    />
                    <el-badge :value="(realtimeAlerts || []).length" class="badge" :max="99" />
                  </div>
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

    <!-- 告警设置对话框 -->
    <el-dialog
      title="告警设置"
      v-model="data.showAlertSettings"
      width="400px"
      destroy-on-close
    >
      <el-form :model="data.alertSettingsForm" label-width="140px">
        <el-form-item label="告警限流时间(秒)">
          <el-slider
            v-model="data.alertSettingsForm.throttleTime"
            :min="3"
            :max="60"
            :step="1"
            :marks="{3:'3秒', 10:'10秒', 30:'30秒', 60:'1分钟'}"
          />
        </el-form-item>
        <el-form-item label="启用告警摘要">
          <el-switch v-model="data.alertSettingsForm.enableSummary" />
        </el-form-item>
        <el-form-item label="摘要最小告警数" v-if="data.alertSettingsForm.enableSummary">
          <el-input-number
            v-model="data.alertSettingsForm.minCount"
            :min="1"
            :max="20"
            :step="1"
            size="small"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="data.showAlertSettings = false">取消</el-button>
          <el-button type="primary" @click="updateAlertSettings">保存设置</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, nextTick, watch } from 'vue';
import { useApi } from '@/api';
import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Close, Cpu, VideoCamera, Warning, Search, SuccessFilled, CircleCloseFilled } from '@element-plus/icons-vue';
import flvjs from 'flv.js';
import DPlayer from 'dplayer';
import Hls from 'hls.js';
import useWebRTC from '@/composables/useWebRTC';

// --- State and Refs ---
const api = useApi();
const router = useRouter();
const authStore = useAuthStore();
const videoElement = ref(null);
const videoRef = ref(null);
const video = ref(null);
const player = ref(null);
const isStreaming = ref(false);
const videoSource = ref('rtmp'); // 修改默认使用RTMP而不是WebRTC
const rawInputStreamUrl = ref('rtmp://localhost:1935/live/test'); // 预填充RTMP地址
const playbackUrl = ref('');
const selectedDeviceId = ref('');
const videoDevices = ref([]);
const cameraId = ref(`camera_${Date.now()}`);
const aiAnalysisEnabled = ref(false);
const localTrackingEnabled = ref(false);
const aiSettings = reactive({
  face_recognition: true,
  object_detection: true,
  behavior_analysis: false,
  sound_detection: false,
  fire_detection: true,
  liveness_detection: true,
});
const detectionResults = ref([]);
const performanceStats = ref({});
const realtimeAlerts = ref([]);
const dangerZones = ref([]);
const currentZonePoints = ref([]);
const isDrawingZone = ref(false);
const wsConnected = ref(false);
let ws = null;

// WebRTC相关
const apiBaseUrl = import.meta.env.VITE_APP_AI_SERVICE_URL || 'http://localhost:8002';  // 修改为正确的AI服务端口
const { connect: connectWebRTC, disconnect: disconnectWebRTC, isConnected: webrtcConnected } = useWebRTC(apiBaseUrl);

// 【新增】一个可重用的函数来根据当前设置过滤检测结果
const filterResults = (results) => {
  if (!results || results.length === 0) {
    return [];
  }

  return results.filter(det => {
    const { type, class_name } = det;

    // 人脸识别
    if (type === 'face' || class_name === 'face') {
      return aiSettings.face_recognition;
    }

    // 火焰/烟雾检测
    if (type === 'fire' || type === 'smoke' || class_name === 'fire' || class_name === 'smoke') {
      return aiSettings.fire_detection;
    }

    // 目标检测 (涵盖常见物体: 人员、车辆、包裹等)
    const objectTypes = ['person', 'car', 'bicycle', 'motorcycle', 'bus', 'truck', 'backpack', 'handbag', 'suitcase'];
    if (objectTypes.includes(type) || objectTypes.includes(class_name)) {
      return aiSettings.object_detection;
    }

    // 行为分析和声音检测通常不会有独立的检测框，除非后端有特定实现
    // 默认情况下，如果类型不匹配任何受控类别，则显示
    return true;
  });
};


// --- WebSocket Logic ---
const disconnectWebSocket = () => {
  if (ws) {
    console.log('[WebSocket] 正在主动断开连接...');
    ws.onclose = null; // 移除onclose处理器，避免重连
    ws.onerror = null;
    ws.onmessage = null;
    ws.onopen = null;
    ws.close(1000, "正常关闭"); // 使用正常关闭代码
    ws = null;
    wsConnected.value = false;
  }
};

const connectWebSocket = () => {
  disconnectWebSocket();

  const backendWsUrl = import.meta.env.VITE_APP_WS_URL || 'ws://127.0.0.1:8000';
  
  const currentCameraId = cameraId.value || 'test';
  
  let wsFullUrl = '';
  if (backendWsUrl.includes('/ws/')) {
    wsFullUrl = backendWsUrl.replace(/\/ws\/?$/, '/ws/') + `alerts/${currentCameraId}/`;
  } else {
    wsFullUrl = `${backendWsUrl.replace(/\/$/, '')}/ws/alerts/${currentCameraId}/`;
  }
  
  console.log(`[WebSocket] 正在连接到后端WebSocket服务: ${wsFullUrl}`);
  
  try {
    ws = new WebSocket(wsFullUrl);
    
    // 心跳间隔（毫秒）
    const HEARTBEAT_INTERVAL = 30000;
    // 存储心跳定时器ID
    let heartbeatTimer = null;
    
    // 发送心跳的函数
    const sendHeartbeat = () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        console.log('[WebSocket] 发送心跳...');
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    };
    
    ws.onopen = () => {
      wsConnected.value = true;
      console.log('[WebSocket] ✅ 连接已建立! 可以接收实时检测结果');
      
      ws.send(JSON.stringify({
        type: 'subscribe',
        camera_id: currentCameraId
      }));
      
      // 连接成功后开始发送心跳
      heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
    };
    
    ws.onmessage = (event) => {
      try {
        const messageData = JSON.parse(event.data);
        
        // 打印接收到的消息类型，帮助调试
        console.log(`[WebSocket] 收到消息，类型: ${messageData.type || '未知'}`, messageData);
        
        if (messageData.type === 'stream_initialized') {
          console.log('[父组件] 收到视频流初始化消息，分辨率为:', messageData.data?.resolution);
        
        } else if (messageData.type === 'detection_result' && messageData.data) {
          let detections = [];
          const data = messageData.data;
          
          const isThrottled = data.is_throttled === true;
          
          if (data.detections) {
            if (Array.isArray(data.detections)) {
              detections = data.detections;
            } else if (data.detections.detections) {
              detections = data.detections.detections;
            } else {
              detections = [data.detections];
            }
          }

          const timestamp = data.timestamp || Date.now();
          const frameId = data.frame_id || `frame_${timestamp}`;
          const currentVideoTime = video.value ? video.value.currentTime : 0;

          detections.forEach(detection => {
            detection.frame_timestamp = timestamp;
            detection.frame_id = frameId;
            detection.video_time = currentVideoTime;
            
            if (isThrottled) {
              detection.is_throttled = true;
            }
          });

          detectionResults.value = filterResults(detections);
          console.log(`[WebSocket] 更新检测结果: ${detections.length}个对象`);

        } else if (messageData.type === 'new_alert' || messageData.type === 'alert') {
          const alertData = messageData.data || messageData;
          handleAlert(alertData);
        
        } else if (messageData.type === 'throttled_alert') {
          console.log('[告警限流] 收到限流通知:', messageData);
          
          if (data && data.alertSettingsForm && data.alertSettingsForm.enableSummary) {
            ElMessage({
              type: 'info',
              message: `[告警限流] ${messageData.message || '告警限流已启用'}`,
              duration: 3000
            });
          }
          
          realtimeAlerts.value.unshift({
            id: `throttle_${Date.now()}`,
            type: 'throttled',
            title: '告警限流',
            description: messageData.message || `相同类型告警在${messageData.throttle_seconds || 10}秒内多次触发，已限流`,
            timestamp: Date.now(),
          });
          
          if (realtimeAlerts.value.length > 20) {
            realtimeAlerts.value.pop();
          }
        } else if (messageData.type === 'pong' || messageData.type === 'heartbeat') {
          // 处理心跳消息
          console.log(`[WebSocket] 收到心跳响应: ${messageData.type}`);
        } else if (messageData.type === 'subscription_confirmed') {
          // 订阅确认
          console.log(`[WebSocket] 订阅确认: camera_id=${messageData.camera_id}, group=${messageData.group}`);
        } else {
          // 未知消息类型
          console.log(`[WebSocket] 收到未知类型消息:`, messageData);
        }
      } catch (error) {
        console.error('WebSocket 消息解析错误:', error, '原始消息:', event.data);
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket 发生错误:', error);
      ElMessage.warning('WebSocket连接错误，无法接收实时检测结果');
      // 出错时清除心跳定时器
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
        heartbeatTimer = null;
      }
    };
    
    ws.onclose = (event) => {
      wsConnected.value = false;
      ws = null;
      console.log(`[WebSocket] 连接已关闭，代码: ${event.code}, 原因: ${event.reason || '未知'}`);
      // 关闭时清除心跳定时器
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
        heartbeatTimer = null;
      }
      
      // 如果不是正常关闭且正在流媒体，尝试重新连接
      if (event.code !== 1000 && event.code !== 1001 && isStreaming.value) {
        console.log('[WebSocket] 非正常关闭，3秒后尝试重新连接...');
        setTimeout(() => {
          if (isStreaming.value) {
            console.log('[WebSocket] 正在重新连接...');
            connectWebSocket();
          }
        }, 3000);
      }
    };
  } catch (wsError) {
    console.error('[WebSocket] 创建WebSocket连接失败:', wsError);
    ElMessage.error('无法创建WebSocket连接，部分功能可能不可用');
  }
};

const stopStream = async () => {
  if (aiAnalysisEnabled.value) {
    await stopAIAnalysis();
  }
  disconnectWebSocket();
  
  // 断开WebRTC连接
  if (videoSource.value === 'webrtc') {
    await disconnectWebRTC();
  }
  
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
      
      // 本地摄像头启动后连接WebSocket和AI分析
      connectWebSocket();
      if (aiAnalysisEnabled.value) {
        await startAIAnalysis();
      }
      
    } else if (videoSource.value === 'webrtc') {
      // 使用WebRTC接收视频流
      // WebRTC模式下，startWebRTCStream会自动启动AI流处理和WebRTC连接
      await startWebRTCStream();
      
      // WebRTC模式下连接WebSocket
      connectWebSocket();
      
      // 注意：WebRTC模式下不需要额外调用startAIAnalysis，
      // 因为startWebRTCStream已经启动了AI流处理
      aiAnalysisEnabled.value = true;
      
    } else {
      if (videoSource.value === 'rtmp') {
        const rtmpMatch = rawInputStreamUrl.value.match(/\/([a-zA-Z0-9_-]+)$/);
        if (!rtmpMatch || !rtmpMatch[1]) throw new Error('RTMP流地址格式不正确');
        playbackUrl.value = `http://localhost:8080/hls/${rtmpMatch[1]}.m3u8`;
      } else {
        playbackUrl.value = rawInputStreamUrl.value;
      }
      await startNetworkStream();
      
      // 网络流启动后连接WebSocket和AI分析
      connectWebSocket();
      if (aiAnalysisEnabled.value) {
        await startAIAnalysis();
      }
    }
  } catch (error) {
    ElMessage.error(`启动视频流失败: ${error.message}`);
    isStreaming.value = false;
  }
};

// 启动WebRTC流
const startWebRTCStream = async () => {
  try {
    console.log('[WebRTC] 正在启动WebRTC流...');

    // 确保videoElement引用存在
    if (!videoElement.value) {
      console.error('[WebRTC] 视频元素引用不存在，请检查模板。');
      await nextTick(); // 等待DOM更新
      if (!videoElement.value) {
        throw new Error('视频元素(videoElement)未在DOM中找到。');
      }
    }

    // 从输入中提取流名称
    let streamName = rawInputStreamUrl.value.trim();

    // 如果输入了完整的RTMP URL，提取流名称
    if (streamName.startsWith('rtmp://')) {
      const match = streamName.match(/\/([^\/]+)$/);
      if (match && match[1]) {
        streamName = match[1];
        console.log(`[WebRTC] 从RTMP URL提取的流名称: ${streamName}`);
      }
    }

    // 【关键】使用纯粹的流名称作为摄像头ID
    cameraId.value = streamName;
    console.log(`[WebRTC] 将使用摄像头ID: ${cameraId.value}`);

    const rtmpUrl = `rtmp://localhost:1935/live/${streamName}`;
    console.log(`[WebRTC] 使用RTMP URL: ${rtmpUrl}`);

    const streamConfig = {
      camera_id: cameraId.value,
      stream_url: rtmpUrl,
      source_type: 'rtmp',
      enable_face_recognition: aiSettings.face_recognition,
      enable_object_detection: aiSettings.object_detection,
      enable_behavior_detection: aiSettings.behavior_analysis,
      enable_fire_detection: aiSettings.fire_detection,
      enable_sound_detection: aiSettings.sound_detection,
      enable_liveness_detection: aiSettings.liveness_detection
    };

    console.log('[WebRTC] 启动AI流配置:', streamConfig);

    const response = await api.ai.startStream(streamConfig);
    console.log('[WebRTC] AI流启动响应:', response);

    if (response?.status !== 'success') {
      throw new Error(response?.message || 'AI流处理启动失败');
    }

    console.log('[WebRTC] AI流处理已启动，正在建立WebRTC连接');
    console.log('[WebRTC] 等待6秒让AI服务初始化视频流...');
    await new Promise(resolve => setTimeout(resolve, 6000));

    try {
      console.log(`[WebRTC] 正在连接摄像头ID: ${cameraId.value}, API基础URL: ${apiBaseUrl}`);
      
      // 【强化】确保video元素先显示出来
      if (videoElement.value) {
        videoElement.value.style.display = 'block';
        videoElement.value.style.width = '100%';
        videoElement.value.style.height = '100%';
        videoElement.value.style.objectFit = 'contain';
        console.log('[WebRTC] 已设置视频元素样式:', 
          'display:', videoElement.value.style.display,
          'width:', videoElement.value.style.width,
          'height:', videoElement.value.style.height
        );
      }
      
      // 将 videoElement.value 传递给 connectWebRTC
      await connectWebRTC(cameraId.value, videoElement.value);
      
      // 设置video.value引用，确保其他函数可以访问到视频元素
      video.value = videoElement.value;

      // 强制更新视频元素状态和样式
      await nextTick();
      if (videoElement.value) {
        console.log('[WebRTC] 视频元素状态检查:', 
          'readyState:', videoElement.value.readyState,
          'videoWidth:', videoElement.value.videoWidth,
          'videoHeight:', videoElement.value.videoHeight
        );
      }

      videoElement.value.addEventListener('loadedmetadata', () => {
        console.log('[WebRTC] 视频元数据已加载，视频尺寸:', videoElement.value.videoWidth, 'x', videoElement.value.videoHeight);
        onVideoLoaded();
      });
      
      // 添加播放事件监听
      videoElement.value.addEventListener('playing', () => {
        console.log('[WebRTC] 视频已开始播放!');
      });
      
      // 添加错误事件监听
      videoElement.value.addEventListener('error', (e) => {
        console.error('[WebRTC] 视频播放错误:', e);
      });

      console.log('[WebRTC] WebRTC流启动成功');
    } catch (webrtcError) {
      console.error('[WebRTC] WebRTC连接失败，尝试直接播放RTMP流:', webrtcError);
      ElMessage.warning('WebRTC连接失败，将使用普通RTMP播放模式');
      
      // WebRTC失败时的回退逻辑(可选)
      // 将videoSource切换为rtmp模式并重新启动
      videoSource.value = 'rtmp';
      await nextTick();
      if (videoRef.value) {
         const options = {
            container: videoRef.value,
            live: true,
            autoplay: true,
            video: {
              url: rtmpUrl,
              type: 'flv'
            }
         };
         player.value = new DPlayer(options);
         video.value = player.value.video;
      }
    }
  } catch (error) {
    ElMessage.error(`启动WebRTC流失败: ${error.message}`);
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
    // 如果是WebRTC模式，不需要测试连接，直接返回成功
    if (videoSource.value === 'webrtc') {
      console.log('[测试连接] WebRTC模式无需测试连接');
      return true;
    }
    
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
    // 移除对aiAnalyzer的引用，因为该组件已被删除
  });

  // 播放进度变化时再次检查Canvas尺寸
  player.value.on('timeupdate', () => {
    // 每10秒检查一次
    const currentTime = player.value.video.currentTime;
    if (currentTime > 0 && Math.floor(currentTime) % 10 === 0) {
      // 移除对aiAnalyzer的引用
    }
  });

  // 监听视频调整尺寸事件
  player.value.on('resize', () => {
    console.log('[播放器] 视频尺寸已调整');
    // 移除对aiAnalyzer的引用
  });

  // 监听全屏变化
  player.value.on('fullscreen', () => {
    console.log('[播放器] 视频全屏状态已变化');
    // 移除对aiAnalyzer的引用
  });

  console.log('[播放器] 播放器创建完成，当前视频元素:', video.value);
};

// --- AI Logic ---
// 新增：前端设置项到后端API参数的映射
const settingToApiMapping = {
};

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
    face_recognition: '人脸识别',
    object_detection: '目标检测',
    behavior_analysis: '行为分析',
    sound_detection: '声音检测',
    fire_detection: '火焰检测',
  };
  return translations[settingName] || settingName;
};

// 获取当前AI设置的函数
const fetchAISettings = async () => {
  if (!cameraId.value || !isStreaming.value) return;

  try {
    const response = await api.ai.updateSettings(cameraId.value, {});
    if (response?.settings) {
      // 将后端返回的设置直接更新到本地状态，因为键名现在已匹配
      Object.assign(aiSettings, response.settings);
      console.log('[AI设置] 已从服务器获取最新设置:', response.settings);
    }
  } catch (error) {
    console.error('[AI设置] 获取设置失败:', error);
  }
};

const startAIAnalysis = async () => {
  try {
    const streamUrlForAI = (videoSource.value === 'local') ? `webcam://${selectedDeviceId.value}` : rawInputStreamUrl.value;
    
    // 直接使用aiSettings作为payload的基础
    const payload = {
      camera_id: cameraId.value,
      stream_url: streamUrlForAI,
      source_type: videoSource.value,
      settings: aiSettings,
    };
    
    const response = await api.ai.startStream(payload);
    if (response?.status !== 'success') {
      throw new Error(response?.message || response?.detail || 'AI分析启动失败');
    }

    // 启动成功后，获取最新设置
    aiAnalysisEnabled.value = true;
    await fetchAISettings();
    
    // 如果是WebRTC模式，确保视频元素已创建并连接
    if (videoSource.value === 'webrtc' && !webrtcConnected.value) {
      await startWebRTCStream();
    }

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
  console.log('[视频检查] 当前视频容器尺寸:', videoRef.value ? `${videoRef.value.clientWidth} x ${videoRef.value.clientHeight}` : '无法获取容器尺寸');
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

// 添加更多的视频调试信息
const onVideoLoaded = () => {
  if (!video.value) {
    console.warn('[视频] 视频元素尚未加载');
    return;
  }

  console.log('[视频] 视频已加载，尺寸:', video.value.videoWidth, 'x', video.value.videoHeight);
  console.log('[视频] 视频元素属性:', 
    'currentSrc:', video.value.currentSrc,
    'networkState:', video.value.networkState,
    'readyState:', video.value.readyState,
    'paused:', video.value.paused
  );
  
  // 尝试强制播放视频
  try {
    if (video.value.paused) {
      console.log('[视频] 尝试强制播放视频');
      video.value.play().then(() => {
        console.log('[视频] 强制播放成功');
      }).catch(err => {
        console.error('[视频] 强制播放失败:', err);
      });
    }
  } catch (e) {
    console.error('[视频] 播放尝试出错:', e);
  }
  
  // 记录视频信息但不再尝试调整Canvas，因为AIAnalyzer组件已被移除
  logVideoElementInfo();
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
// 清空所有告警
const clearAllAlerts = () => {
  realtimeAlerts.value = [];
  ElMessage.success('已清空所有告警');
};

// 删除单个告警
const removeAlert = (index) => {
  realtimeAlerts.value.splice(index, 1);
};

const getDetectionIcon = (type) => {
  const icons = {
    person: '👤', car: '🚗', fire: '🔥', face: '😀', smoke: '💨', animal: '🐕',
  };
  return icons[type] || '📦';
};
// 获取告警图标
const getAlertIcon = (type) => {
  const icons = {
    'stranger_intrusion': '👤',
    'person_fall': '🆘',
    'fire_smoke': '🔥',
    'stranger_face_detected': '👁️',
    'spoofing_attack': '⚠️',
    'abnormal_sound_scream': '🔊',
    'abnormal_sound_fight': '👊',
    'abnormal_sound_glass_break': '💔',
    'other': '❗',
    // 添加新的限流告警类型图标
    'throttled': '⏱️'
  };
  return icons[type] || '❓';
};
const formatTime = (timestamp) => (timestamp ? new Date(timestamp).toLocaleTimeString() : '');

const handleApiError = (error) => {
  if (error.response?.status === 401) {
    authStore.logout();
    router.push('/login');
  }
};

const data = reactive({
  recentAlerts: new Map(), // 存储最近的告警，用于去重
  alertThrottleTime: 10000, // 相同类型告警的限流时间（毫秒）
  alertCountMap: new Map(), // 记录短时间内特定类型告警的计数
  alertSummaryTimer: null, // 告警摘要定时器
  pendingAlertCount: 0, // 未显示的告警计数
  
  // 告警设置
  showAlertSettings: false, // 控制告警设置面板显示
  alertSettingsForm: {
    throttleTime: 10, // 秒为单位，UI显示用
    enableSummary: true, // 是否启用告警摘要
    minCount: 3, // 触发摘要的最小告警数量
  }
});

// 更新告警设置
const updateAlertSettings = () => {
  // 将秒转换为毫秒
  data.alertThrottleTime = data.alertSettingsForm.throttleTime * 1000;
  console.log('[告警设置] 已更新:', data.alertSettingsForm);
  data.showAlertSettings = false;
  
  // 清空当前的告警缓存
  data.recentAlerts.clear();
  data.alertCountMap.clear();
  data.pendingAlertCount = 0;
  
  if (data.alertSummaryTimer) {
    clearTimeout(data.alertSummaryTimer);
    data.alertSummaryTimer = null;
  }
  
  ElMessage.success('告警设置已更新');
};

// 告警处理函数 - 添加限流逻辑
const handleAlert = (alertData) => {
  const alertType = alertData.alert_type || alertData.event_type || 'warning';
  const alertMessage = alertData.message || '检测到异常事件';
  const alertKey = `${alertType}:${alertMessage}`;
  const now = Date.now();
  
  // 检查是否是重复告警
  if (data.recentAlerts.has(alertKey)) {
    const lastAlertTime = data.recentAlerts.get(alertKey);
    
    // 如果相同告警在限流时间内出现，则只增加计数而不显示
    if (now - lastAlertTime < data.alertThrottleTime) {
      // 增加此类告警的计数
      const currentCount = data.alertCountMap.get(alertKey) || 0;
      data.alertCountMap.set(alertKey, currentCount + 1);
      data.pendingAlertCount++;
      
      // 如果启用了告警摘要且没有摘要定时器，创建一个
      if (data.alertSettingsForm.enableSummary && !data.alertSummaryTimer) {
        data.alertSummaryTimer = setTimeout(() => {
          // 显示告警摘要（只有当累积的告警数量超过最小值时才显示）
          if (data.pendingAlertCount >= data.alertSettingsForm.minCount) {
            ElMessage({
              type: 'warning',
              message: `最近${data.alertThrottleTime/1000}秒内有${data.pendingAlertCount}个告警，请关注监控画面`,
              duration: 5000
            });
          }
          
          // 重置计数器和定时器
          data.alertCountMap.clear();
          data.pendingAlertCount = 0;
          data.alertSummaryTimer = null;
        }, data.alertThrottleTime);
      }
      
      // 更新最后告警时间
      data.recentAlerts.set(alertKey, now);
      return;
    }
  }
  
  // 如果是新告警或者超过限流时间的告警，则显示
  ElMessage({ 
    type: 'warning', 
    message: alertMessage,
    duration: 3000 // 降低提示显示时间
  });
  
  // 更新最后告警时间
  data.recentAlerts.set(alertKey, now);
  
  // 添加到实时告警列表
  realtimeAlerts.value.unshift({
    id: `alert_${now}`,
    type: alertType,
    title: alertMessage,
    description: alertData.description || alertData.details?.message || '请注意查看监控画面',
    timestamp: now,
  });
  
  // 限制告警列表长度
  if (realtimeAlerts.value.length > 20) {
    realtimeAlerts.value.pop();
  }
};

// 添加检查WebRTC状态的函数
const checkWebRTCStatus = async () => {
  console.log('[WebRTC调试] 检查WebRTC状态...');
  
  // 检查视频元素引用
  if (!videoElement.value) {
    console.error('[WebRTC调试] 视频元素引用不存在!');
    ElMessage.error('视频元素引用不存在，这将导致WebRTC连接失败');
    return;
  }
  
  console.log('[WebRTC调试] 视频元素状态:', 
    'offsetWidth:', videoElement.value.offsetWidth,
    'offsetHeight:', videoElement.value.offsetHeight,
    'style.display:', videoElement.value.style.display,
    'style.visibility:', videoElement.value.style.visibility,
    'readyState:', videoElement.value.readyState
  );
  
  // 尝试调用后端API获取WebRTC连接状态
  try {
    const response = await api.ai.getWebRTCStatus();
    console.log('[WebRTC调试] 服务器WebRTC状态:', response);
    ElMessage.info(`WebRTC连接状态: ${JSON.stringify(response)}`);
  } catch (error) {
    console.error('[WebRTC调试] 获取WebRTC状态失败:', error);
    ElMessage.error('获取WebRTC状态失败');
  }
  
  // 尝试强制视频元素可见
  if (videoElement.value) {
    videoElement.value.style.display = 'block';
    videoElement.value.style.visibility = 'visible';
    videoElement.value.style.width = '100%';
    videoElement.value.style.height = '100%';
    videoElement.value.style.position = 'absolute';
    videoElement.value.style.top = '0';
    videoElement.value.style.left = '0';
    videoElement.value.style.zIndex = '10';
    videoElement.value.style.backgroundColor = '#000';
    
    // 尝试播放视频
    if (videoElement.value.paused) {
      videoElement.value.play()
        .then(() => console.log('[WebRTC调试] 视频播放成功'))
        .catch(err => console.error('[WebRTC调试] 视频播放失败:', err));
    }
    
    ElMessage.success('已强制设置视频元素样式，请查看是否可见');
  }
};

// --- 组件生命周期钩子 ---
onMounted(async () => {
  // 获取可用的视频设备
  try {
    // 请求摄像头权限
    const devices = await navigator.mediaDevices.enumerateDevices();
    videoDevices.value = devices.filter(device => device.kind === 'videoinput');
    
    if (videoDevices.value.length > 0) {
      selectedDeviceId.value = videoDevices.value[0].deviceId;
    }
    
    // 确保视频元素引用存在 - 重要：添加更多等待和检查逻辑
    await nextTick();
    let attempts = 0;
    const maxAttempts = 5;
    
    const checkVideoElement = async () => {
      if (videoElement.value) {
        console.log('[挂载] 成功获取视频元素引用');
        return true;
      } else {
        console.warn(`[挂载] 未找到视频元素引用，尝试 ${attempts + 1}/${maxAttempts}`);
        await nextTick();
        attempts++;
        
        if (attempts >= maxAttempts) {
          console.error('[挂载] 多次尝试后仍未找到视频元素引用');
          return false;
        }
        
        // 延迟100ms再次尝试
        await new Promise(resolve => setTimeout(resolve, 100));
        return await checkVideoElement();
      }
    };
    
    await checkVideoElement();
  } catch (error) {
    console.error('获取视频设备列表失败:', error);
  }
  
  // 初始化其他必要的内容
  await fetchAISettings();
});

onUnmounted(() => {
  disconnectWebSocket();
  
  if (isStreaming.value) {
    stopStream();
  }
});

// 添加新的事件处理函数
const onVideoError = (e) => {
  console.error('[视频] 视频加载错误:', e);
  if (videoElement.value) {
    console.error('[视频] 错误代码:', videoElement.value.error?.code);
    console.error('[视频] 错误消息:', videoElement.value.error?.message);
  }
};

const onVideoPlaying = () => {
  console.log('[视频] 视频开始播放!', 
    'currentTime:', videoElement.value?.currentTime,
    'videoWidth:', videoElement.value?.videoWidth,
    'videoHeight:', videoElement.value?.videoHeight
  );
};

// 添加视频状态检查定时器
onMounted(() => {
  // 每10秒检查一次视频状态，确保视频仍在播放
  const checkVideoInterval = setInterval(() => {
    if (isStreaming.value && videoElement.value) {
      console.log('[视频状态检查] 视频元素状态:', 
        'paused:', videoElement.value.paused,
        'ended:', videoElement.value.ended,
        'readyState:', videoElement.value.readyState,
        'networkState:', videoElement.value.networkState,
        'currentTime:', videoElement.value.currentTime,
        'error:', videoElement.value.error ? '有错误' : '无错误'
      );
      
      // 如果视频已暂停但应该在播放，尝试重新播放
      if (videoElement.value.paused && !videoElement.value.ended && videoElement.value.readyState >= 2) {
        console.log('[视频状态检查] 视频已暂停，尝试重新播放');
        videoElement.value.play().catch(err => {
          console.error('[视频状态检查] 无法重新播放视频:', err);
        });
      }
    }
  }, 10000);
  
  // 组件卸载时清除定时器
  onUnmounted(() => {
    clearInterval(checkVideoInterval);
  });
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

/* 修改视频容器样式 */
.video-container {
  position: relative;
  width: 100%;
  height: 480px;
  background-color: #000;
  border-radius: 4px;
  overflow: hidden;
}

.video-player-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #000;
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 使视频元素始终可见 */
.video-element {
  position: absolute;
  top: 0;
  left: 0;
  width: 100% !important;
  height: 100% !important;
  object-fit: contain;
  z-index: 5;
}

/* 使DPlayer容器只在非WebRTC模式下可见 */
.dplayer-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
  display: none; /* 默认隐藏，只在特定模式下显示 */
}

/* 在非WebRTC模式下显示DPlayer */
.non-webrtc-mode .dplayer-container {
  display: block;
}

/* 在WebRTC或local模式下隐藏DPlayer */
.webrtc-mode .dplayer-container,
.local-mode .dplayer-container {
  display: none;
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

/* 确保DPlayer视频元素正常显示 */
:deep(.dplayer-video-wrap) {
  position: relative;
  width: 100% !important;
  height: 100% !important;
  z-index: 2;
}

:deep(.dplayer-video) {
  width: 100% !important;
  height: 100% !important;
  object-fit: contain;
}

/* 确保控制栏可见并正常工作 */
:deep(.dplayer-controller) {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 3;
}

:deep(.dplayer-controller .dplayer-icons .dplayer-icon) {
  pointer-events: auto !important;
}

:deep(.dplayer-controller .dplayer-icons .dplayer-full) {
  display: block !important;
}

/* 确保DPlayer控制栏显示正常 */
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

/* 告警项样式 */
.alert-item {
  display: flex;
  padding: 10px;
  margin-bottom: 10px;
  border-radius: 4px;
  background-color: #f8f8f8;
  transition: all 0.3s;
}

/* 不同类型告警的样式 */
.alert-stranger_intrusion { border-left: 4px solid #409eff; }
.alert-person_fall { border-left: 4px solid #f56c6c; }
.alert-fire_smoke { border-left: 4px solid #e6a23c; }
.alert-stranger_face_detected { border-left: 4px solid #67c23a; }
.alert-spoofing_attack { border-left: 4px solid #f56c6c; }
.alert-abnormal_sound_scream { border-left: 4px solid #e6a23c; }
.alert-abnormal_sound_fight { border-left: 4px solid #f56c6c; }
.alert-abnormal_sound_glass_break { border-left: 4px solid #f56c6c; }
.alert-other { border-left: 4px solid #909399; }
/* 添加限流告警样式 */
.alert-throttled { 
  border-left: 4px solid #909399; 
  background-color: #f5f7fa;
  color: #909399;
}

/* 告警图标样式 */
.alert-icon {
  font-size: 24px;
  margin-right: 10px;
  width: 30px;
  text-align: center;
}

/* 告警内容样式 */
.alert-content {
  flex: 1;
}

.alert-title {
  font-weight: bold;
  margin-bottom: 5px;
}

.alert-description {
  font-size: 12px;
  color: #606266;
  margin-bottom: 5px;
}

.alert-time {
  font-size: 12px;
  color: #909399;
}

.input-help {
  margin-top: 4px;
  font-size: 12px;
}

/* 卡片标题栏样式 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 告警设置对话框 */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  width: 100%;
  margin-top: 20px;
}

/* 告警摘要文本 */
.alert-summary {
  font-weight: bold;
  color: #e6a23c;
}
</style>
