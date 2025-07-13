import { ref, onUnmounted } from 'vue'

/**
 * WebSocket通信组合式API
 * 提供实时通信功能，包含自动重连、消息处理和连接状态管理
 * 
 * @param {string} url WebSocket服务器URL
 * @param {Object} options 配置选项
 * @returns {Object} WebSocket操作和状态对象
 */
export function useWebSocket(url, options = {}) {
  // 默认配置
  const defaultOptions = {
    reconnectInterval: 5000,       // 重连间隔(毫秒)
    reconnectAttempts: 10,         // 最大重连次数
    autoReconnect: true,           // 是否自动重连
    heartbeatInterval: 30000,      // 心跳间隔(毫秒)
    heartbeatMessage: 'ping',      // 心跳消息内容
    debug: false                   // 是否启用调试日志
  }
  
  const config = { ...defaultOptions, ...options }
  
  // 状态管理
  const socket = ref(null)
  const messages = ref([])
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const reconnectCount = ref(0)
  const lastError = ref(null)
  
  // 定时器引用
  let reconnectTimer = null
  let heartbeatTimer = null
  
  /**
   * 记录日志(仅在调试模式下)
   */
  const log = (message, type = 'info') => {
    if (!config.debug) return
    
    const prefix = `[WebSocket] ${type.toUpperCase()}:`
    switch (type) {
      case 'error': console.error(prefix, message); break
      case 'warn':  console.warn(prefix, message); break
      default:      console.log(prefix, message)
    }
  }
  
  /**
   * 建立WebSocket连接
   */
  const connect = () => {
    // 避免重复连接
    if (isConnected.value || isConnecting.value) return
    
    isConnecting.value = true
    
    try {
      log(`正在连接到 ${url}`)
    socket.value = new WebSocket(url)

      // 连接建立事件
    socket.value.onopen = () => {
        log('连接已建立')
      isConnected.value = true
        isConnecting.value = false
        reconnectCount.value = 0
        lastError.value = null
        
        // 启动心跳
        startHeartbeat()
    }

      // 接收消息事件
    socket.value.onmessage = (event) => {
      try {
          // 如果收到的是心跳响应，不处理
          if (event.data === 'pong') return
          
        const data = JSON.parse(event.data)
        messages.value.push(data)
          
          // 保持消息列表在合理大小
          if (messages.value.length > 100) {
            messages.value.shift()
          }
        } catch (error) {
          log(`解析消息失败: ${error.message}`, 'error')
        }
      }
      
      // 连接关闭事件
      socket.value.onclose = (event) => {
        log(`连接已关闭: 代码=${event.code}, 原因=${event.reason || '未知'}`)
        isConnected.value = false
        isConnecting.value = false
        
        // 清理心跳
        stopHeartbeat()
        
        // 自动重连
        if (config.autoReconnect && reconnectCount.value < config.reconnectAttempts) {
          scheduleReconnect()
        }
      }
      
      // 连接错误事件
      socket.value.onerror = (error) => {
        log(`连接错误: ${error}`, 'error')
        lastError.value = error
      }
      } catch (error) {
      log(`创建WebSocket实例失败: ${error.message}`, 'error')
      isConnecting.value = false
      lastError.value = error
      
      // 尝试重连
      if (config.autoReconnect) {
        scheduleReconnect()
      }
    }
  }
  
  /**
   * 安排重新连接
   */
  const scheduleReconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
    }
    
    reconnectCount.value++
    
    // 使用指数退避策略计算重连延迟
    const delay = Math.min(
      config.reconnectInterval * Math.pow(1.5, reconnectCount.value - 1),
      30000 // 最大30秒
    )
    
    log(`计划在 ${delay}ms 后重新连接 (尝试 ${reconnectCount.value}/${config.reconnectAttempts})`)
    
    reconnectTimer = setTimeout(() => {
      log(`正在尝试重新连接 (${reconnectCount.value}/${config.reconnectAttempts})`)
      connect()
    }, delay)
  }
  
  /**
   * 启动心跳机制
   */
  const startHeartbeat = () => {
    if (!config.heartbeatInterval) return
    
    stopHeartbeat()
    
    heartbeatTimer = setInterval(() => {
      if (isConnected.value) {
        log('发送心跳')
        send(config.heartbeatMessage)
      }
    }, config.heartbeatInterval)
  }
  
  /**
   * 停止心跳机制
   */
  const stopHeartbeat = () => {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  /**
   * 断开WebSocket连接
   */
  const disconnect = () => {
    log('主动断开连接')
    
    // 停止自动重连和心跳
    config.autoReconnect = false
    stopHeartbeat()
    
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    
    if (socket.value && (isConnected.value || isConnecting.value)) {
      try {
      socket.value.close()
      } catch (error) {
        log(`关闭连接时出错: ${error.message}`, 'error')
      }
    }
    
    isConnected.value = false
    isConnecting.value = false
  }

  /**
   * 发送消息到服务器
   * @param {any} data 要发送的数据
   * @returns {boolean} 是否发送成功
   */
  const send = (data) => {
    if (!socket.value || !isConnected.value) {
      log('无法发送消息: 未连接', 'warn')
      return false
    }
    
    try {
      const message = typeof data === 'string' ? data : JSON.stringify(data)
      socket.value.send(message)
      return true
    } catch (error) {
      log(`发送消息失败: ${error.message}`, 'error')
      return false
    }
  }
  
  /**
   * 清空消息历史
   */
  const clearMessages = () => {
    messages.value = []
  }
  
  /**
   * 重置连接状态并重新连接
   */
  const resetAndReconnect = () => {
    disconnect()
    reconnectCount.value = 0
    lastError.value = null
    config.autoReconnect = true
    connect()
  }
  
  // 组件卸载时自动清理资源
  onUnmounted(() => {
    disconnect()
  })

  return {
    // 状态
    socket,
    messages,
    isConnected,
    isConnecting,
    reconnectCount,
    lastError,
    
    // 方法
    connect,
    disconnect,
    send,
    clearMessages,
    resetAndReconnect
  }
} 
 