import { ref } from 'vue'

export function useWebSocket(url) {
  const socket = ref(null)
  const messages = ref([])
  const isConnected = ref(false)

  const connect = () => {
    socket.value = new WebSocket(url)

    socket.value.onopen = () => {
      console.log('WebSocket 连接已建立')
      isConnected.value = true
    }

    socket.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        messages.value.push(data)
      } catch (error) {
        console.error('解析 WebSocket 消息失败:', error)
      }
    }

    socket.value.onclose = () => {
      console.log('WebSocket 连接已关闭')
      isConnected.value = false
      // 尝试重新连接
      setTimeout(connect, 5000)
    }

    socket.value.onerror = (error) => {
      console.error('WebSocket 错误:', error)
      socket.value.close()
    }
  }

  const disconnect = () => {
    if (socket.value) {
      socket.value.close()
    }
  }

  const send = (data) => {
    if (socket.value && isConnected.value) {
      socket.value.send(JSON.stringify(data))
    }
  }

  return {
    messages,
    isConnected,
    connect,
    disconnect,
    send
  }
} 