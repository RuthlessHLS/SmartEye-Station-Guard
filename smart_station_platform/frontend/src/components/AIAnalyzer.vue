<template>
  <div class="ai-analyzer">
    <canvas ref="overlayCanvas" class="overlay-canvas" @click="handleCanvasClick"></canvas>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue' // 【修改】移除了 computed 导入
import { useAIAnalysis } from '@/composables/useAIAnalysis'
import { useLocalTracking } from '@/composables/useLocalTracking'
import { ElMessage } from 'element-plus'

// 组件属性定义
const props = defineProps({
  // 视频元素引用
  video: {
    type: [Object, null],
    required: false,
    default: null
  },
  // 摄像头ID
  cameraId: {
    type: String,
    required: true
  },
  // 是否启用AI分析 (指后端AI服务)
  enabled: {
    type: Boolean,
    default: false
  },
  // 是否使用实时模式（更高频率发送帧到后端，但后端现在是拉取模式，这个属性主要用于本地处理的帧率控制）
  realtimeMode: {
    type: Boolean,
    default: true
  },
  // 危险区域配置
  dangerZones: {
    type: Array,
    default: () => []
  },
  // 当前正在编辑的区域点
  currentZonePoints: {
    type: Array,
    default: () => []
  },
  // 外部传入的检测结果（从后端通过WebSocket接收）
  detectionResults: {
    type: Array,
    default: () => []
  },
  // 是否启用本地跟踪（由 AIVideoMonitor.vue 控制并传入）
  localTrackingEnabled: {
    type: Boolean,
    default: false
  }
})

// 事件定义
const emit = defineEmits([
  'detection-results',  // 检测结果事件
  'performance-stats',  // 性能统计事件
  'canvas-click'        // 画布点击事件
])

// 画布相关引用
const overlayCanvas = ref(null)
const canvasContext = ref(null)
const canvasWidth = ref(0)
const canvasHeight = ref(0)

// 帧处理状态
let isProcessingFrame = false
let analysisTimer = null // 用于控制前端帧捕获和绘制的定时器

// 使用AI分析组合式API (不再用于发送帧，而是管理后端AI状态和接收其性能数据)
// 【修复 ESLint no-empty-pattern】如果没有直接使用的暴露变量，则无需解构
useAIAnalysis(props.cameraId)

// 使用本地目标跟踪组合式API
const {
  localDetections,
  isModelLoaded,
  isModelLoading,
  loadModel: loadLocalTrackingModel,
  processFrame: processLocalFrame,
  updateServerDetections, // 【修复 ESLint no-unused-vars】这个现在会被使用
  getPerformanceStats: getLocalTrackingStats,
  setTrackingEnabled
} = useLocalTracking()

/**
 * 捕获视频帧
 * 从视频元素中提取当前帧并绘制到画布。
 * 如果启用了本地跟踪，则进行本地处理。
 */
const captureFrame = async () => {
  if (!props.video || props.video.paused || props.video.ended || !canvasContext.value) {
    // 如果视频未就绪或组件未启用，则跳过
    return
  }

  // 避免在处理上一帧时再次捕获
  if (isProcessingFrame) {
    return
  }
  isProcessingFrame = true

  try {
    const ctx = canvasContext.value
    const videoWidth = props.video.videoWidth || props.video.width || 640
    const videoHeight = props.video.videoHeight || props.video.height || 480

    if (videoWidth === 0 || videoHeight === 0) {
      console.warn('视频尺寸无效，跳过帧捕获')
      isProcessingFrame = false
      return
    }

    // 确保 Canvas 尺寸正确
    if (overlayCanvas.value.width !== videoWidth || overlayCanvas.value.height !== videoHeight) {
      resizeCanvas()
    }

    // 将视频帧绘制到 Canvas 上
    ctx.drawImage(props.video, 0, 0, videoWidth, videoHeight)

    // 【核心修改】只在启用本地跟踪时才进行本地检测和处理
    if (props.localTrackingEnabled) {
      const results = await processLocalFrame(props.video)
      if (results && results.length > 0) {
        // 本地检测结果在 useLocalTracking 中更新 localDetections
        // renderDetections 会使用 localDetections
      }
      // 更新本地跟踪的性能统计
      emit('performance-stats', getLocalTrackingStats())
    }
    // 【修改】移除了此处将帧发送到后端服务器的 canvas.toBlob() 和 handleFrame() 调用
    // 因为后端AI服务现在是主动从流中拉取帧进行分析的。

  } catch (error) {
    console.error('帧捕获或本地处理失败:', error)
  } finally {
    isProcessingFrame = false
  }

  // 【修复 ReferenceError: drawOverlays is not defined】
  // 在这里调用实际的绘制函数 renderDetections
  // 根据 localTrackingEnabled 状态选择绘制本地检测结果或服务器检测结果
  renderDetections(props.localTrackingEnabled ? localDetections.value : props.detectionResults)
}

/**
 * 启动分析循环
 * 设置定时器定期捕获和分析视频帧
 */
const startAnalysis = () => {
  if (!props.video) {
    console.warn("视频元素未就绪，无法启动分析循环。");
    return;
  }

  if (analysisTimer) {
    clearInterval(analysisTimer);
  }

  // 根据 realtimeMode 控制前端帧捕获和绘制频率
  const interval = props.realtimeMode ? 1000 / 20 : 1000 / 10; // 20 FPS 或 10 FPS
  analysisTimer = setInterval(captureFrame, interval);
  console.log(`前端分析/渲染循环已启动，帧间隔: ${interval}ms`);

  // 控制本地跟踪模型的启停和加载
  if (props.localTrackingEnabled) {
    setTrackingEnabled(true); // 启用本地跟踪器的内部逻辑
    if (!isModelLoaded.value && !isModelLoading.value) {
      console.log('🧠 正在加载本地跟踪模型...');
      loadLocalTrackingModel().then(() => {
        if (isModelLoaded.value) {
          console.log('✅ 本地跟踪模型加载完成。');
        } else {
          console.warn('⚠️ 本地跟踪模型加载失败，请检查网络或模型路径。');
          ElMessage.error('本地模型加载失败，请检查网络或刷新页面。');
          setTrackingEnabled(false); // 加载失败则禁用本地跟踪
        }
      }).catch(error => {
        console.error('❌ 本地模型加载过程中发生错误:', error);
        ElMessage.error('本地模型加载异常，将禁用本地跟踪。');
        setTrackingEnabled(false); // 异常则禁用本地跟踪
      });
    }
  } else {
    setTrackingEnabled(false); // 禁用本地跟踪器的内部逻辑
  }
};

/**
 * 停止分析循环
 * 清理定时器和资源
 */
const stopAnalysis = () => {
  if (analysisTimer) {
    clearInterval(analysisTimer)
    analysisTimer = null
  }
  setTrackingEnabled(false) // 禁用本地跟踪
  clearCanvas()
  console.log("前端分析/渲染循环已停止。")
}

/**
 * 清空画布
 */
const clearCanvas = () => {
  if (canvasContext.value) {
    canvasContext.value.clearRect(0, 0, canvasWidth.value, canvasHeight.value)
  }
}

/**
 * 渲染检测框
 * * @param {Array} detections 检测结果数组
 */
const renderDetections = (detections) => {
  if (!canvasContext.value || !overlayCanvas.value) return

  // 清空画布
  clearCanvas()

  // 获取画布尺寸
  const canvas = overlayCanvas.value
  const ctx = canvasContext.value

  // 首先绘制危险区域
  renderDangerZones(ctx, canvas.width, canvas.height)

  // 绘制当前正在编辑的区域
  renderCurrentZonePoints(ctx)

  // 如果没有检测结果，直接返回
  if (!detections || detections.length === 0) return

  // 遍历所有检测结果并绘制
  detections.forEach(detection => {
    // 【修复】 兼容后端返回的字段 (class_name, name)，并提供默认值
    const {
      bbox,
      type,
      label: detectionLabel,
      class_name,
      name,
      confidence,
      color,
      is_dangerous,
      face_name: detectionFaceName
    } = detection

    // 如果没有边界框数据，跳过
    if (!bbox || bbox.length !== 4) return

    // 确定显示的标签和人脸名称
    const label = detectionLabel || class_name || name || '检测目标'
    const face_name = detectionFaceName || (type === 'face' ? name : null)


    // 从AI处理的图像尺寸映射到当前画布尺寸
    // 注意：这里的 ai_image_size 应该是后端检测结果带回的，或者通过 props.video 获取
    // 为了简化，这里直接使用 video 元素的实际尺寸进行映射
    const aiImageSize = props.video ? { width: props.video.videoWidth, height: props.video.videoHeight } : { width: 640, height: 480 };

    // 【修复边界框尺寸计算】
    const [x, y, w, h] = mapBboxToCanvas(bbox, aiImageSize, canvas.width, canvas.height)

    // 设置样式
    // 根据 is_dangerous 决定颜色
    ctx.lineWidth = 2
    ctx.strokeStyle = is_dangerous ? '#ff0000' : (detection.color || '#22c55e') // 危险区域红色，否则绿色

    // 绘制边界框
    ctx.beginPath()
    ctx.rect(x, y, w, h)
    ctx.stroke()

    // 绘制标签背景
    const confidenceText = confidence ? ` ${(confidence * 100).toFixed(1)}%` : ''
    // 【修改】根据类型选择正确的标签（对象使用 class_name，人脸使用 name）
    const labelText = `${label}${confidenceText}`
    const textWidth = ctx.measureText(labelText).width + 10

    ctx.fillStyle = is_dangerous ? 'rgba(239, 68, 68, 0.7)' : 'rgba(34, 197, 94, 0.7)'
    ctx.fillRect(x, y - 25, textWidth, 25) // 调整背景高度和位置

    // 绘制标签文本
    ctx.fillStyle = '#ffffff'
    ctx.font = '14px Arial' // 调整字体大小
    ctx.fillText(labelText, x + 5, y - 8)

    // 如果是人脸检测结果，添加额外信息 (face_name)
    // 【修改】使用 name 字段，并显示区域名称
    if (type === 'face' && face_name) {
      const faceText = face_name === 'unknown' ? '未知人员' : face_name
      ctx.fillStyle = 'rgba(59, 130, 246, 0.7)'
      ctx.fillRect(x, y + h, ctx.measureText(faceText).width + 10, 25) // 调整背景高度和位置
      ctx.fillStyle = '#ffffff'
      ctx.fillText(faceText, x + 5, y + h + 18) // 调整文本位置
    } else if (is_dangerous && zone_name) { // 如果是危险区域的人员，显示区域名称
        const dangerZoneText = `区域: ${zone_name}`
        ctx.fillStyle = 'rgba(239, 68, 68, 0.7)'
        ctx.fillRect(x, y + h, ctx.measureText(dangerZoneText).width + 10, 25)
        ctx.fillStyle = '#ffffff'
        ctx.fillText(dangerZoneText, x + 5, y + h + 18)
    }
  })
}

/**
 * 将AI检测的边界框坐标映射到当前画布尺寸
 * * @param {Array} bbox 原始边界框坐标 [x1, y1, x2, y2]
 * @param {Object} aiImageSize AI处理的图像尺寸 { width, height }
 * @param {number} canvasWidth 当前画布宽度
 * @param {number} canvasHeight 当前画布高度
 * @returns {Array} 映射后的边界框坐标 [x, y, width, height]
 */
const mapBboxToCanvas = (bbox, aiImageSize, canvasWidth, canvasHeight) => {
  // 【修复】后端传的是 [x1, y1, x2, y2]，需要计算 width 和 height
  const [x1, y1, x2, y2] = bbox

  // 计算缩放比例
  const scaleX = canvasWidth / aiImageSize.width
  const scaleY = canvasHeight / aiImageSize.height

  // 应用缩放并计算正确的宽度和高度
  return [
    x1 * scaleX,
    y1 * scaleY,
    (x2 - x1) * scaleX,
    (y2 - y1) * scaleY
  ]
}

/**
 * 渲染危险区域
 * * @param {CanvasRenderingContext2D} ctx 画布上下文
 * @param {number} width 画布宽度
 * @param {number} height 画布高度
 */
const renderDangerZones = (ctx, width, height) => {
  if (!props.dangerZones || props.dangerZones.length === 0) return

  props.dangerZones.forEach(zone => {
    if (!zone.points || zone.points.length < 3) return

    // 设置样式
    ctx.fillStyle = zone.color || 'rgba(239, 68, 68, 0.2)' // 红色半透明
    ctx.strokeStyle = zone.borderColor || 'rgba(239, 68, 68, 0.8)'
    ctx.lineWidth = 2

    // 开始绘制多边形
    ctx.beginPath()

    // 将区域点映射到画布尺寸
    const mappedPoints = zone.points.map(point => ({
      x: point.x * width,
      y: point.y * height
    }))

    // 移动到第一个点
    ctx.moveTo(mappedPoints[0].x, mappedPoints[0].y)

    // 绘制其余点
    for (let i = 1; i < mappedPoints.length; i++) {
      ctx.lineTo(mappedPoints[i].x, mappedPoints[i].y)
    }

    // 闭合路径
    ctx.closePath()

    // 填充和描边
    ctx.fill()
    ctx.stroke()

    // 绘制区域名称
    if (zone.name) {
      const centerX = mappedPoints.reduce((sum, p) => sum + p.x, 0) / mappedPoints.length
      const centerY = mappedPoints.reduce((sum, p) => sum + p.y, 0) / mappedPoints.length

      ctx.fillStyle = '#ffffff'
      ctx.font = '12px Arial'
      ctx.textAlign = 'center'
      ctx.fillText(zone.name, centerX, centerY)
      ctx.textAlign = 'left' // 重置对齐方式
    }
  })
}

/**
 * 渲染当前正在编辑的区域点
 * * @param {CanvasRenderingContext2D} ctx 画布上下文
 */
const renderCurrentZonePoints = (ctx) => {
  if (!props.currentZonePoints || props.currentZonePoints.length === 0) return

  // 设置样式
  ctx.fillStyle = 'rgba(59, 130, 246, 0.2)' // 蓝色半透明
  ctx.strokeStyle = 'rgba(59, 130, 246, 0.8)'
  ctx.lineWidth = 2

  // 绘制已有的点
  props.currentZonePoints.forEach((point, index) => {
    ctx.beginPath()
    ctx.arc(point.x * canvasWidth.value, point.y * canvasHeight.value, 5, 0, Math.PI * 2)
    ctx.fill()

    // 绘制点的索引
    ctx.fillStyle = '#ffffff'
    ctx.font = '12px Arial'
    ctx.fillText(index + 1, point.x * canvasWidth.value + 8, point.y * canvasHeight.value + 4)
    ctx.fillStyle = 'rgba(59, 130, 246, 0.2)' // 重置填充颜色
  })

  // 如果有多个点，连接它们
  if (props.currentZonePoints.length > 1) {
    ctx.beginPath()
    ctx.moveTo(
      props.currentZonePoints[0].x * canvasWidth.value,
      props.currentZonePoints[0].y * canvasHeight.value
    )

    for (let i = 1; i < props.currentZonePoints.length; i++) {
      ctx.lineTo(
        props.currentZonePoints[i].x * canvasWidth.value,
        props.currentZonePoints[i].y * canvasHeight.value
      )
    }

    // 如果有3个或更多点，闭合路径
    if (props.currentZonePoints.length >= 3) {
      ctx.closePath()
      ctx.fill()
  }

    ctx.stroke()
  }
}

/**
 * 处理画布点击事件
 * * @param {MouseEvent} event 鼠标事件
 */
const handleCanvasClick = (event) => {
  if (!overlayCanvas.value) return

  // 获取相对于画布的点击坐标
  const rect = overlayCanvas.value.getBoundingClientRect()
  const x = (event.clientX - rect.left) / rect.width
  const y = (event.clientY - rect.top) / rect.height

  // 发送点击事件
  emit('canvas-click', { x, y, originalEvent: event })
}

/**
 * 调整画布大小以匹配视频尺寸
 */
const resizeCanvas = () => {
  if (!overlayCanvas.value || !props.video) return

  // 获取视频尺寸
  const videoWidth = props.video.videoWidth || props.video.width || props.video.clientWidth
  const videoHeight = props.video.videoHeight || props.video.height || props.video.clientHeight

  if (videoWidth && videoHeight) {
    // 设置画布尺寸
    overlayCanvas.value.width = videoWidth
    overlayCanvas.value.height = videoHeight
    canvasWidth.value = videoWidth
    canvasHeight.value = videoHeight

    // 如果有检测结果，重新渲染
    // 这里依赖的是 props.detectionResults (服务器结果) 或 localDetections (本地结果)
    // 直接调用 renderDetections 即可，它会根据 currentDetectionsToDraw 来判断
    renderDetections(props.localTrackingEnabled ? localDetections.value : props.detectionResults)
  }
}

// 监听启用状态变化
watch(() => props.enabled, (newVal) => {
  if (newVal) {
    startAnalysis()
    } else {
    stopAnalysis()
  }
})

// 监听视频源变化
watch(() => props.video, () => {
    nextTick(() => {
      resizeCanvas()
    })
})

// 监听外部传入的检测结果 (来自服务器)
watch(() => props.detectionResults, (newResults) => {
  // 只有当本地跟踪未启用时，才直接渲染服务器结果
  // 如果本地跟踪启用，则由 localDetections (通过 updateServerDetections 间接更新) 驱动渲染
  if (!props.localTrackingEnabled && newResults && newResults.length > 0) {
    renderDetections(newResults)
  }
  // 【修复】当服务器结果更新时，更新本地跟踪器的服务器检测结果
  if (props.localTrackingEnabled) {
    updateServerDetections(newResults);
  }
})

// 监听本地跟踪启用状态变化，同步到 useLocalTracking
watch(() => props.localTrackingEnabled, (newVal) => {
  setTrackingEnabled(newVal) // 同步到 useLocalTracking
  if (newVal) {
    // 如果启用本地跟踪，确保模型已加载并启动本地分析循环
    startAnalysis() // startAnalysis 内部会处理模型加载和循环启动
  } else {
    // 如果禁用本地跟踪，清空本地检测结果，并可能需要重新渲染上次的服务器结果
    localDetections.value = []
    // 重新渲染以显示上次的服务器结果，如果存在且后端AI启用
    if (props.enabled && props.detectionResults && props.detectionResults.length > 0) {
      renderDetections(props.detectionResults)
    } else {
      clearCanvas() // 如果后端AI也禁用，则清空
    }
  }
})

// 监听危险区域变化
watch(() => props.dangerZones, () => {
  // 如果有检测结果，重新渲染以包含新的危险区域
  renderDetections(props.localTrackingEnabled ? localDetections.value : props.detectionResults)
}, { deep: true })

// 监听当前区域点变化
watch(() => props.currentZonePoints, () => {
  // 重新渲染
  renderDetections(props.localTrackingEnabled ? localDetections.value : props.detectionResults)
}, { deep: true })

// 组件挂载时的初始化
onMounted(() => {
  if (overlayCanvas.value) {
    canvasContext.value = overlayCanvas.value.getContext('2d')
    resizeCanvas()
  }

  // 监听窗口大小变化，调整画布尺寸
    window.addEventListener('resize', resizeCanvas)

  // 如果 AI 分析或本地跟踪已启用，启动分析循环
  if (props.enabled || props.localTrackingEnabled) {
      startAnalysis()
  }
})

// 组件卸载时的清理
onUnmounted(() => {
  stopAnalysis()
  window.removeEventListener('resize', resizeCanvas)
})

// 对外暴露的方法
defineExpose({
  startAnalysis,
  stopAnalysis,
  clearCanvas,
  renderDetections
})
</script>

<style scoped>
.ai-analyzer {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none; /* 允许点击穿透到底层视频 */
  z-index: 10;
}
</style>
