<!-- AI分析器组件 -->
<template>
  <div class="ai-analyzer">
    <canvas ref="overlayCanvas" class="overlay-canvas"></canvas>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useAIAnalysis } from '@/composables/useAIAnalysis'

const props = defineProps({
  video: {
    type: [Object, null],
    required: false,
    default: null
  },
  cameraId: {
    type: String,
    required: true
  },
  enabled: {
    type: Boolean,
    default: false
  },
  realtimeMode: {
    type: Boolean,
    default: true
  },
  dangerZones: {
    type: Array,
    default: () => []
  },
  currentZonePoints: {
    type: Array,
    default: () => []
  },
  detectionResults: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['detection-results', 'performance-stats', 'canvas-click'])

const overlayCanvas = ref(null)
const canvasContext = ref(null)
let isProcessingFrame = false
let analysisTimer = null

const {
  sendFrameToAI,
  processResults,
  updateStats,
  getStats
} = useAIAnalysis(props.cameraId)

// 处理单个帧
const handleFrame = (blob, width, height) => {
  if (!blob) {
    isProcessingFrame = false
    return
  }
  
  sendFrameToAI(blob, width, height)
    .then(results => {
      if (results) {
        const processed = processResults(results)
        emit('detection-results', processed)
      }
    })
    .catch(error => console.error('AI分析失败:', error))
    .finally(() => {
      isProcessingFrame = false
      updateStats()
      emit('performance-stats', getStats())
    })
}

// 捕获视频帧
const captureFrame = () => {
  if (!props.video || isProcessingFrame || !props.enabled) {
    return
  }

  isProcessingFrame = true

  try {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    
    // 获取视频的实际尺寸
    const videoWidth = props.video.videoWidth || props.video.width || 640
    const videoHeight = props.video.videoHeight || props.video.height || 480
    
    if (videoWidth === 0 || videoHeight === 0) {
      console.warn('视频尺寸无效，跳过帧捕获')
      isProcessingFrame = false
      return
    }
    
    canvas.width = videoWidth
    canvas.height = videoHeight
    
    // 使用临时canvas的context来绘制视频帧
    ctx.drawImage(props.video, 0, 0, videoWidth, videoHeight)
    canvas.toBlob(blob => handleFrame(blob, videoWidth, videoHeight), 'image/jpeg', 0.8)
  } catch (error) {
    console.error('帧捕获失败:', error)
    isProcessingFrame = false
  }
}

// 启动分析循环
const startAnalysis = () => {
  if (!analysisTimer) {
    analysisTimer = setInterval(captureFrame, props.realtimeMode ? 100 : 500)
  }
}

// 停止分析
const stopAnalysis = () => {
  if (analysisTimer) {
    clearInterval(analysisTimer)
    analysisTimer = null
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

// 绘制检测结果
const drawDetectionResults = (results) => {
  if (!canvasContext.value || !overlayCanvas.value) return
  
  // 清除画布
  canvasContext.value.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height)
  
  if (!results || results.length === 0) {
    console.log('🎨 没有检测结果需要绘制')
    return
  }
  
  canvasContext.value.save()
  
  // 获取Canvas尺寸
  const canvasWidth = overlayCanvas.value.width
  const canvasHeight = overlayCanvas.value.height
  
  console.log(`🎨 Canvas尺寸: ${canvasWidth}x${canvasHeight}，绘制 ${results.length} 个检测框`)
  
  // 简化的坐标转换逻辑
  let scaleX = 1, scaleY = 1
  
  if (props.video && props.video.videoWidth && props.video.videoHeight) {
    // 直接使用视频原始尺寸到Canvas尺寸的比例
    scaleX = canvasWidth / props.video.videoWidth
    scaleY = canvasHeight / props.video.videoHeight
    
    console.log('📐 坐标转换参数:', {
      videoSize: `${props.video.videoWidth}x${props.video.videoHeight}`,
      canvasSize: `${canvasWidth}x${canvasHeight}`,
      scale: `${scaleX.toFixed(3)}x${scaleY.toFixed(3)}`
    })
  } else {
    console.warn('⚠️ 无法获取视频尺寸，使用默认缩放比例')
  }
  
  results.forEach((result, index) => {
    // 适配不同的数据格式
    let x, y, width, height, confidence, label
    
    if (result.bbox && Array.isArray(result.bbox)) {
      // AIVideoMonitor格式: {bbox: [x1, y1, x2, y2], confidence, label}
      const [x1, y1, x2, y2] = result.bbox
      
      // 应用坐标转换
      x = Math.max(0, Math.min(x1 * scaleX, canvasWidth))
      y = Math.max(0, Math.min(y1 * scaleY, canvasHeight))
      width = Math.max(0, Math.min((x2 - x1) * scaleX, canvasWidth - x))
      height = Math.max(0, Math.min((y2 - y1) * scaleY, canvasHeight - y))
      
      confidence = result.confidence || 0
      label = result.label || result.class_name || '未知'
    } else {
      // 其他格式: {x, y, width, height, confidence, class_name}
      x = Math.max(0, Math.min((result.x || 0) * scaleX, canvasWidth))
      y = Math.max(0, Math.min((result.y || 0) * scaleY, canvasHeight))
      width = Math.max(0, Math.min((result.width || 0) * scaleX, canvasWidth - x))
      height = Math.max(0, Math.min((result.height || 0) * scaleY, canvasHeight - y))
      confidence = result.confidence || 0
      label = result.class_name || result.label || '未知'
    }
    
    // 跳过无效的检测框
    if (width <= 0 || height <= 0) {
      console.warn(`⚠️ 跳过无效检测框 ${index}:`, { x, y, width, height })
      return
    }
    
    console.log(`🎯 绘制检测框 ${index}:`, { 
      type: result.type, 
      label, 
      confidence: (confidence * 100).toFixed(1) + '%',
      originalBbox: [...result.bbox], // 展开数组以显示实际值
      bboxFormat: 'left,top,right,bottom',
      videoSize: props.video ? `${props.video.videoWidth}x${props.video.videoHeight}` : 'unknown',
      canvasSize: `${canvasWidth}x${canvasHeight}`,
      scaleFactors: `${scaleX.toFixed(3)}x${scaleY.toFixed(3)}`,
      transformedCoords: {
        x: x.toFixed(1), 
        y: y.toFixed(1), 
        width: width.toFixed(1), 
        height: height.toFixed(1),
        right: (x + width).toFixed(1),
        bottom: (y + height).toFixed(1)
      },
      calculationSteps: {
        step1_originalCoords: `left=${result.bbox[0]}, top=${result.bbox[1]}, right=${result.bbox[2]}, bottom=${result.bbox[3]}`,
        step2_afterScale: `x=${(result.bbox[0] * scaleX).toFixed(1)}, y=${(result.bbox[1] * scaleY).toFixed(1)}, w=${((result.bbox[2] - result.bbox[0]) * scaleX).toFixed(1)}, h=${((result.bbox[3] - result.bbox[1]) * scaleY).toFixed(1)}`,
        step3_clampedFinal: `x=${x.toFixed(1)}, y=${y.toFixed(1)}, w=${width.toFixed(1)}, h=${height.toFixed(1)}`
      }
    })
    
    // 根据检测类型选择颜色
    let color = '#00ff00' // 默认绿色
    if (result.type === 'face') {
      color = '#409EFF' // 蓝色
    } else if (result.type === 'unknown_face') {
      color = '#F56C6C' // 红色
    } else if (result.type === 'fire_detection' || result.type === 'fire') {
      color = '#FF4444' // 深红色
    } else if (result.type === 'person') {
      color = '#67C23A' // 绿色
    }
    
    // 绘制边界框
    canvasContext.value.strokeStyle = color
    canvasContext.value.lineWidth = 3
    canvasContext.value.strokeRect(x, y, width, height)
    
    // 绘制标签背景
    const labelText = `${label} ${(confidence * 100).toFixed(1)}%`
    canvasContext.value.font = 'bold 14px Arial'
    const textMetrics = canvasContext.value.measureText(labelText)
    const textHeight = 22
    const padding = 6
    
    // 确保标签不会超出Canvas边界
    const labelY = Math.max(textHeight, y)
    const labelX = Math.min(x, canvasWidth - textMetrics.width - padding * 2)
    
    canvasContext.value.fillStyle = color
    canvasContext.value.fillRect(labelX, labelY - textHeight, textMetrics.width + padding * 2, textHeight)
    
    // 绘制标签文字
    canvasContext.value.fillStyle = '#ffffff'
    canvasContext.value.fillText(labelText, labelX + padding, labelY - 6)
  })
  
  canvasContext.value.restore()
  
  console.log(`✅ 成功绘制 ${results.length} 个检测框`)
}

// 绘制危险区域
const drawDangerZones = () => {
  if (!canvasContext.value || !overlayCanvas.value) return
  
  // 先绘制检测结果（会清除画布）
  if (props.detectionResults && props.detectionResults.length > 0) {
    drawDetectionResults(props.detectionResults)
  } else {
    // 如果没有检测结果，清除画布
    canvasContext.value.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height)
  }
  
  // 在检测结果之上绘制已保存的危险区域
  props.dangerZones.forEach(zone => {
    drawZone(zone.coordinates, '#f56c6c', zone.name, true)
  })
  
  // 绘制正在绘制的区域
  if (props.currentZonePoints.length > 0) {
    drawZone(props.currentZonePoints, '#409EFF', '新区域', false)
  }
}

// 绘制单个区域
const drawZone = (points, color, name, isComplete) => {
  if (!canvasContext.value || points.length === 0) return

  canvasContext.value.save()

  // 绘制区域边界
  canvasContext.value.strokeStyle = color
  canvasContext.value.lineWidth = 3
  canvasContext.value.setLineDash(isComplete ? [] : [8, 4])

  canvasContext.value.beginPath()
  canvasContext.value.moveTo(points[0][0], points[0][1])

  for (let i = 1; i < points.length; i++) {
    canvasContext.value.lineTo(points[i][0], points[i][1])
  }

  if (isComplete && points.length > 2) {
    canvasContext.value.closePath()

    // 填充半透明背景
    canvasContext.value.fillStyle = color + '20' // 添加透明度
    canvasContext.value.fill()
  }

  canvasContext.value.stroke()

  // 绘制顶点
  points.forEach((point, index) => {
    canvasContext.value.fillStyle = color
    canvasContext.value.beginPath()
    canvasContext.value.arc(point[0], point[1], 4, 0, 2 * Math.PI)
    canvasContext.value.fill()

    // 显示顶点序号
    canvasContext.value.fillStyle = '#ffffff'
    canvasContext.value.font = '12px Arial'
    canvasContext.value.textAlign = 'center'
    canvasContext.value.fillText(index + 1, point[0], point[1] + 4)
  })

  // 绘制区域名称
  if (points.length > 0) {
    const centerX = points.reduce((sum, point) => sum + point[0], 0) / points.length
    const centerY = points.reduce((sum, point) => sum + point[1], 0) / points.length

    canvasContext.value.fillStyle = color
    canvasContext.value.font = 'bold 14px Arial'
    canvasContext.value.textAlign = 'center'
    canvasContext.value.fillText(name, centerX, centerY)
  }

  canvasContext.value.restore()
}

// 处理Canvas点击事件
const handleCanvasClick = (event) => {
  const rect = overlayCanvas.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  // 转换为相对于Canvas的坐标
  const canvasX = (x / rect.width) * overlayCanvas.value.width
  const canvasY = (y / rect.height) * overlayCanvas.value.height

  emit('canvas-click', { x: canvasX, y: canvasY, originalEvent: event })
}

// 启用/禁用Canvas交互
const setCanvasInteractive = (interactive) => {
  if (overlayCanvas.value) {
    overlayCanvas.value.style.pointerEvents = interactive ? 'auto' : 'none'
    if (interactive) {
      overlayCanvas.value.addEventListener('click', handleCanvasClick)
    } else {
      overlayCanvas.value.removeEventListener('click', handleCanvasClick)
    }
  }
}

// 调整Canvas尺寸
const resizeCanvas = () => {
  if (!overlayCanvas.value) {
    console.warn('Canvas元素不存在，跳过尺寸调整')
    return
  }
  
  try {
    let containerRect = null
    
    // 优先使用video元素的尺寸
    if (props.video && props.video.getBoundingClientRect) {
      containerRect = props.video.getBoundingClientRect()
      console.log('📐 使用video元素尺寸:', containerRect)
    }
    
    // 如果video元素无效，使用父容器尺寸
    if (!containerRect || containerRect.width <= 0 || containerRect.height <= 0) {
      const parent = overlayCanvas.value.parentElement
      if (parent) {
        containerRect = parent.getBoundingClientRect()
        console.log('📐 使用父容器尺寸:', containerRect)
      }
    }
    
    // 最后的后备方案：使用固定尺寸
    if (!containerRect || containerRect.width <= 0 || containerRect.height <= 0) {
      containerRect = { width: 640, height: 480 }
      console.log('📐 使用默认尺寸:', containerRect)
    }
    
    // 应用尺寸设置
    const width = Math.floor(containerRect.width)
    const height = Math.floor(containerRect.height)
    
    if (width > 0 && height > 0) {
      // 设置Canvas的显示尺寸
      overlayCanvas.value.style.width = width + 'px'
      overlayCanvas.value.style.height = height + 'px'
      
      // 设置Canvas的内部分辨率（用于绘制）
      overlayCanvas.value.width = width
      overlayCanvas.value.height = height
      
      console.log('✅ Canvas尺寸已调整:', width, 'x', height)
      
      // 重新绘制内容
      nextTick(() => {
        drawDangerZones()
      })
    } else {
      console.warn('⚠️ 无效的容器尺寸:', { width, height })
    }
  } catch (error) {
    console.error('❌ 调整Canvas尺寸失败:', error)
  }
}

// 监听属性变化，重新绘制
watch(() => [props.dangerZones, props.currentZonePoints, props.detectionResults], ([newDangerZones, newCurrentZonePoints, newDetectionResults]) => {
  console.log('🔄 AIAnalyzer props变化:', {
    dangerZones: newDangerZones?.length || 0,
    currentZonePoints: newCurrentZonePoints?.length || 0,
    detectionResults: newDetectionResults?.length || 0
  })
  drawDangerZones()
}, { deep: true, immediate: true })

// 监听video属性变化，重新初始化Canvas
watch(() => props.video, (newVideo, oldVideo) => {
  console.log('🔄 video属性变化:', { 
    old: oldVideo ? 'exists' : 'null', 
    new: newVideo ? 'exists' : 'null' 
  })
  
  if (newVideo) {
    // 立即调整Canvas尺寸
    nextTick(() => {
      resizeCanvas()
    })
    
    // 延迟再次调整，确保video元素完全加载
    setTimeout(() => {
      resizeCanvas()
    }, 200)
  }
}, { immediate: true })



// 暴露方法给父组件
defineExpose({
  drawDangerZones,
  setCanvasInteractive,
  resizeCanvas,
  getCanvas: () => overlayCanvas.value,
  getContext: () => canvasContext.value
})

// 组件挂载时初始化
onMounted(() => {
  console.log('🔧 AIAnalyzer组件挂载')
  
  if (overlayCanvas.value) {
    canvasContext.value = overlayCanvas.value.getContext('2d')
    console.log('✅ Canvas上下文已创建')
    
    // 立即尝试调整Canvas尺寸
    resizeCanvas()
    
    // 多次尝试调整Canvas尺寸，确保video元素完全加载
    const resizeAttempts = [100, 300, 500, 1000]
    resizeAttempts.forEach(delay => {
      setTimeout(() => {
        resizeCanvas()
      }, delay)
    })
    
    // 监听窗口大小变化
    window.addEventListener('resize', resizeCanvas)
  }
  
  // 延迟启动分析，确保video元素已经准备好
  if (props.enabled) {
    setTimeout(() => {
      startAnalysis()
    }, 200)
  }
})

// 组件卸载时清理
onUnmounted(() => {
  stopAnalysis()
  
  // 清理事件监听器
  if (overlayCanvas.value) {
    overlayCanvas.value.removeEventListener('click', handleCanvasClick)
  }
  window.removeEventListener('resize', resizeCanvas)
})
</script>

<style scoped>
.ai-analyzer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 10;
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
</style> 