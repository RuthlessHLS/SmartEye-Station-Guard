<template>
  <div class="face-login-container">
    <div class="face-login-card">
      <h2 class="title">人脸识别登录</h2>
      <p class="subtitle">请将面部对准摄像头，并按提示操作</p>

      <!-- 视频预览区域 -->
      <div class="video-wrapper">
        <video ref="videoElement" autoplay muted playsinline class="video-feed"></video>
        <div class="video-overlay">
          <div class="face-guide-frame"></div>
          
          <!-- 状态提示 -->
          <div v-if="statusMessage" class="status-prompt" :class="statusClass">
             <i v-if="statusIcon" class="status-icon" :class="statusIcon"></i>
            {{ statusMessage }}
          </div>
          
          <!-- 倒计时 -->
          <div v-if="isVerifying" class="countdown-circle">
            <svg class="countdown-svg" viewBox="0 0 36 36">
              <path class="circle-bg"
                d="M18 2.0845
                  a 15.9155 15.9155 0 0 1 0 31.831
                  a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path class="circle"
                :stroke-dasharray="countdownProgress + ', 100'"
                d="M18 2.0845
                  a 15.9155 15.9155 0 0 1 0 31.831
                  a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <div class="countdown-text">{{ countdown.toFixed(1) }}s</div>
          </div>
        </div>
        
        <!-- 加载状态 -->
        <div v-if="loading" class="loading-overlay">
          <div class="spinner"></div>
          <p>{{ loadingMessage }}</p>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-buttons">
        <el-button 
          type="primary"
          @click="startVerification" 
          :disabled="isVerifying || loading"
          :loading="loading"
          size="large"
          round
        >
          {{ verificationButtonText }}
        </el-button>
        <el-button @click="goToPasswordLogin" link>使用密码登录</el-button>
      </div>

      <!-- 错误信息 -->
       <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
        class="error-alert"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { ElMessage, ElAlert, ElButton } from 'element-plus';

const router = useRouter();
const authStore = useAuthStore();
const videoElement = ref(null);

const stream = ref(null);
const websocket = ref(null);
const loading = ref(true); // 初始为true，等待摄像头
const loadingMessage = ref('正在初始化摄像头...');
const errorMessage = ref('');
const statusMessage = ref('准备就绪');
const isVerifying = ref(false);

const countdown = ref(7.0);
const countdownTimer = ref(null);
const frameRequestID = ref(null);

const verificationButtonText = computed(() => {
  if(loading.value) return '准备中...';
  if(isVerifying.value) return '正在验证...';
  if(errorMessage.value) return '重新尝试';
  return '开始人脸识别';
});

const statusInfo = computed(() => {
  switch (statusMessage.value) {
    case '请眨眼':
    case '请左右摇头':
    case '请上下点头':
    case '请张开您的嘴巴':
      return { class: 'challenge', icon: 'el-icon-bell' };
    case '验证成功！正在登录...':
    case '活体检测通过，正在进行身份识别...':
      return { class: 'success', icon: 'el-icon-circle-check' };
    case '识别失败':
    case '验证超时':
    case '活体检测失败':
      return { class: 'error', icon: 'el-icon-circle-close' };
    default:
      return { class: 'info', icon: 'el-icon-info-filled' };
  }
});

const statusClass = computed(() => statusInfo.value.class);
const statusIcon = computed(() => statusInfo.value.icon);


const countdownProgress = computed(() => {
  // 确保countdown.value不大于总时长，避免UI超出
  const totalDuration = 15.0; // 后端总会话超时时间
  return (Math.max(0, countdown.value) / totalDuration) * 100;
});

const initCamera = async () => {
  try {
    loading.value = true;
    loadingMessage.value = '正在初始化摄像头...';
    errorMessage.value = '';
    stream.value = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
    });
    if (videoElement.value) {
      videoElement.value.srcObject = stream.value;
    }
    statusMessage.value = '摄像头准备就绪';
  } catch (error) {
    errorMessage.value = '无法访问摄像头，请检查权限';
    statusMessage.value = '摄像头访问失败';
    console.error(error);
  } finally {
    loading.value = false;
  }
};

const startVerification = () => {
  if (!stream.value) {
    ElMessage.warning('摄像头尚未准备好');
    return;
  }
  
  resetState();
  isVerifying.value = true;
  statusMessage.value = '正在连接服务器...';

  // 使用环境变量中的AI服务URL（端口8002）
  const aiServiceUrl = import.meta.env.VITE_APP_AI_SERVICE_URL || 'http://127.0.0.1:8002';
  // 将http://转换为ws://
  const wsBaseUrl = aiServiceUrl.replace(/^http:\/\//, 'ws://');
  
  // 构建完整的WebSocket URL
  let wsUrl = '';
  if (wsBaseUrl.includes('/ws/')) {
    // 确保在ws和face_verification之间有斜杠
    wsUrl = wsBaseUrl.replace(/\/ws\/?$/, '/ws/') + 'face_verification';
  } else {
    wsUrl = `${wsBaseUrl.replace(/\/$/, '')}/ws/face_verification`;
  }
  
  console.log(`[FaceLogin] 正在连接WebSocket: ${wsUrl}`);
  websocket.value = new WebSocket(wsUrl);

  websocket.value.onopen = () => {
    console.log('[FaceLogin] WebSocket连接成功');
    statusMessage.value = '连接成功，准备接收挑战...';
    // 不再立即开始发送帧，等待服务器指令
  };

  websocket.value.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch(data.status) {
      case 'challenge':
        statusMessage.value = data.message;
        isVerifying.value = true; // 开始验证流程
        startCountdown(); // <--- FIX: Start the countdown timer on new challenge
        
        // 接收到挑战后，开始发送视频帧
        if (!frameRequestID.value) {
          startStreamingFrames(); 
        }
        break;
      case 'info':
        // 显示服务器的提示信息，但不改变核心状态
        statusMessage.value = data.message;
        break;
      case 'verifying':
        // 活体检测成功，准备发送最后一帧
        statusMessage.value = data.message;
        stopStreamingFrames(); // 停止发送连续帧
        sendFinalFrame(); // 发送高质量单帧进行识别
        break;
      case 'success':
        statusMessage.value = "验证成功！正在登录...";
        stopVerification();
        authStore.handleSuccessfulLogin({
          access: data.access,
          refresh: data.refresh,
          user: data.user
        }).then(() => {
          router.push('/dashboard');
        });
        break;
      case 'failed':
        errorMessage.value = data.message || '验证失败，请重试';
        statusMessage.value = data.message.startsWith('活体检测失败') ? '活体检测失败' : '识别失败';
        stopVerification();
        break;
    }
  };

  websocket.value.onerror = (error) => {
    console.error('WebSocket Error:', error);
    errorMessage.value = '连接验证服务器失败，请检查网络或联系管理员。';
    stopVerification();
  };

  websocket.value.onclose = () => {
    console.log('WebSocket connection closed.');
    stopVerification(false); // only stop timers, don't reset state if it's already done
  };
};

// --- FIX: Add countdown logic ---
const startCountdown = () => {
  // 清除之前的计时器
  if (countdownTimer.value) {
    clearInterval(countdownTimer.value);
  }
  // 从后端会话总时长开始倒计时
  countdown.value = 15.0; 
  
  countdownTimer.value = setInterval(() => {
    if (countdown.value > 0) {
      countdown.value -= 0.1;
    } else {
      // 即使前端倒计时结束，也由后端来最终决定超时
      // 这里只停止前端计时器
      stopVerification(true);
    }
  }, 100);
};


const startStreamingFrames = () => {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  
  const sendFrame = () => {
    if (!isVerifying.value || !videoElement.value || websocket.value?.readyState !== WebSocket.OPEN) {
      if (frameRequestID.value) {
        cancelAnimationFrame(frameRequestID.value);
        frameRequestID.value = null;
      }
      return;
    }
    
    canvas.width = videoElement.value.videoWidth;
    canvas.height = videoElement.value.videoHeight;
    context.drawImage(videoElement.value, 0, 0, canvas.width, canvas.height);
    
    canvas.toBlob((blob) => {
      if (blob && websocket.value?.readyState === WebSocket.OPEN) {
        // 发送为二进制数据
        websocket.value.send(blob);
      }
    }, 'image/jpeg', 0.8); // 提高一点图像质量

    frameRequestID.value = requestAnimationFrame(sendFrame);
  };
  
  frameRequestID.value = requestAnimationFrame(sendFrame);
};

const stopStreamingFrames = () => {
  if (frameRequestID.value) {
    cancelAnimationFrame(frameRequestID.value);
    frameRequestID.value = null;
  }
};

const sendFinalFrame = () => {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  
  if (!videoElement.value) return;

  canvas.width = videoElement.value.videoWidth;
  canvas.height = videoElement.value.videoHeight;
  context.drawImage(videoElement.value, 0, 0, canvas.width, canvas.height);
  
  canvas.toBlob((blob) => {
    if (blob && websocket.value?.readyState === WebSocket.OPEN) {
      websocket.value.send(blob);
    }
  }, 'image/jpeg', 0.95); // 发送高质量最终帧
};


const stopVerification = (reset = true) => {
  isVerifying.value = false;
  stopStreamingFrames();
  
  if (countdownTimer.value) {
    clearInterval(countdownTimer.value);
    countdownTimer.value = null;
  }

  if (websocket.value) {
    // 检查状态，避免在已关闭时再次关闭
    if (websocket.value.readyState === WebSocket.OPEN) {
      websocket.value.close();
    }
    websocket.value = null;
  }
  
  if(reset) {
    // 保留错误信息给用户看
    // errorMessage.value = '';
  }
};

const resetState = () => {
  errorMessage.value = '';
  statusMessage.value = '准备就绪';
  isVerifying.value = false;
  countdown.value = 15.0; // 重置为总时长
  if (countdownTimer.value) {
    clearInterval(countdownTimer.value);
    countdownTimer.value = null;
  }
};

const goToPasswordLogin = () => {
  router.push('/login');
};

onMounted(() => {
  initCamera();
});

onUnmounted(() => {
  stopVerification();
  if (stream.value) {
    stream.value.getTracks().forEach(track => track.stop());
  }
});
</script>

<style scoped>
.face-login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.face-login-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 40px;
  width: 420px;
  box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.18);
}

.title {
  font-size: 24px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.subtitle {
  font-size: 14px;
  color: #666;
  margin-bottom: 24px;
}

.video-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  background-color: #111;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 24px;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);
}

.video-feed {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scaleX(-1); /* 镜像翻转，符合用户照镜子的习惯 */
}

.video-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  pointer-events: none;
}

.face-guide-frame {
  width: 65%;
  height: 85%;
  border: 4px solid rgba(255, 255, 255, 0.8);
  border-radius: 50% / 40%;
  box-shadow: 0 0 0 999px rgba(0, 0, 0, 0.5);
  animation: pulse 2s infinite ease-in-out;
}

@keyframes pulse {
  0% { border-color: rgba(255, 255, 255, 0.8); }
  50% { border-color: rgba(68, 133, 255, 0.9); }
  100% { border-color: rgba(255, 255, 255, 0.8); }
}

.status-prompt {
  position: absolute;
  bottom: 20px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 16px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.status-prompt.success { background: #67C23A; }
.status-prompt.error { background: #F56C6C; }
.status-prompt.challenge {
  background-color: rgba(230, 162, 60, 0.8); /* 橙色背景以示挑战 */
}

.status-prompt.info {
  background-color: rgba(64, 158, 255, 0.8); /* 蓝色背景作为提示 */
}

.countdown-circle {
  position: absolute;
  top: 15px;
  right: 15px;
  width: 50px;
  height: 50px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.countdown-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}
.circle-bg {
  fill: none;
  stroke: rgba(255, 255, 255, 0.2);
  stroke-width: 3.8;
}
.circle {
  fill: none;
  stroke: #409eff;
  stroke-width: 4;
  stroke-linecap: round;
  transition: stroke-dasharray 0.1s linear;
}

.countdown-text {
  color: white;
  font-size: 16px;
  font-weight: bold;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0,0,0,0.6);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: white;
}

.spinner {
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-left-color: #fff;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.error-alert {
  margin-top: 20px;
}
</style> 