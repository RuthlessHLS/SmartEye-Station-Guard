                import { ref, onMounted, onUnmounted } from 'vue'
import * as tf from '@tensorflow/tfjs'
import * as cocoSsd from '@tensorflow-models/coco-ssd'

export function useLocalTracking() {
  const model = ref(null)
  const isModelLoaded = ref(false)
  const isModelLoading = ref(false)
  const localDetections = ref([])
  const lastServerDetections = ref([])
  const detectionHistory = ref(new Map()) // 跟踪ID -> 历史检测记录
  const processingTime = ref(0)
  const frameCount = ref(0)
  const trackingEnabled = ref(true)
  
  // 本地检测配置
  const config = {
    minScore: 0.5,        // 最小检测分数
    maxDetections: 10,    // 最大检测数量
    interpolationFrames: 3, // 在服务器响应之间插入的帧数
    trackingHistorySize: 10, // 每个目标保留的历史记录数量
    iouThreshold: 0.5,    // IOU阈值，用于匹配检测框
    enablePrediction: true // 启用位置预测
  }
  
  // 初始化TensorFlow.js
  const initializeTensorflow = async () => {
    try {
      if (!tf.getBackend()) {
        await tf.setBackend('webgl')
      }
      
      // 检查后端是否成功设置
      const backend = tf.getBackend()
      if (!backend) {
        // 尝试其他可用的后端
        const availableBackends = ['webgl', 'cpu', 'wasm']
        for (const backendName of availableBackends) {
          try {
            await tf.setBackend(backendName)
            if (tf.getBackend()) break
          } catch (e) {
            console.warn(`无法设置后端 ${backendName}: ${e.message}`)
          }
        }
      }
      
      // 预热TensorFlow.js
      const warmupTensor = tf.tensor2d([[1, 2], [3, 4]])
      warmupTensor.dispose()
      
      return !!tf.getBackend()
    } catch (error) {
      console.error('TensorFlow.js初始化失败:', error)
      return false
    }
  }
  
  // 加载模型
  const loadModel = async () => {
    if (isModelLoaded.value || isModelLoading.value) return
    
    try {
      isModelLoading.value = true
      
      // 先初始化TensorFlow.js
      const tfInitialized = await initializeTensorflow()
      if (!tfInitialized) {
        throw new Error('TensorFlow.js初始化失败')
      }
      
      // 加载COCO-SSD模型
      model.value = await cocoSsd.load({
        base: 'lite_mobilenet_v2' // 使用轻量级模型提高速度
      })
      
      isModelLoaded.value = true
    } catch (error) {
      console.error('模型加载失败:', error)
    } finally {
      isModelLoading.value = false
    }
  }
  
  // 本地目标检测
  const detectObjects = async (videoElement) => {
    if (!model.value || !videoElement || !trackingEnabled.value) return []
    
    try {
      const startTime = performance.now()
      
      // 检查TensorFlow.js状态
      if (!tf.getBackend()) {
        console.log('⚠️ TensorFlow.js后端未初始化，尝试重新初始化')
        await initializeTensorflow()
        if (!tf.getBackend()) {
          throw new Error('TensorFlow.js后端不可用')
        }
      }
      
      // 使用TensorFlow.js进行目标检测
      const predictions = await model.value.detect(videoElement, config.maxDetections)
      
      // 过滤低置信度检测结果
      const filteredPredictions = predictions.filter(p => p.score >= config.minScore)
      
      // 转换为标准格式
      const detections = filteredPredictions.map(p => ({
        type: p.class,
        label: p.class,
        bbox: [p.bbox[0], p.bbox[1], p.bbox[0] + p.bbox[2], p.bbox[1] + p.bbox[3]], // [x1, y1, x2, y2]
        confidence: p.score,
        source: 'local',
        timestamp: Date.now()
      }))
      
      // 更新处理时间
      processingTime.value = performance.now() - startTime
      frameCount.value++
      
      return detections
    } catch (error) {
      console.error('本地目标检测失败:', error)
      return []
    }
  }
  
  // 计算两个边界框的IOU (Intersection over Union)
  const calculateIOU = (box1, box2) => {
    // 计算交集区域
    const [x1_1, y1_1, x2_1, y2_1] = box1
    const [x1_2, y1_2, x2_2, y2_2] = box2
    
    const x_left = Math.max(x1_1, x1_2)
    const y_top = Math.max(y1_1, y1_2)
    const x_right = Math.min(x2_1, x2_2)
    const y_bottom = Math.min(y2_1, y2_2)
    
    // 如果没有交集，返回0
    if (x_right < x_left || y_bottom < y_top) return 0
    
    // 计算交集面积
    const intersection_area = (x_right - x_left) * (y_bottom - y_top)
    
    // 计算两个边界框的面积
    const box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
    const box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
    
    // 计算并集面积
    const union_area = box1_area + box2_area - intersection_area
    
    // 返回IOU
    return intersection_area / union_area
  }
  
  // 将本地检测与服务器检测结果匹配
  const matchDetections = (localDetects, serverDetects) => {
    // 如果没有服务器检测结果，直接返回本地检测结果
    if (!serverDetects || serverDetects.length === 0) {
      return localDetects.map(det => ({
        ...det,
        matched: false,
        tracking_id: det.tracking_id || `local_${Date.now()}_${Math.floor(Math.random() * 1000)}`
      }))
    }
    
    // 复制本地和服务器检测结果，避免修改原始数据
    const localCopy = [...localDetects]
    const serverCopy = [...serverDetects]
    
    // 记录匹配结果
    const matches = []
    const unmatched = []
    
    // 遍历本地检测结果
    localCopy.forEach(localDet => {
      // 查找最佳匹配的服务器检测结果
      let bestMatch = null
      let bestIOU = 0
      
      serverCopy.forEach(serverDet => {
        // 只匹配同类型的检测框
        if (localDet.type === serverDet.type || 
            (localDet.type === 'person' && serverDet.type === 'person')) {
          const iou = calculateIOU(localDet.bbox, serverDet.bbox)
          if (iou > config.iouThreshold && iou > bestIOU) {
            bestMatch = serverDet
            bestIOU = iou
          }
        }
      })
      
      if (bestMatch) {
        // 找到匹配，使用服务器检测的ID和置信度
        matches.push({
          ...localDet,
          tracking_id: bestMatch.tracking_id,
          confidence: bestMatch.confidence,
          matched: true,
          matchScore: bestIOU
        })
        
        // 从服务器检测列表中移除已匹配的结果
        const index = serverCopy.indexOf(bestMatch)
        if (index !== -1) {
          serverCopy.splice(index, 1)
        }
      } else {
        // 未找到匹配，保留本地检测结果
        unmatched.push({
          ...localDet,
          matched: false,
          tracking_id: localDet.tracking_id || `local_${Date.now()}_${Math.floor(Math.random() * 1000)}`
        })
      }
    })
    
    // 合并匹配和未匹配的结果
    return [...matches, ...unmatched]
  }
  
  // 基于历史轨迹预测位置
  const predictPosition = (trackingId) => {
    const history = detectionHistory.value.get(trackingId)
    if (!history || history.length < 2) return null
    
    // 获取最近的两个检测结果
    const latest = history[history.length - 1]
    const previous = history[history.length - 2]
    
    // 计算时间差（秒）
    const timeDelta = (latest.timestamp - previous.timestamp) / 1000
    if (timeDelta <= 0) return latest.bbox
    
    // 计算位置差异
    const [x1_prev, y1_prev, x2_prev, y2_prev] = previous.bbox
    const [x1_latest, y1_latest, x2_latest, y2_latest] = latest.bbox
    
    // 计算中心点
    const center_prev = [(x1_prev + x2_prev) / 2, (y1_prev + y2_prev) / 2]
    const center_latest = [(x1_latest + x2_latest) / 2, (y1_latest + y2_latest) / 2]
    
    // 计算速度（像素/秒）
    const velocity_x = (center_latest[0] - center_prev[0]) / timeDelta
    const velocity_y = (center_latest[1] - center_prev[1]) / timeDelta
    
    // 计算大小差异
    const width_prev = x2_prev - x1_prev
    const height_prev = y2_prev - y1_prev
    const width_latest = x2_latest - x1_latest
    const height_latest = y2_latest - y1_latest
    
    // 计算大小变化速率
    const width_change_rate = (width_latest - width_prev) / timeDelta
    const height_change_rate = (height_latest - height_prev) / timeDelta
    
    // 预测下一帧的位置（假设匀速运动）
    // 预测时间为1/30秒（假设30fps）
    const prediction_time = 1/30
    
    // 预测中心点
    const predicted_center_x = center_latest[0] + velocity_x * prediction_time
    const predicted_center_y = center_latest[1] + velocity_y * prediction_time
    
    // 预测宽高
    const predicted_width = Math.max(10, width_latest + width_change_rate * prediction_time)
    const predicted_height = Math.max(10, height_latest + height_change_rate * prediction_time)
    
    // 计算预测的边界框
    const predicted_bbox = [
      predicted_center_x - predicted_width / 2,
      predicted_center_y - predicted_height / 2,
      predicted_center_x + predicted_width / 2,
      predicted_center_y + predicted_height / 2
    ]
    
    return predicted_bbox
  }
  
  // 更新检测历史记录
  const updateDetectionHistory = (detections) => {
    // 遍历所有检测结果
    detections.forEach(detection => {
      if (!detection.tracking_id) return
      
      // 获取或创建历史记录
      let history = detectionHistory.value.get(detection.tracking_id) || []
      
      // 添加当前检测结果到历史记录
      history.push({
        bbox: detection.bbox,
        timestamp: detection.timestamp || Date.now(),
        confidence: detection.confidence
      })
      
      // 限制历史记录大小
      if (history.length > config.trackingHistorySize) {
        history = history.slice(-config.trackingHistorySize)
      }
      
      // 更新历史记录
      detectionHistory.value.set(detection.tracking_id, history)
    })
    
    // 清理过期的历史记录
    const currentTime = Date.now()
    const expirationTime = 2000 // 2秒
    
    detectionHistory.value.forEach((history, id) => {
      if (history.length > 0) {
        const lastUpdate = history[history.length - 1].timestamp
        if (currentTime - lastUpdate > expirationTime) {
          detectionHistory.value.delete(id)
        }
      }
    })
  }
  
  // 在服务器检测之间插入本地检测结果
  const interpolateDetections = (localDetects) => {
    if (!lastServerDetections.value || lastServerDetections.value.length === 0) {
      return localDetects
    }
    
    // 匹配本地检测与服务器检测
    const matchedDetections = matchDetections(localDetects, lastServerDetections.value)
    
    // 更新检测历史记录
    updateDetectionHistory(matchedDetections)
    
    // 对于每个未匹配的服务器检测结果，尝试进行预测
    if (config.enablePrediction) {
      lastServerDetections.value.forEach(serverDet => {
        // 检查是否已经在匹配结果中
        const alreadyMatched = matchedDetections.some(
          det => det.tracking_id === serverDet.tracking_id
        )
        
        if (!alreadyMatched && serverDet.tracking_id) {
          // 尝试预测位置
          const predictedBbox = predictPosition(serverDet.tracking_id)
          if (predictedBbox) {
            // 添加预测结果
            matchedDetections.push({
              ...serverDet,
              bbox: predictedBbox,
              confidence: serverDet.confidence * 0.9, // 降低置信度
              isPredicted: true,
              source: 'prediction',
              timestamp: Date.now()
            })
          }
        }
      })
    }
    
    return matchedDetections
  }
  
  // 处理视频帧
  const processFrame = async (videoElement) => {
    if (!trackingEnabled.value || !videoElement) return localDetections.value
    
    try {
      // 检查模型是否已加载
      if (!model.value) {
        console.log('⚠️ 模型未加载，尝试重新加载')
        await loadModel()
        if (!model.value) {
          console.log('❌ 模型加载失败，无法处理帧')
          return localDetections.value
        }
      }
      
      // 执行本地目标检测
      const detections = await detectObjects(videoElement)
      
      // 插值处理
      const interpolated = interpolateDetections(detections)
      
      // 更新本地检测结果
      localDetections.value = interpolated
      
      return interpolated
    } catch (error) {
      console.error('处理帧失败:', error)
      return localDetections.value
    }
  }
  
  // 更新服务器检测结果
  const updateServerDetections = (detections) => {
    if (!detections || !Array.isArray(detections)) return
    
    // 添加时间戳
    const timestamped = detections.map(det => ({
      ...det,
      timestamp: Date.now(),
      source: 'server'
    }))
    
    // 更新最新的服务器检测结果
    lastServerDetections.value = timestamped
    
    // 更新检测历史记录
    updateDetectionHistory(timestamped)
    
    // 合并本地检测和服务器检测
    if (localDetections.value.length > 0) {
      // 匹配并更新本地检测结果
      localDetections.value = matchDetections(localDetections.value, timestamped)
    }
  }
  
  // 获取性能统计
  const getPerformanceStats = () => {
    return {
      processingTime: processingTime.value,
      frameCount: frameCount.value,
      modelLoaded: isModelLoaded.value,
      trackedObjects: detectionHistory.value.size
    }
  }
  
  // 设置配置
  const setConfig = (newConfig) => {
    Object.assign(config, newConfig)
  }
  
  // 启用/禁用跟踪
  const setTrackingEnabled = (enabled) => {
    trackingEnabled.value = enabled
  }
  
  // 组件挂载时加载模型
  onMounted(() => {
    // 延迟加载模型，等待页面完全渲染
    setTimeout(() => {
      loadModel()
    }, 1000)
  })
  
  // 组件卸载时清理资源
  onUnmounted(() => {
    // 清理TensorFlow资源
    if (model.value) {
      try {
        // 释放模型资源
        model.value = null
        
        // 清理TensorFlow内存
        if (tf) {
          tf.disposeVariables()
          tf.engine().endScope()
          tf.engine().disposeVariables()
        }
      } catch (e) {
        console.error('清理TensorFlow资源失败:', e)
      }
    }
  })
  
  return {
    localDetections,
    isModelLoaded,
    isModelLoading,
    loadModel,
    processFrame,
    updateServerDetections,
    getPerformanceStats,
    setConfig,
    setTrackingEnabled
  }
} 