<!-- AI分析器组件 -->
<template>
  <div class="ai-analyzer">
    <!-- 叠加在视频上的检测框画布 -->
    <canvas ref="overlayCanvas" class="overlay-canvas" @click="handleCanvasClick"></canvas>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useAIAnalysis } from '@/composables/useAIAnalysis'
import { useLocalTracking } from '@/composables/useLocalTracking'

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
  // 是否启用AI分析
  enabled: {
    type: Boolean,
    default: false
  },
  // 是否使用实时模式（更高频率发送帧）
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
  // 外部传入的检测结果（可选）
  detectionResults: {
    type: Array,
    default: () => []
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
let analysisTimer = null
let localProcessingTimer = null
const serverFrameInterval = ref(500) // 发送到服务器的帧间隔（毫秒）
const lastServerFrameTime = ref(0)   // 上次发送到服务器的时间
const enableLocalTracking = ref(true) // 是否启用本地跟踪

// 使用AI分析组合式API
const {
  sendFrameToAI,
  processResults,
  updateStats,
  getStats,
  clearCache
} = useAIAnalysis(props.cameraId)

// 使用本地目标跟踪组合式API
const {
  localDetections,
  isModelLoaded,
  loadModel: loadLocalTrackingModel,
  processFrame: processLocalFrame,
  updateServerDetections,
  getPerformanceStats: getLocalTrackingStats
} = useLocalTracking()

/**
 * 处理单个帧
 * 发送到AI服务器进行分析
 * 
 * @param {Blob} blob 帧数据
 * @param {number} width 帧宽度
 * @param {number} height 帧高度
 */
const handleFrame = async (blob, width, height) => {
  if (!blob) {
    isProcessingFrame = false
    return
  }
  
  const currentTime = Date.now()
  const shouldSendToServer = currentTime - lastServerFrameTime.value >= serverFrameInterval.value
  
  // 如果达到发送间隔，才发送到服务器
  if (shouldSendToServer) {
    lastServerFrameTime.value = currentTime
    
    try {
      const results = await sendFrameToAI(blob, width, height)
        if (results) {
          const processed = processResults(results)
          
          // 更新服务器检测结果到本地跟踪系统
        if (enableLocalTracking.value && isModelLoaded.value) {
            updateServerDetections(processed)
          }
          
        // 发送检测结果事件
          emit('detection-results', processed)
        
        // 渲染检测框
        renderDetections(processed.detections)
        }
    } catch (error) {
      console.error('AI分析失败:', error)
    } finally {
      // 更新性能统计
        updateStats()
        emit('performance-stats', getStats())
    }
  }
  
  isProcessingFrame = false
}

/**
 * 捕获视频帧
 * 从视频元素中提取当前帧并发送到AI服务
 */
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
    
    // 如果启用了本地跟踪，先进行本地处理
    if (enableLocalTracking.value && isModelLoaded.value) {
      // 本地处理视频帧
      processLocalFrame(props.video).then(localResults => {
        if (localResults && localResults.length > 0) {
          // 使用本地检测结果更新UI
          emit('detection-results', { detections: localResults })
          renderDetections(localResults)
        }
      }).catch(err => {
        console.error('本地处理视频帧失败:', err)
      })
    }
    
    // 发送到服务器处理
    canvas.toBlob(blob => handleFrame(blob, videoWidth, videoHeight), 'image/jpeg', 0.8)
  } catch (error) {
    console.error('帧捕获失败:', error)
    isProcessingFrame = false
  }
}

/**
 * 启动本地分析循环
 * 使用requestAnimationFrame实现更高帧率
 */
const startLocalAnalysis = () => {
  if (enableLocalTracking.value && isModelLoaded.value && props.video) {
    const runLocalAnalysis = () => {
      if (props.enabled && props.video) {
        try {
          processLocalFrame(props.video).then(localResults => {
            if (localResults && localResults.length > 0) {
              // 使用本地检测结果更新UI
              emit('detection-results', { detections: localResults })
              renderDetections(localResults)
            }
            
            // 继续下一帧分析
            if (props.enabled) {
              localProcessingTimer = requestAnimationFrame(runLocalAnalysis)
            }
          }).catch(error => {
            console.error('本地分析出错:', error)
            // 出错后短暂延迟再尝试继续
            setTimeout(() => {
              if (props.enabled) {
                localProcessingTimer = requestAnimationFrame(runLocalAnalysis)
              }
            }, 1000)
          })
        } catch (error) {
          console.error('本地分析循环出错:', error)
          // 出错后短暂延迟再尝试继续
          setTimeout(() => {
            if (props.enabled) {
              localProcessingTimer = requestAnimationFrame(runLocalAnalysis)
            }
          }, 1000)
        }
      }
    }
    
    // 启动分析循环
    localProcessingTimer = requestAnimationFrame(runLocalAnalysis)
  }
}

/**
 * 启动分析循环
 * 设置定时器定期捕获和分析视频帧
 */
const startAnalysis = () => {
  // 启动服务器分析
  if (!analysisTimer) {
    // 根据模式设置发送间隔
    serverFrameInterval.value = props.realtimeMode ? 200 : 500
    analysisTimer = setInterval(captureFrame, 100) // 固定100ms捕获帧，但不一定发送到服务器
  }
  
  // 如果本地跟踪已启用且模型已加载，启动本地分析
  if (enableLocalTracking.value && isModelLoaded.value) {
    startLocalAnalysis()
  } else if (enableLocalTracking.value) {
    // 如果模型未加载，先加载模型
    console.log('🧠 加载本地跟踪模型...')
    loadLocalTrackingModel().then(() => {
      console.log('✅ 本地跟踪模型加载完成:', isModelLoaded.value)
      if (isModelLoaded.value) {
        startLocalAnalysis()
      } else {
        console.warn('⚠️ 模型加载失败，禁用本地跟踪')
        enableLocalTracking.value = false
      }
    }).catch(error => {
      console.error('❌ 模型加载失败:', error)
      console.warn('⚠️ 由于错误，禁用本地跟踪')
      enableLocalTracking.value = false
    })
  }
}

/**
 * 停止分析循环
 * 清理定时器和资源
 */
const stopAnalysis = () => {
  if (analysisTimer) {
    clearInterval(analysisTimer)
    analysisTimer = null
  }
  
  if (localProcessingTimer) {
    cancelAnimationFrame(localProcessingTimer)
    localProcessingTimer = null
  }
  
  // 清空画布
  clearCanvas()
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
 * 
 * @param {Array} detections 检测结果数组
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
    const { bbox, type, label, confidence, color, is_dangerous } = detection
    
    // 如果没有边界框数据，跳过
    if (!bbox || bbox.length !== 4) return
    
    // 从AI处理的图像尺寸映射到当前画布尺寸
    const aiImageSize = detection.ai_image_size || { width: 640, height: 480 }
    const [x, y, w, h] = mapBboxToCanvas(bbox, aiImageSize, canvas.width, canvas.height)
    
    // 设置样式
    ctx.lineWidth = 2
    ctx.strokeStyle = is_dangerous ? '#ff0000' : (color || '#22c55e')
    
    // 绘制边界框
    ctx.beginPath()
    ctx.rect(x, y, w, h)
    ctx.stroke()
    
    // 绘制标签背景
    const confidenceText = confidence ? ` ${Math.round(confidence * 100)}%` : ''
    const labelText = `${label}${confidenceText}`
    const textWidth = ctx.measureText(labelText).width + 10
    
    ctx.fillStyle = is_dangerous ? 'rgba(239, 68, 68, 0.7)' : 'rgba(34, 197, 94, 0.7)'
    ctx.fillRect(x, y - 20, textWidth, 20)
    
    // 绘制标签文本
    ctx.fillStyle = '#ffffff'
    ctx.font = '12px Arial'
    ctx.fillText(labelText, x + 5, y - 5)
    
    // 如果是人脸识别结果，添加额外信息
    if (type === 'face' && detection.face_name) {
      const faceText = detection.face_name
      ctx.fillStyle = 'rgba(59, 130, 246, 0.7)'
      ctx.fillRect(x, y + h, ctx.measureText(faceText).width + 10, 20)
      ctx.fillStyle = '#ffffff'
      ctx.fillText(faceText, x + 5, y + h + 15)
    }
  })
    }
    
/**
 * 将AI检测的边界框坐标映射到当前画布尺寸
 * 
 * @param {Array} bbox 原始边界框坐标 [x, y, width, height]
 * @param {Object} aiImageSize AI处理的图像尺寸
 * @param {number} canvasWidth 当前画布宽度
 * @param {number} canvasHeight 当前画布高度
 * @returns {Array} 映射后的边界框坐标
 */
const mapBboxToCanvas = (bbox, aiImageSize, canvasWidth, canvasHeight) => {
  const [x, y, width, height] = bbox
  
  // 计算缩放比例
  const scaleX = canvasWidth / aiImageSize.width
  const scaleY = canvasHeight / aiImageSize.height
  
  // 应用缩放
  return [
    x * scaleX,
    y * scaleY,
    width * scaleX,
    height * scaleY
  ]
}

/**
 * 渲染危险区域
 * 
 * @param {CanvasRenderingContext2D} ctx 画布上下文
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
 * 
 * @param {CanvasRenderingContext2D} ctx 画布上下文
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
 * 
 * @param {MouseEvent} event 鼠标事件
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
    if (props.detectionResults && props.detectionResults.length > 0) {
      renderDetections(props.detectionResults)
    }
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

// 监听外部传入的检测结果
watch(() => props.detectionResults, (newResults) => {
  if (newResults && newResults.length > 0) {
    renderDetections(newResults)
  }
})

// 监听危险区域变化
watch(() => props.dangerZones, () => {
  // 如果有检测结果，重新渲染以包含新的危险区域
  if (props.detectionResults && props.detectionResults.length > 0) {
    renderDetections(props.detectionResults)
  } else {
    // 否则只渲染危险区域
    clearCanvas()
    if (canvasContext.value) {
      renderDangerZones(canvasContext.value, canvasWidth.value, canvasHeight.value)
      renderCurrentZonePoints(canvasContext.value)
    }
  }
}, { deep: true })
  
// 监听当前区域点变化
watch(() => props.currentZonePoints, () => {
  // 重新渲染
  if (props.detectionResults && props.detectionResults.length > 0) {
    renderDetections(props.detectionResults)
  } else {
    clearCanvas()
    if (canvasContext.value) {
      renderDangerZones(canvasContext.value, canvasWidth.value, canvasHeight.value)
      renderCurrentZonePoints(canvasContext.value)
    }
  }
}, { deep: true })

// 组件挂载时的初始化
onMounted(() => {
  if (overlayCanvas.value) {
    canvasContext.value = overlayCanvas.value.getContext('2d')
    resizeCanvas()
  }
    
  // 监听窗口大小变化，调整画布尺寸
    window.addEventListener('resize', resizeCanvas)
  
  // 如果已启用，启动分析
  if (props.enabled) {
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