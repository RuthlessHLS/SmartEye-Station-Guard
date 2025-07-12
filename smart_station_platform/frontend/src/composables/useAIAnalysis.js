import { ref } from 'vue'
import { useApi } from '@/api'

export function useAIAnalysis(cameraId) {
  const api = useApi()
  
  // 性能统计
  const stats = ref({
    avgProcessTime: 0,
    fps: 0,
    processedFrames: 0,
    skippedFrames: 0,
    errorCount: 0,
    lastUpdate: Date.now()
  })

  // 发送帧到AI服务进行分析
  const sendFrameToAI = async (frameBlob, width, height) => {
    const startTime = performance.now()
    
    try {
      const formData = new FormData()
      formData.append('frame', frameBlob)
      formData.append('camera_id', cameraId)
      formData.append('timestamp', new Date().toISOString())
      
      const response = await api.ai.analyzeFrame(formData)
      
      // 更新性能统计
      const processTime = performance.now() - startTime
      stats.value.avgProcessTime = (stats.value.avgProcessTime * 0.9) + (processTime * 0.1)
      stats.value.processedFrames++
      
      return response.data
    } catch (error) {
      console.error('AI分析请求失败:', error)
      stats.value.errorCount++
      throw error
    }
  }

  // 处理分析结果
  const processResults = (results) => {
    if (!results || !results.detections) {
      return null
    }

    return {
      detections: results.detections.map(detection => ({
        type: detection.type,
        label: detection.class_name || detection.type,
        confidence: detection.confidence,
        bbox: detection.bbox,
        timestamp: new Date(detection.timestamp || Date.now())
      })),
      alerts: results.alerts || []
    }
  }

  // 更新性能统计
  const updateStats = () => {
    const now = Date.now()
    const timeDiff = (now - stats.value.lastUpdate) / 1000
    
    if (timeDiff >= 1) {
      stats.value.fps = Math.round(stats.value.processedFrames / timeDiff)
      stats.value.processedFrames = 0
      stats.value.lastUpdate = now
    }
  }

  // 获取当前统计数据
  const getStats = () => stats.value

  return {
    sendFrameToAI,
    processResults,
    updateStats,
    getStats
  }
} 