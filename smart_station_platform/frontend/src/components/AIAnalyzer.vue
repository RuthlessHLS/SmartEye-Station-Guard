<template>
  <div class="ai-analyzer">
    <canvas ref="overlayCanvas" class="overlay-canvas" @click="handleCanvasClick"></canvas>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';

// --- 组件属性定义 ---
const props = defineProps({
  video: { type: [Object, null], default: null },
  cameraId: { type: String, required: true },
  enabled: { type: Boolean, default: false },
  realtimeMode: { type: Boolean, default: true },
  dangerZones: { type: Array, default: () => [] },
  currentZonePoints: { type: Array, default: () => [] },
  detectionResults: { type: Array, default: () => [] },
  localTrackingEnabled: { type: Boolean, default: false }
});

// --- 事件定义 ---
const emit = defineEmits(['detection-results', 'performance-stats', 'canvas-click']);

// --- 画布和状态相关引用 ---
const overlayCanvas = ref(null);
const canvasContext = ref(null);

// 【保留】这部分是正确的，用于存储从后端收到的AI分辨率
const aiImageSize = ref({ width: 1920, height: 1080 }); // 提供一个合理的默认值


// --- 【简化并保留】这部分函数不再被调用，可以安全移除 ---
/**
 * 此函数不再需要，因为新的 renderDetections 方法更简单高效
 */
/*
const mapBboxToCanvas = (bbox, originalSize, canvasWidth, canvasHeight) => {
  // ...
};
*/


/**
 * 【保留】此函数逻辑基本正确，无需大的改动
 */
const resizeCanvas = () => {
  if (!overlayCanvas.value || !props.video || !props.video.videoWidth) {
    return;
  }
  const videoEl = props.video;
  const canvasEl = overlayCanvas.value;

  // 直接使用视频的原始尺寸设置Canvas
  const videoWidth = videoEl.videoWidth;
  const videoHeight = videoEl.videoHeight;

  if (canvasEl.width !== videoWidth || canvasEl.height !== videoHeight) {
    canvasEl.width = videoWidth;
    canvasEl.height = videoHeight;
    console.log(`[AIAnalyzer] 画布已根据视频固有分辨率调整尺寸: ${videoWidth}x${videoHeight}`);

    // 同时保存这个分辨率作为AI图像尺寸
    aiImageSize.value = { width: videoWidth, height: videoHeight };

    // 使用nextTick确保DOM更新后再渲染
    nextTick(() => {
      // 尝试多次渲染，解决某些浏览器下Canvas初始化问题
      renderDetections(props.detectionResults);
      
      // 再次尝试渲染以确保显示正确
      setTimeout(() => {
        renderDetections(props.detectionResults);
      }, 100);
    });
  }
};

// 添加绘制时间戳的函数
const drawTimestamp = (frameId, videoTime, isSynchronized, timeDifference) => {
  if (!canvasContext.value || !overlayCanvas.value) return;
  
  const ctx = canvasContext.value;
  const canvas = overlayCanvas.value;
  
  // eslint-disable-next-line no-unused-vars
  const currentClientTime = Date.now();
  
  // 检查是否为最新帧（用于检测延迟）
  let isDelayed = false;
  // eslint-disable-next-line no-unused-vars
  let delayMs = 0;
  
  if (frameId && frameId.includes('_')) {
    const frameTimeParts = frameId.split('_');
    if (frameTimeParts.length >= 3) {
      // 从帧ID中提取时间信息（如果有）
      const frameNumber = parseInt(frameTimeParts[2]);
      
      // 检查是否有足够的帧信息判断延迟
      if (!isNaN(frameNumber)) {
        const expectedFrameNumber = frameNumber + 1;
        isDelayed = expectedFrameNumber - frameNumber > 5; // 如果差距超过5帧，认为有延迟
      }
    }
  }
  
  // 确定信息框大小
  const boxHeight = (isDelayed || !isSynchronized) ? 110 : 50;
  
  // 在画布右上角绘制时间戳信息
  ctx.save();
  
  // 绘制背景
  ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
  ctx.fillRect(canvas.width - 250, 10, 240, boxHeight);
  
  ctx.font = '12px Arial';
  ctx.fillStyle = '#FFFFFF';
  ctx.textAlign = 'right';
  
  // 显示帧ID和视频时间
  ctx.fillText(`帧ID: ${frameId || '未知'}`, canvas.width - 15, 25);
  ctx.fillText(`视频时间: ${videoTime.toFixed(2)}s`, canvas.width - 15, 45);
  
  // 如果检测到延迟，显示警告
  if (isDelayed) {
    ctx.fillStyle = '#FFFF00'; // 黄色警告
    ctx.fillText(`⚠️ 检测可能不同步！延迟超过5帧`, canvas.width - 15, 65);
  }
  
  // 显示同步状态
  if (!isSynchronized) {
    ctx.fillStyle = timeDifference > 1.0 ? '#FF6666' : '#FFFF00'; // 红色或黄色，取决于差异程度
    ctx.fillText(`⚠️ 视频/检测不同步: ${timeDifference.toFixed(2)}s`, canvas.width - 15, isDelayed ? 85 : 65);
    
    if (timeDifference > 1.0) {
      ctx.fillText(`建议: 尝试暂停后再播放`, canvas.width - 15, isDelayed ? 105 : 85);
    }
  }
  
  ctx.restore();
};

/**
 * 修改renderDetections函数，使用带时间戳的绘制算法
 */
const renderDetections = (detections) => {
  if (!canvasContext.value || !overlayCanvas.value || !props.video) {
    console.error('[AIAnalyzer] Canvas、上下文或视频元素不存在，无法渲染');
    return;
  }

  const canvas = overlayCanvas.value;
  const ctx = canvasContext.value;
  const video = props.video;
  
  // 清空画布
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  
  // 获取关键尺寸信息
  const videoOriginalWidth = video.videoWidth;
  const videoOriginalHeight = video.videoHeight;
  const canvasWidth = canvas.width;
  const canvasHeight = canvas.height;
  
  // 获取后端AI处理的原始分辨率
  const aiWidth = aiImageSize.value?.width || videoOriginalWidth;
  const aiHeight = aiImageSize.value?.height || videoOriginalHeight;
  
  console.log(`[AIAnalyzer] 坐标映射关系:`, {
    视频原始尺寸: `${videoOriginalWidth}x${videoOriginalHeight}`,
    Canvas尺寸: `${canvasWidth}x${canvasHeight}`,
    AI处理尺寸: `${aiWidth}x${aiHeight}`
  });
  
  // 【添加】先检查传入的detections是否为空
  if (!detections || detections.length === 0) {
    console.log('[AIAnalyzer] 没有检测结果可显示');
    return;
  }
  
  // 【新增】根据当前设置过滤检测结果
  let filteredDetections = [...detections];
  if (!props.enabled) {
    // 如果整个AI分析被禁用，则不显示任何检测框
    filteredDetections = [];
    console.log('[AIAnalyzer] AI分析已禁用，不显示检测框');
  } else {
    // 获取父组件传递的AI设置
    const aiSettings = typeof props.realtimeMode === 'object' ? props.realtimeMode : null;
    
    // 根据各功能的启用状态过滤检测结果
    filteredDetections = detections.filter(detection => {
      // 人脸检测过滤
      if (detection.type === 'face') {
        const faceEnabled = aiSettings?.faceRecognition !== false;
        if (!faceEnabled) {
          console.log('[AIAnalyzer] 过滤掉人脸检测框，因为人脸识别已禁用');
          return false;
        }
      }
      
      // 目标检测过滤
      if (detection.type === 'object') {
        const objectEnabled = aiSettings?.objectDetection !== false;
        if (!objectEnabled) {
          console.log('[AIAnalyzer] 过滤掉目标检测框，因为目标检测已禁用');
          return false;
        }
      }
      
      return true;
    });
    
    console.log('[AIAnalyzer] 过滤后的检测结果数量:', filteredDetections.length, '原始数量:', detections.length);
  }
  
  // 如果过滤后没有检测结果，则直接返回
  if (filteredDetections.length === 0) return;
  
  // 获取当前视频时间
  const currentVideoTime = video.currentTime;
  
  // 提取帧ID和时间戳
  let frameId = "unknown";
  // eslint-disable-next-line no-unused-vars
  let frameTimestamp = Date.now();
  let videoTimeFromDetection = null;
  
  // 从检测结果中获取帧信息
  if (filteredDetections.length > 0) {
    frameId = filteredDetections[0].frame_id || "unknown";
    frameTimestamp = filteredDetections[0].frame_timestamp || Date.now();
    // 使用后端传来的视频时间
    videoTimeFromDetection = filteredDetections[0].video_time;
  }
  
  // 检查视频时间和检测结果时间是否匹配
  let isSynchronized = true;
  let timeDifference = 0;
  
  if (videoTimeFromDetection !== null && currentVideoTime > 0) {
    // 计算实际视频播放时间与后端处理时间的差异
    timeDifference = Math.abs(currentVideoTime - videoTimeFromDetection);
    // 如果时间差超过1秒，认为不同步（调整为更合理的阈值）
    isSynchronized = timeDifference < 1.0;
    
    // 如果检测到严重不同步，记录警告
    if (timeDifference > 2.0) {
      console.warn(`[AIAnalyzer] 视频时间与检测结果时间严重不同步! 视频时间=${currentVideoTime.toFixed(2)}s, 
        检测时间=${videoTimeFromDetection.toFixed(2)}s, 差异=${timeDifference.toFixed(2)}s`);
    }
  } else if (currentVideoTime > 0 && filteredDetections.length > 0) {
    // 如果没有视频时间但有检测结果，标记为不同步
    isSynchronized = false;
    console.warn(`[AIAnalyzer] 检测结果缺少视频时间戳! 视频时间=${currentVideoTime.toFixed(2)}s`);
  }
  
  // 绘制时间戳信息，包括同步状态
  drawTimestamp(frameId, currentVideoTime, isSynchronized, timeDifference);
  
  // 使用更鲜明的颜色
  const typeColors = {
    'face': '#00FFFF', // 青色
    'person': '#FF0000', // 红色
    'car': '#00FF00', // 绿色
    'bottle': '#FFFF00', // 黄色
    'chair': '#FF00FF', // 紫色
    'default': '#FFFFFF' // 白色
  };
  
  // 计算视频显示区域尺寸和偏移量（处理视频黑边问题）
  const canvasRatio = canvasWidth / canvasHeight;
  const videoRatio = videoOriginalWidth / videoOriginalHeight;
  
  let displayWidth, displayHeight, offsetX, offsetY;
  
  if (canvasRatio >= videoRatio) {
    // Canvas较宽，视频高度填满
    displayHeight = canvasHeight;
    displayWidth = videoOriginalWidth * (canvasHeight / videoOriginalHeight);
    offsetX = (canvasWidth - displayWidth) / 2;
    offsetY = 0;
  } else {
    // Canvas较窄，视频宽度填满
    displayWidth = canvasWidth;
    displayHeight = videoOriginalHeight * (canvasWidth / videoOriginalWidth);
    offsetX = 0;
    offsetY = (canvasHeight - displayHeight) / 2;
  }
  
  // 计算缩放比例
  const scaleX = displayWidth / aiWidth;
  const scaleY = displayHeight / aiHeight;
  
  // 绘制每个检测框
  filteredDetections.forEach((detection, index) => {
    if (!detection.bbox || detection.bbox.length !== 4) return;
    
    // 获取原始坐标
    const [x1, y1, x2, y2] = detection.bbox;
    
    // 确认坐标值有效
    if (isNaN(x1) || isNaN(y1) || isNaN(x2) || isNaN(y2)) {
      console.warn(`[AIAnalyzer] 检测框 #${index} 坐标无效:`, detection.bbox);
      return;
    }
    
    // 计算宽高
    const width = x2 - x1;
    const height = y2 - y1;
    
    if (width <= 0 || height <= 0) {
      console.warn(`[AIAnalyzer] 检测框 #${index} 宽高无效: ${width}x${height}`);
      return;
    }
    
    // 映射坐标到Canvas，考虑视频黑边
    const scaledX = Math.round(x1 * scaleX + offsetX);
    const scaledY = Math.round(y1 * scaleY + offsetY);
    const scaledWidth = Math.round(width * scaleX);
    const scaledHeight = Math.round(height * scaleY);
    
    // 仅对第一个检测框输出详细日志
    if (index === 0) {
      console.log(`[AIAnalyzer] 检测框 #${index} 详情:`, {
        AI坐标: `(${x1}, ${y1}, ${x2}, ${y2})`,
        Canvas坐标: `(${scaledX}, ${scaledY}, ${scaledX + scaledWidth}, ${scaledY + scaledHeight})`,
        缩放比例: `X=${scaleX.toFixed(3)}, Y=${scaleY.toFixed(3)}`,
        偏移量: `X=${offsetX.toFixed(0)}, Y=${offsetY.toFixed(0)}`,
        帧ID: detection.frame_id || '未知',
        视频时间: currentVideoTime.toFixed(2) + 's',
        同步状态: isSynchronized ? '同步' : '不同步',
        时间差: timeDifference.toFixed(2) + 's'
      });
    }
    
    // 确定颜色 - 基于对象类型
    let color = typeColors.default;
    let objectType = '';
    
    if (detection.type === 'face') {
      color = typeColors.face;
      objectType = detection.identity?.name || '人脸';
      
      // 根据人脸置信度设置不同的颜色
      if (detection.identity) {
        const confidence = detection.identity.confidence || 0;
        const isKnown = detection.identity.is_known || false;
        const shouldAlert = detection.identity.should_alert || false;
        
        if (isKnown) {
          // 已知人员 - 青色
          color = '#00FFFF';
        } else if (shouldAlert) {
          // 需要告警的未知人员 - 红色
          color = '#FF0000';
          objectType = '未知人员(告警)';
        } else if (confidence >= 0.4 && confidence < 0.5) {
          // 置信度在40%-50%之间的未知人员 - 黄色
          color = '#FFFF00';
          objectType = '未知人员(低置信度)';
        } else {
          // 其他未知人员 - 橙色
          color = '#FFA500';
          objectType = '未知人员';
        }
      }
    } else if (detection.class_name) {
      color = typeColors[detection.class_name.toLowerCase()] || typeColors.default;
      objectType = detection.class_name;
    } else if (detection.type) {
      color = typeColors[detection.type.toLowerCase()] || typeColors.default;
      objectType = detection.type;
    }
    
    // 如果检测到不同步，使边框颜色变淡
    if (!isSynchronized) {
      // 添加50%透明度
      color = color + '80';
    }
    
    // 信息显示
    let label = objectType;
    if (detection.confidence) {
      label += ` (${Math.round(detection.confidence * 100)}%)`;
    } else if (detection.identity?.confidence) {
      label += ` (${Math.round(detection.identity.confidence * 100)}%)`;
    }
    
    // 增强边框可见性 - 使用双边框技术
    
    // 绘制半透明填充
    ctx.fillStyle = color + '20'; // 透明度调整为20%
    ctx.fillRect(scaledX, scaledY, scaledWidth, scaledHeight);
    
    // 外边框 - 黑色，增强可见性
    ctx.strokeStyle = 'black';
    ctx.lineWidth = 4;
    ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);
    
    // 内边框 - 彩色，表示对象类型
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);
    
    // 绘制标签
    if (label) {
      // 测量文本宽度
      ctx.font = 'bold 16px Arial';
      const textWidth = ctx.measureText(label).width;
      const textHeight = 20;
      
      // 标签位置 - 优先显示在目标上方
      const textX = Math.max(0, Math.min(scaledX, canvasWidth - textWidth - 6));
      const textY = scaledY > 30 ? scaledY - 10 : scaledY + scaledHeight + 20;
      
      // 绘制标签背景
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(textX, textY - 18, textWidth + 10, textHeight);
      
      // 绘制文本
      ctx.fillStyle = 'white';
      ctx.fillText(label, textX + 5, textY - 4);
    }
  });
};

// --- 其他函数 (基本保持不变) ---

const handleCanvasClick = (event) => {
  if (!overlayCanvas.value) return;
  const rect = overlayCanvas.value.getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width;
  const y = (event.clientY - rect.top) / rect.height;
  emit('canvas-click', { x, y, originalEvent: event });
};


// --- 生命周期和侦听器 (基本保持不变) ---

onMounted(() => {
  if (overlayCanvas.value) {
    canvasContext.value = overlayCanvas.value.getContext('2d');
  }
  window.addEventListener('resize', resizeCanvas);
});

onUnmounted(() => {
  window.removeEventListener('resize', resizeCanvas);
  if (props.video) {
    props.video.removeEventListener('loadedmetadata', resizeCanvas);
    props.video.removeEventListener('playing', resizeCanvas);
  }
});

// 添加缺失的函数
const startAnalysis = () => {
  console.log('[AIAnalyzer] 开始AI分析');
  renderDetections(props.detectionResults);
};

const stopAnalysis = () => {
  console.log('[AIAnalyzer] 停止AI分析');
  if (canvasContext.value && overlayCanvas.value) {
    canvasContext.value.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height);
  }
};

const clearCanvas = () => {
  if (canvasContext.value && overlayCanvas.value) {
    canvasContext.value.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height);
  }
};

watch(() => props.video, (newVideo, oldVideo) => {
    if (oldVideo) {
        oldVideo.removeEventListener('loadedmetadata', resizeCanvas);
        oldVideo.removeEventListener('playing', resizeCanvas);
    }
    
    if (newVideo) {
        // 监听视频加载元数据事件
        newVideo.addEventListener('loadedmetadata', resizeCanvas);
        
        // 监听视频开始播放事件
        newVideo.addEventListener('playing', resizeCanvas);
        
        // 立即尝试调整Canvas大小
        nextTick(resizeCanvas);
        
        // 多次尝试调整，确保视频完全加载后Canvas也能正确调整
        setTimeout(resizeCanvas, 500);
        setTimeout(resizeCanvas, 1000);
        setTimeout(resizeCanvas, 3000);
    }
});

watch(() => props.detectionResults, (newResults) => {
  renderDetections(newResults);
}, { deep: true });

// ... 其他 watchers 保持不变 ...


// --- Expose ---
defineExpose({
  startAnalysis,
  stopAnalysis,
  clearCanvas,
  renderDetections,
  resizeCanvas,
  drawTimestamp,
  setAiImageSize: (size) => {
    console.log('[AIAnalyzer] 接收到父组件设置的原始分辨率:', size);
    if(size && size.width && size.height) {
        const oldSize = { ...aiImageSize.value };
        aiImageSize.value = size;
        console.log('[AIAnalyzer] 原始分辨率已更新:', { 旧值: oldSize, 新值: size });
        
        // 如果视频元素和Canvas已经存在，尝试调整Canvas尺寸
        nextTick(() => {
          if (props.video && overlayCanvas.value) {
            console.log('[AIAnalyzer] 分辨率更新后尝试调整Canvas尺寸');
            resizeCanvas();
          }
          
          // 立即重新渲染当前检测结果
          if (props.detectionResults && props.detectionResults.length > 0) {
            console.log('[AIAnalyzer] 分辨率更新后重新渲染检测框');
            renderDetections(props.detectionResults);
          }
        });
    }
  }
});
</script>

<style scoped>
.ai-analyzer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 20; /* 确保在视频之上，但在DPlayer控制器之下 */
  pointer-events: auto; /* 【改动】允许点击事件传递，确保检测框正确定位 */
}

.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: auto; /* 【保留】允许画布自身接收点击事件以绘制危险区域等 */

  /* 【关键样式】确保画布的缩放方式与视频一致 */
  object-fit: contain;
}

/* 【保留】这些深度选择器有助于确保DPlayer的兼容性 */
:deep(.dplayer-video-wrap) {
  position: relative;
  overflow: visible !important;
}

:deep(.dplayer-container video) {
  object-fit: contain !important;
}

:deep(.dplayer-controller) {
  z-index: 40 !important;
}
</style>
