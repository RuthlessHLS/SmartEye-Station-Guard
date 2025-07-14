import { ref, reactive, computed } from 'vue'
import { useApi } from '@/api'

/**
 * AI视频分析组合式API
 * 负责处理视频帧发送到AI服务器、结果处理和性能统计
 * 
 * @param {string} cameraId 摄像头ID
 * @returns {Object} AI分析操作和状态对象
 */
export function useAIAnalysis(cameraId) {
  const api = useApi()
  
  // 性能统计
  const stats = reactive({
    avgProcessTime: 0,         // 平均处理时间(毫秒)
    fps: 0,                    // 每秒处理帧数
    processedFrames: 0,        // 已处理帧数
    skippedFrames: 0,          // 跳过的帧数
    errorCount: 0,             // 错误次数
    lastUpdate: Date.now(),    // 上次更新时间
    totalRequests: 0,          // 总请求数
    successRequests: 0,        // 成功请求数
    networkLatency: 0,         // 网络延迟(毫秒)
    processingLatency: 0,      // 服务器处理延迟(毫秒)
    totalLatency: 0            // 总延迟(毫秒)
  })

  // 检测结果缓存
  const resultCache = reactive({
    lastResults: null,         // 最后一次检测结果
    timestamp: 0,              // 结果时间戳
    pendingRequest: false      // 是否有请求正在进行
  })
  
  // 计算属性：成功率
  const successRate = computed(() => {
    return stats.totalRequests > 0 
      ? Math.round((stats.successRequests / stats.totalRequests) * 100) 
      : 0
  })

  /**
   * 发送视频帧到AI服务进行分析
   * 
   * @param {Blob} frameBlob 视频帧Blob对象
   * @param {number} width 帧宽度
   * @param {number} height 帧高度
   * @returns {Promise<Object>} 分析结果
   */
  const sendFrameToAI = async (frameBlob, width, height) => {
    // 如果已有请求在处理中，跳过本次请求
    if (resultCache.pendingRequest) {
      stats.skippedFrames++
      return null
    }
    
    resultCache.pendingRequest = true
    const requestStartTime = performance.now()
    const requestTimestamp = Date.now()
    
    try {
      // 准备表单数据
      const formData = new FormData()
      formData.append('frame', frameBlob)
      formData.append('camera_id', cameraId)
      formData.append('timestamp', new Date().toISOString())
      formData.append('image_width', width)
      formData.append('image_height', height)
      
      // 记录发送的图像尺寸，用于坐标转换
      window.lastSentImageSize = {
        width,
        height,
        timestamp: requestTimestamp
      }
      
      // 发送请求到AI服务
      const response = await api.ai.analyzeFrame(formData, {
        timeout: 60000 // 60秒超时
      })
      
      // 更新性能统计
      const totalTime = performance.now() - requestStartTime
      const processingTime = response.processing_time || 0
      const networkTime = totalTime - processingTime
      
      stats.avgProcessTime = (stats.avgProcessTime * 0.9) + (totalTime * 0.1)
      stats.processedFrames++
      stats.totalRequests++
      stats.successRequests++
      stats.networkLatency = (stats.networkLatency * 0.9) + (networkTime * 0.1)
      stats.processingLatency = (stats.processingLatency * 0.9) + (processingTime * 0.1)
      stats.totalLatency = (stats.totalLatency * 0.9) + (totalTime * 0.1)
      
      // 更新结果缓存
      resultCache.lastResults = response
      resultCache.timestamp = Date.now()
      
      return response
    } catch (error) {
      console.error('AI分析请求失败:', error)
      stats.errorCount++
      stats.totalRequests++
      return null
    } finally {
      resultCache.pendingRequest = false
    }
  }

  /**
   * 处理分析结果
   * 转换为前端友好的格式，并处理坐标映射
   */
  const processResults = (results) => {
    if (!results || !results.detections) {
      return null
    }

    const aiImageSize = window.lastSentImageSize || { width: 640, height: 480 }
    
    const processedDetections = results.detections.map(detection => ({
      id: detection.id || `${detection.type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: detection.type,
        label: detection.class_name || detection.type,
        confidence: detection.confidence,
        bbox: detection.bbox,
        timestamp: new Date(detection.timestamp || Date.now()),
      ai_image_size: aiImageSize,
      metadata: detection.metadata || {},
      tracking_id: detection.tracking_id,
      is_dangerous: detection.is_dangerous || false,
      danger_zone_id: detection.danger_zone_id,
      face_name: detection.face_name,
      face_distance: detection.face_distance,
      behavior: detection.behavior,
      color: getDetectionColor(detection.type)
    }))

    return {
      detections: processedDetections,
      alerts: results.alerts || [],
      processing_time: results.processing_time,
      timestamp: results.timestamp || Date.now()
    }
  }

  /**
   * 根据检测类型获取显示颜色
   * 
   * @param {string} type 检测类型
   * @returns {string} 颜色代码
   */
  const getDetectionColor = (type) => {
    const colorMap = {
      person: '#22c55e',       // 绿色
      face: '#3b82f6',         // 蓝色
      face_unknown: '#f97316', // 橙色
      fire: '#ef4444',         // 红色
      smoke: '#9ca3af',        // 灰色
      car: '#8b5cf6',          // 紫色
      truck: '#6366f1',        // 靛蓝色
      bicycle: '#06b6d4',      // 青色
      motorcycle: '#14b8a6',   // 蓝绿色
      bus: '#f59e0b',          // 琥珀色
      danger_zone: '#dc2626'   // 危险区域：红色
    }
    
    return colorMap[type] || '#64748b' // 默认为石板灰
  }

  /**
   * 更新性能统计
   * 计算帧率和其他性能指标
   */
  const updateStats = () => {
    const now = Date.now()
    const timeDiff = (now - stats.lastUpdate) / 1000
    
    if (timeDiff >= 1) {
      stats.fps = Math.round(stats.processedFrames / timeDiff)
      stats.processedFrames = 0
      stats.lastUpdate = now
    }
  }

  /**
   * 获取当前统计数据
   * 
   * @returns {Object} 性能统计数据
   */
  const getStats = () => {
    return {
      ...stats,
      successRate: successRate.value
    }
  }

  /**
   * 重置统计数据
   */
  const resetStats = () => {
    Object.assign(stats, {
      avgProcessTime: 0,
      fps: 0,
      processedFrames: 0,
      skippedFrames: 0,
      errorCount: 0,
      lastUpdate: Date.now(),
      totalRequests: 0,
      successRequests: 0,
      networkLatency: 0,
      processingLatency: 0,
      totalLatency: 0
    })
  }

  /**
   * 清除检测缓存
   */
  const clearCache = async () => {
    try {
      await api.ai.clearDetectionCache(cameraId)
      resultCache.lastResults = null
      resultCache.timestamp = 0
      return true
    } catch (error) {
      console.error('清除检测缓存失败:', error)
      return false
    }
  }

  return {
    // 方法
    sendFrameToAI,
    processResults,
    updateStats,
    getStats,
    resetStats,
    clearCache,
    
    // 状态
    stats,
    resultCache,
    successRate
  }
} 