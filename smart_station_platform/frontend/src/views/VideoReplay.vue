<template>
  <div class="video-replay" style="padding: 24px;">
    <el-card>
      <template #header>
        <span>📼 视频回放</span>
      </template>
      <div class="controls" style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center;">
        <el-input v-model="cameraId" placeholder="摄像头ID" style="width: 120px;" />
        <el-date-picker
          v-model="startTime"
          type="datetime"
          placeholder="起始时间"
          format="YYYY-MM-DD HH:mm:ss"
        />
        <el-input-number
          v-model="duration"
          :min="10"
          :max="300"
          :step="10"
          label="时长(秒)"
        />
        <el-button type="primary" @click="loadReplay">加载回放</el-button>
      </div>

      <video
        ref="videoEl"
        style="width: 100%; margin-top: 16px; background: #000;"
        controls
        playsinline
      ></video>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import Hls from 'hls.js'
import api from '@/api'

const cameraId = ref('1')
const startTime = ref(new Date(Date.now() - 60 * 1000)) // 默认前一分钟
const duration = ref(60)
const videoEl = ref(null)
let hlsInstance = null

const loadReplay = async () => {
  try {
    // 销毁旧实例
    if (hlsInstance) {
      hlsInstance.destroy()
      hlsInstance = null
    }

    const params = {
      camera_id: cameraId.value,
      start: startTime.value.toISOString(),
      duration: duration.value
    }

    // 后端直接返回 m3u8 文本
    const m3u8Text = await api.playback.get(params)

    // 创建本地 URL 供 hls.js 播放
    const blob = new Blob([m3u8Text], { type: 'application/vnd.apple.mpegurl' })
    const objectUrl = URL.createObjectURL(blob)

    if (Hls.isSupported()) {
      hlsInstance = new Hls()
      hlsInstance.loadSource(objectUrl)
      hlsInstance.attachMedia(videoEl.value)
    } else if (videoEl.value.canPlayType('application/vnd.apple.mpegurl')) {
      videoEl.value.src = objectUrl
    } else {
      console.error('HLS 不被当前浏览器支持')
    }
  } catch (err) {
    console.error('加载回放失败', err)
  }
}
</script> 