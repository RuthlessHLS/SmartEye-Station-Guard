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
import { ref, reactive, watch } from 'vue';
import axios from 'axios';

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

// --- Core Logic ---

// 从后端API获取验证码数据
const fetchCaptcha = async () => {
  loading.value = true;
  resetSlider(); // 重置滑块状态
  try {
    // 【重要】请将 URL 替换为你的后端 API 地址
    const response = await axios.get('http://127.0.0.1:8000/api/users/captcha/generate/');
    const data = response.data;
    captcha.backgroundImage = data.background_image;
    captcha.sliderImage = data.slider_image;
    captcha.sliderY = data.slider_y;
    captcha.captchaKey = data.captcha_key;
  } catch (error) {
    console.error('获取验证码失败:', error);
    // 这里可以添加用户友好的错误提示
  } finally {
    loading.value = false;
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

  // [新增] 计算拖动耗时
  const endTime = Date.now();
  const duration = (endTime - startTime) / 1000; // 转换为秒
  // 定义前端的最小耗时（可以比后端略短，给网络延迟留出空间）
  const minDuration = 0.8; // 例如，0.8秒
  if (duration < minDuration) {
    alert('操作过快，请拖动滑块完成验证！');
    // 操作过快时，重置滑块位置，并重新获取验证码以增加破解难度
    fetchCaptcha();
    // 不关闭模态框，也不触发 success 事件
    return;
  }

  // 触发 `success` 事件，将验证所需的数据传递给父组件
  emit('success', {
    captcha_key: captcha.captchaKey,
    captcha_position: sliderLeft.value,
  });

  // 验证成功后自动关闭模态框
  closeModal();
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
