<template>
  <div class="face-login-container">
    <div class="face-login-card">
      <h2>人脸识别登录</h2>
      
      <!-- 视频预览区域 -->
      <div class="video-container">
        <video ref="videoElement" autoplay muted playsinline></video>
        <canvas ref="canvasElement" class="detection-canvas"></canvas>
        
        <!-- 活体检测指示和提示 -->
        <div v-if="isDetecting" class="detection-overlay">
          <div class="detection-prompt">
            {{ currentPrompt }}
          </div>
          <div class="detection-progress">
            <div class="progress-bar" :style="{ width: `${detectionProgress}%` }"></div>
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
        <button 
          @click="startDetection" 
          :disabled="isDetecting || loading"
          class="primary-button"
        >
          开始识别
        </button>
        <button @click="goToPasswordLogin" class="secondary-button">
          使用密码登录
        </button>
      </div>

      <!-- 错误信息 -->
      <div v-if="errorMessage" class="error-message">
        {{ errorMessage }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import api from '@/api';

// 路由和状态管理
const router = useRouter();
const authStore = useAuthStore();

// DOM引用
const videoElement = ref(null);
const canvasElement = ref(null);

// 状态变量
const stream = ref(null);
const isDetecting = ref(false);
const loading = ref(false);
const loadingMessage = ref('');
const errorMessage = ref('');
const currentPrompt = ref('请正视摄像头');
const detectionProgress = ref(0);

// --- 活体检测强化: 随机化动作序列 ---
let livenessFrames = []; // 用于存储活体检测的帧

const actionPool = [
  { prompt: '请眨眨眼睛', duration: 2500 },
  { prompt: '请向左转头', duration: 2500 },
  { prompt: '请向右转头', duration: 2500 },
  { prompt: '请张张嘴', duration: 2000 },
];

const shuffleArray = (array) => {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}

let detectionSteps = [];

const generateDetectionSteps = () => {
  const shuffledActions = shuffleArray([...actionPool]);
  const selectedActions = shuffledActions.slice(0, 3); // 始终随机选择3个动作

  detectionSteps = [
    { prompt: '请正视摄像头', duration: 2000 },
    ...selectedActions
  ];
};
// --- 活体检测强化结束 ---

const currentStepIndex = ref(0);
let detectionTimer = null;

const initCamera = async () => {
  try {
    loading.value = true;
    loadingMessage.value = '正在初始化摄像头...';
    stream.value = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
    });
    if (videoElement.value) {
      videoElement.value.srcObject = stream.value;
    }
    loading.value = false;
  } catch (error) {
    errorMessage.value = '无法访问摄像头，请确保已授予摄像头权限';
    loading.value = false;
  }
};

const startDetection = () => {
  if (!stream.value) {
    initCamera();
    return;
  }
  generateDetectionSteps();
  errorMessage.value = '';
  isDetecting.value = true;
  currentStepIndex.value = 0;
  detectionProgress.value = 0;
  livenessFrames = [];
  currentPrompt.value = detectionSteps[0].prompt;
  runDetectionStep();
};

const captureFrame = () => {
  if (!videoElement.value) return null;
  const canvas = canvasElement.value;
  const video = videoElement.value;
  const context = canvas.getContext('2d');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg').split(',')[1];
}

const runDetectionStep = () => {
  const currentStep = detectionSteps[currentStepIndex.value];
  const stepDuration = currentStep.duration;

  // 用setTimeout代替setInterval，确保动作完成后再捕获
  detectionTimer = setTimeout(() => {
    const frameData = captureFrame();
    if (frameData) {
      livenessFrames.push({
        action: currentStep.prompt,
        image_data: frameData,
        timestamp: Date.now() // 添加时间戳
      });
    }

    detectionProgress.value = ((currentStepIndex.value + 1) / detectionSteps.length) * 100;
    
    currentStepIndex.value++;
    if (currentStepIndex.value < detectionSteps.length) {
      currentPrompt.value = detectionSteps[currentStepIndex.value].prompt;
      runDetectionStep();
    } else {
      performFaceRecognition();
    }
  }, stepDuration);
};

const performFaceRecognition = async () => {
  try {
    loading.value = true;
    loadingMessage.value = '正在进行安全验证...';
    isDetecting.value = false;
    
    if (livenessFrames.length < detectionSteps.length) {
      errorMessage.value = "未能捕获所有活体检测图像，请重试。";
      loading.value = false;
      return;
    }
    
    const primaryImage = livenessFrames[0].image_data;
    
    const response = await api.auth.verifyFace({
      primary_image: primaryImage,
      liveness_frames: livenessFrames
    });
    
    if (response && response.data && response.data.success) {
      await authStore.login({
        access_token: response.data.token,
        refresh_token: response.data.refresh_token,
        user: response.data.user,
        face_auth: true
      });
      router.push('/dashboard');
    } else {
      errorMessage.value = (response && response.data && response.data.message) || '人脸识别失败，请重试';
      loading.value = false;
    }
  } catch (error) {
    let errorMsg = '人脸识别过程中发生错误，请重试';
    if (error.response && error.response.data && error.response.data.message) {
      errorMsg = error.response.data.message;
    }
    errorMessage.value = errorMsg;
    loading.value = false;
  }
};

const goToPasswordLogin = () => {
  router.push('/login');
};

const cleanup = () => {
  if (detectionTimer) clearTimeout(detectionTimer);
  if (stream.value) {
    stream.value.getTracks().forEach(track => track.stop());
    stream.value = null;
  }
};

onMounted(initCamera);
onUnmounted(cleanup);
</script>

<style scoped>
.face-login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f0f2f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.face-login-card {
  background: #fff;
  border-radius: 8px;
  padding: 30px;
  width: 400px;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
  text-align: center;
}

.face-login-card h2 {
  margin-bottom: 20px;
  color: #333;
}

.video-container {
  position: relative;
  width: 100%;
  height: 300px;
  background-color: #000;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 20px;
}

video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.detection-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.detection-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: rgba(0, 0, 0, 0.3);
  color: white;
}

.detection-prompt {
  font-size: 20px;
  font-weight: bold;
  margin-bottom: 20px;
  text-shadow: 0 0 5px rgba(0, 0, 0, 0.5);
}

.detection-progress {
  width: 80%;
  height: 10px;
  background-color: rgba(255, 255, 255, 0.3);
  border-radius: 5px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background-color: #1890ff;
  transition: width 0.3s;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: rgba(0, 0, 0, 0.7);
  color: white;
}

.spinner {
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-top: 4px solid #fff;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin-bottom: 15px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 15px;
  margin-bottom: 20px;
}

.primary-button, .secondary-button {
  padding: 10px 20px;
  border-radius: 4px;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.3s;
  border: none;
}

.primary-button {
  background-color: #1890ff;
  color: white;
}

.primary-button:hover {
  background-color: #40a9ff;
}

.primary-button:disabled {
  background-color: #b3d9ff;
  cursor: not-allowed;
}

.secondary-button {
  background-color: #f0f0f0;
  color: #666;
}

.secondary-button:hover {
  background-color: #e0e0e0;
}

.error-message {
  color: #f56c6c;
  margin-top: 15px;
}
</style> 