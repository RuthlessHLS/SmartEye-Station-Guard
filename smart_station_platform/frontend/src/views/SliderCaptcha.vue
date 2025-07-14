<template>
  <!-- 遮罩层，覆盖整个页面 -->
  <div class="captcha-overlay" @click.self="closeModal">
    <!-- 验证码主容器 -->
    <div class="captcha-container">
      <!-- 头部：标题和刷新按钮 -->
      <div class="captcha-header">
        <span class="captcha-title">请完成安全验证</span>
        <button @click="fetchCaptcha" class="refresh-btn" title="刷新">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-arrow-repeat" viewBox="0 0 16 16">
            <path d="M11.534 7h3.932a.25.25 0 0 1 .192.41l-1.966 2.36a.25.25 0 0 1-.384 0l-1.966-2.36a.25.25 0 0 1 .192-.41zm-11 2h3.932a.25.25 0 0 0 .192-.41L2.692 6.23a.25.25 0 0 0-.384 0L.342 8.59A.25.25 0 0 0 .534 9z"/>
            <path fill-rule="evenodd" d="M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 1 1-.771-.636A6.002 6.002 0 0 1 13.917 7H12.5A5.002 5.002 0 0 0 8 3zM3.5 12.5A5.002 5.002 0 0 0 8 15c1.552 0 2.94-.707 3.857-1.818a.5.5 0 1 1 .771.636A6.002 6.002 0 0 1 2.083 9H3.5a5.002 5.002 0 0 0 0 3.5z"/>
          </svg>
        </button>
      </div>

      <!-- 主体：图片和加载提示 -->
      <div class="captcha-body">
        <div v-if="loading" class="loading-container">
          <div class="spinner"></div>
          <p>加载中...</p>
        </div>
        <div v-if="!loading && captcha.backgroundImage"
             class="image-container"
             :style="{ height: `${imageHeight}px` }">
          <!-- 背景图 -->
          <img :src="captcha.backgroundImage" alt="captcha background" class="background-image" />
          <!-- 滑块图 -->
          <img :src="captcha.sliderImage" alt="slider piece" class="slider-image"
               :style="{ top: `${captcha.sliderY}px`, left: `${sliderLeft}px` }" />
        </div>
      </div>

      <!-- 底部：滑动轨道 -->
      <div class="slider-track" ref="trackRef">
        <div class="slider-progress" :style="{ width: `${sliderLeft + 10}px` }"></div>
        <div class="slider-handle"
             :style="{ left: `${sliderLeft}px` }"
             @mousedown.prevent="onDragStart"
             @touchstart.prevent="onDragStart">
          <span class="handle-icon">→</span>
        </div>
        <div class="slider-text" :style="{ opacity: isDragging ? 0 : 1 }">
          向右滑动填充拼图
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue';
import axios from 'axios';
// 导入 API 客户端
import api from '@/api';
import { ElMessage } from 'element-plus'; // 导入 ElMessage

// --- Props and Emits ---
// `v-model:visible` 用于父组件控制此模态框的显示/隐藏
const props = defineProps({
  visible: Boolean,
});
const emit = defineEmits(['update:visible', 'success']);

// --- State Management ---
const loading = ref(false); // 初始不加载，等watcher触发时再设置为true
const imageHeight = 150; // 图片高度，应与后端生成的一致
const trackRef = ref(null); // 滑动轨道的DOM引用

// 响应式对象，存储从后端获取的验证码数据
const captcha = reactive({
  backgroundImage: '',
  sliderImage: '',
  sliderY: 0,
  captchaKey: '',
});

// 滑块的实时状态
const sliderLeft = ref(0);
const isDragging = ref(false);
let startX = 0; // 拖动开始时的鼠标X坐标

const imageWidth = ref(320); // 图片实际宽度
const trackWidth = ref(0); // 轨道宽度

// 添加重试相关的状态
const maxRetries = 3;
const retryCount = ref(0);
const retryDelay = 1000; // 1秒

// 计算滑块位置相对于原图的比例
const calculateActualPosition = (trackPosition) => {
  if (!trackWidth.value) return 0;
  
  // 滑块宽度
  const SLIDER_WIDTH = 40;
  
  // 计算可滑动区域的宽度（轨道宽度减去滑块宽度）
  const slidableWidth = trackWidth.value - SLIDER_WIDTH;
  
  // 计算图片可用宽度（图片宽度减去滑块宽度）
  const usableImageWidth = imageWidth.value - SLIDER_WIDTH;
  
  // 计算比例
  const ratio = usableImageWidth / slidableWidth;
  
  // 计算实际位置，并确保在有效范围内
  const actualPosition = Math.round(trackPosition * ratio);
  
  // 确保位置在有效范围内
  return Math.max(0, Math.min(actualPosition, usableImageWidth));
};

// 在组件挂载后获取轨道宽度
onMounted(() => {
  if (trackRef.value) {
    trackWidth.value = trackRef.value.clientWidth;
  }
});

// --- Core Logic ---

// 从后端API获取验证码数据
const fetchCaptcha = async () => {
  loading.value = true;
  resetSlider(); // 重置滑块状态
  
  try {
    const response = await api.auth.getCaptcha();
    console.log('验证码响应数据:', response); // 调试日志
    
    if (!response || !response.data) {
      throw new Error('未收到验证码数据');
    }

    const data = response.data;

    // 检查必需字段
    const requiredFields = ['background_image', 'slider_image', 'slider_y', 'captcha_key'];
    const missingFields = requiredFields.filter(field => !data[field]);
    
    if (missingFields.length > 0) {
      throw new Error(`验证码数据缺少必需字段: ${missingFields.join(', ')}`);
    }

    // 重置重试计数
    retryCount.value = 0;

    // 创建图片对象以获取实际尺寸
    const img = new Image();
    img.onload = () => {
      imageWidth.value = img.width;
      // 更新验证码数据
      captcha.backgroundImage = data.background_image;
      captcha.sliderImage = data.slider_image;
      captcha.sliderY = data.slider_y;
      captcha.captchaKey = data.captcha_key;
      loading.value = false;
    };
    img.onerror = () => {
      throw new Error('验证码图片加载失败');
    };
    img.src = data.background_image;

  } catch (error) {
    console.error('获取验证码失败:', error);
    let errorMessage = '获取验证码失败';
    
    if (error.response) {
      if (error.response.status === 500) {
        errorMessage = '服务器内部错误，请稍后重试';
      } else {
        errorMessage = error.response.data?.detail || error.response.data?.error || '请求验证码失败';
      }
    } else if (error.message) {
      errorMessage = error.message;
    }
    
    // 处理重试逻辑
    if (retryCount.value < maxRetries) {
      retryCount.value++;
      console.log(`验证码获取失败，${retryDelay/1000}秒后进行第${retryCount.value}次重试`);
      setTimeout(fetchCaptcha, retryDelay);
    } else {
      ElMessage.error(errorMessage);
      loading.value = false;
      closeModal();
    }
  }
};

let startTime = 0; // 用于记录拖动开始的时间戳

// 重置滑块状态
const resetSlider = () => {
  sliderLeft.value = 0;
  isDragging.value = false;
};

// --- Event Handlers ---

// 拖动开始
const onDragStart = (e) => {
  if (loading.value) return;
  isDragging.value = true;
  // 兼容触摸和鼠标事件，获取起始X坐标
  startX = e.clientX || e.touches[0].clientX;
  // 记录开始拖动的时间
  startTime = Date.now();

  // 添加全局事件监听器，以便在页面任何位置移动都能响应
  window.addEventListener('mousemove', onDragMove);
  window.addEventListener('touchmove', onDragMove);
  window.addEventListener('mouseup', onDragEnd);
  window.addEventListener('touchend', onDragEnd);
};

// 拖动中
const onDragMove = (e) => {
  if (!isDragging.value) return;
  const currentX = e.clientX || e.touches[0].clientX;
  const diffX = currentX - startX;

  // 获取轨道的最大可滑动宽度
  const maxLeft = trackRef.value.clientWidth - 40; // 40 是滑块的宽度

  let newLeft = diffX;
  // 边界检查，防止滑块超出轨道
  if (newLeft < 0) newLeft = 0;
  if (newLeft > maxLeft) newLeft = maxLeft;

  sliderLeft.value = newLeft;
};

// 拖动结束
const onDragEnd = () => {
  if (!isDragging.value) return;
  isDragging.value = false;

  // 移除全局事件监听器
  window.removeEventListener('mousemove', onDragMove);
  window.removeEventListener('touchmove', onDragMove);
  window.removeEventListener('mouseup', onDragEnd);
  window.removeEventListener('touchend', onDragEnd);

  // 计算拖动耗时
  const endTime = Date.now();
  const duration = (endTime - startTime) / 1000;
  const minDuration = 1.0; // 与后端保持一致
  
  if (duration < minDuration) {
    ElMessage.warning('请稍慢一些完成验证');
    resetSlider();
    return;
  }

  // 计算实际的验证位置
  const actualPosition = calculateActualPosition(sliderLeft.value);
  
  // 触发 success 事件
  emit('success', {
    captcha_key: captcha.captchaKey,
    captcha_position: actualPosition,
  });

  // 验证成功后自动关闭模态框
  closeModal();
};

// 重置验证码
const resetCaptcha = () => {
  resetSlider();
  fetchCaptcha();
};

// 监听验证失败事件
const onValidationFailed = () => {
  resetSlider();
  fetchCaptcha();
};

// 关闭模态框
const closeModal = () => {
  emit('update:visible', false);
};

// --- Watcher ---
// 监听 `visible` prop 的变化，当模态框变为可见时，自动获取新的验证码
watch(() => props.visible, (newVal) => {
  if (newVal) {
    fetchCaptcha();
  }
}, { immediate: true }); // 添加 immediate: true，确保初始化时也会执行

</script>

<style scoped>
.captcha-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  user-select: none; /* 防止拖动时选中文字 */
}

.captcha-container {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  width: 320px;
  box-shadow: 0 4px 15px rgba(0,0,0,0.2);
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.captcha-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.captcha-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.refresh-btn {
  border: none;
  background: #f0f0f0;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  color: #666;
  transition: transform 0.3s, background-color 0.2s;
}
.refresh-btn:hover {
  background-color: #e0e0e0;
}
.refresh-btn:active {
  transform: rotate(180deg);
}

.captcha-body {
  position: relative;
  width: 100%;
  height: 150px;
  background-color: #f7f7f7;
}

.loading-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: #888;
}

.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3498db;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.image-container {
  position: relative;
  width: 100%;
  overflow: hidden;
}
.background-image {
  width: 100%;
  height: 100%;
  display: block;
}
.slider-image {
  position: absolute;
  width: 40px; /* 必须与后端生成的大小一致 */
  height: 40px;
  border: 1px solid #fff; /* 添加白色边框使其更醒目 */
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.5);
}

.slider-track {
  position: relative;
  height: 40px;
  background-color: #e8e8e8;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  overflow: hidden; /* 隐藏 progress 的溢出部分 */
}

.slider-progress {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background-color: #d1e9ff;
  border-radius: 20px;
}

.slider-handle {
  position: absolute;
  left: 0;
  top: 0;
  width: 40px;
  height: 40px;
  background-color: #1890ff;
  border: 2px solid #fff;
  border-radius: 50%;
  cursor: grab;
  display: flex;
  justify-content: center;
  align-items: center;
  color: white;
  font-size: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
  box-sizing: border-box;
  z-index: 10;
}
.slider-handle:active {
  cursor: grabbing;
}

.slider-text {
  transition: opacity 0.2s;
}
</style>
