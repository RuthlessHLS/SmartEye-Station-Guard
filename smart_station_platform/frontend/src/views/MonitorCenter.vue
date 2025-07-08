<template>
  <div class="monitor-center-container">
    <h1>智能视频监控中心</h1>
    <el-row :gutter="20">
      <el-col :span="18">
        <el-card class="video-display-card">
          <template #header>
            <div class="card-header">
              <span>实时视频监控</span>
              <el-select v-model="selectedCamera" placeholder="选择摄像头" style="width: 150px;" @change="changeCamera">
                <el-option label="摄像头 A" value="camera_a"></el-option>
                <el-option label="摄像头 B" value="camera_b"></el-option>
                <el-option label="摄像头 C" value="camera_c"></el-option>
              </el-select>
            </div>
          </template>
          <div class="video-wrapper">
            <video ref="videoPlayer" class="video-player" controls autoplay muted></video>
            <canvas ref="overlayCanvas" class="overlay-canvas"></canvas>
          </div>
          <div class="control-panel">
            <el-button type="primary" @click="startMonitor">开始监控</el-button>
            <el-button type="danger" @click="stopMonitor">停止监控</el-button>
            <el-button type="warning" @click="toggleDrawMode">
              {{ isDrawing ? '退出绘制' : '绘制危险区域' }}
            </el-button>
            <el-button type="info" :disabled="!isDrawing" @click="saveArea">保存区域</el-button>
            <el-button type="info" :disabled="!isDrawing" @click="clearAreas">清除区域</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="realtime-alerts-card">
          <template #header>
            <div class="card-header">
              <span>实时告警信息</span>
            </div>
          </template>
          <el-table :data="realtimeAlerts" height="500px" style="width: 100%">
            <el-table-column prop="time" label="时间" width="90"></el-table-column>
            <el-table-column prop="type" label="类型" width="90"></el-table-column>
            <el-table-column prop="location" label="位置"></el-table-column>
          </el-table>
          <el-empty v-if="realtimeAlerts.length === 0" description="暂无告警"></el-empty>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue';
import { ElMessage } from 'element-plus';
// import WebSocket from 'ws'; // 如果需要Node.js环境下的WebSocket库，浏览器自带
// import api from '../api'; // 导入后端API服务

const selectedCamera = ref('camera_a');
const videoPlayer = ref(null);
const overlayCanvas = ref(null);
const realtimeAlerts = reactive([]);
const isDrawing = ref(false); // 是否处于绘制模式
let ctx = null; // Canvas 2D 上下文
let drawnAreas = reactive([]); // 存储已绘制的危险区域 (多边形坐标数组)
let currentDrawing = []; // 当前正在绘制的多边形点

let ws = null; // WebSocket 实例

onMounted(() => {
  // 初始化 Canvas
  if (overlayCanvas.value) {
    ctx = overlayCanvas.value.getContext('2d');
    // 确保Canvas尺寸与视频容器一致
    const videoRect = videoPlayer.value.getBoundingClientRect();
    overlayCanvas.value.width = videoRect.width;
    overlayCanvas.value.height = videoRect.height;
  }
  // 模拟视频流 (实际中会通过API获取RTSP/HTTP流并用videojs/flv.js等播放)
  // videoPlayer.value.src = 'your_rtsp_stream_url_or_mock_video.mp4';
  // videoPlayer.value.play();

  // 连接 WebSocket
  connectWebSocket();

  // 模拟AI分析结果和告警推送（开发阶段用于测试）
  // setInterval(mockAIResults, 3000);
});

onUnmounted(() => {
  // 关闭 WebSocket 连接
  if (ws) {
    ws.close();
  }
});

const connectWebSocket = () => {
  // 确保WebSocket连接到Django后端channels的地址
  ws = new WebSocket('ws://127.0.0.1:8000/ws/alerts/');

  ws.onopen = () => {
    ElMessage.success('WebSocket 连接成功！');
    console.log('WebSocket connected');
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'alert' && data.data) {
      realtimeAlerts.unshift({ // 新告警添加到列表顶部
        time: new Date().toLocaleTimeString(),
        type: data.data.event_type || '未知异常',
        location: `相机 ${data.data.camera_id || 'N/A'}` // 可以细化位置信息
      });
      // 保持列表长度，避免无限增长
      if (realtimeAlerts.length > 20) {
        realtimeAlerts.pop();
      }
      // 可以在Canvas上绘制告警区域的闪烁效果
      drawAlertArea(data.data.location);
    }
  };

  ws.onclose = () => {
    ElMessage.warning('WebSocket 连接已断开！尝试重连...');
    console.log('WebSocket disconnected. Reconnecting...');
    setTimeout(connectWebSocket, 5000); // 5秒后尝试重连
  };

  ws.onerror = (error) => {
    ElMessage.error('WebSocket 连接错误！');
    console.error('WebSocket error:', error);
  };
};

const mockAIResults = () => {
  // 模拟 AI 推送告警数据到后端，后端再通过WebSocket推送回来
  // 实际中，这会由AI服务发起HTTP POST请求到后端 /api/alerts/ai-results/
  const mockAlertData = {
    camera_id: selectedCamera.value,
    event_type: '陌生人闯入',
    timestamp: new Date().toISOString(),
    location: { x: Math.random(), y: Math.random(), width: 0.1, height: 0.1 }, // 模拟位置
    confidence: 0.95
  };
  // 理论上这里不直接调用 ws.send，而是模拟AI服务向后端发送HTTP请求
  // 然后后端收到请求后，通过 channels 发送给 ws
  // 为了快速测试，这里暂时直接通过WebSocket发送模拟数据
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'alert', data: mockAlertData }));
  }
};


const startMonitor = () => {
  ElMessage.success('开始监控！');
  // 实际的视频流启动逻辑，例如请求后端提供特定摄像头的流
  // api.post('/cameras/start_stream/', { camera_id: selectedCamera.value });
};

const stopMonitor = () => {
  ElMessage.info('停止监控！');
  // 实际的视频流停止逻辑
  // api.post('/cameras/stop_stream/', { camera_id: selectedCamera.value });
};

const toggleDrawMode = () => {
  isDrawing.value = !isDrawing.value;
  if (isDrawing.value) {
    ElMessage.info('进入绘制模式，请在视频上点击绘制多边形。');
    overlayCanvas.value.addEventListener('click', handleCanvasClick);
  } else {
    ElMessage.info('退出绘制模式。');
    overlayCanvas.value.removeEventListener('click', handleCanvasClick);
    currentDrawing = []; // 清除当前绘制点
    redrawAreas(); // 重新绘制已保存区域
  }
};

const handleCanvasClick = (event) => {
  const rect = overlayCanvas.value.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  currentDrawing.push({ x, y });
  redrawAreas(); // 每次点击后重绘
  drawCurrentDrawing(); // 绘制当前正在画的多边形
};

const redrawAreas = () => {
  ctx.clearRect(0, 0, overlayCanvas.value.width, overlayCanvas.value.height);
  // 绘制所有已保存的区域
  drawnAreas.forEach(area => {
    drawPolygon(area, 'rgba(255, 0, 0, 0.3)', 'red'); // 红色半透明填充，红色边框
  });
};

const drawCurrentDrawing = () => {
  if (currentDrawing.length < 1) return;
  ctx.beginPath();
  ctx.moveTo(currentDrawing[0].x, currentDrawing[0].y);
  for (let i = 1; i < currentDrawing.length; i++) {
    ctx.lineTo(currentDrawing[i].x, currentDrawing[i].y);
  }
  ctx.strokeStyle = 'yellow'; // 正在绘制的线条颜色
  ctx.lineWidth = 2;
  ctx.stroke();
  // 如果点多于一个，绘制连接第一个点和当前鼠标位置的虚线
  // (这里为了简化不实现实时鼠标跟踪，只画点击的点)
};

const drawPolygon = (points, fillStyle, strokeStyle) => {
  if (points.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i++) {
    ctx.lineTo(points[i].x, points[i].y);
  }
  ctx.closePath(); // 闭合路径
  ctx.fillStyle = fillStyle;
  ctx.strokeStyle = strokeStyle;
  ctx.lineWidth = 2;
  ctx.fill();
  ctx.stroke();
};

const drawAlertArea = (location) => {
  // 假设location是 { x, y, width, height }
  // 实际中可能需要根据 AI 传来的坐标类型进行转换
  if (!location || !overlayCanvas.value) return;

  const canvasWidth = overlayCanvas.value.width;
  const canvasHeight = overlayCanvas.value.height;

  // 假设 location 已经是相对坐标 0-1
  const alertX = location.x * canvasWidth;
  const alertY = location.y * canvasHeight;
  const alertWidth = location.width * canvasWidth;
  const alertHeight = location.height * canvasHeight;

  // 绘制闪烁矩形
  let alpha = 0.5;
  let direction = 1; // 1 for increasing, -1 for decreasing
  let intervalId = setInterval(() => {
    redrawAreas(); // 每次闪烁前重绘所有静态区域
    ctx.fillStyle = `rgba(255, 0, 0, ${alpha})`;
    ctx.strokeStyle = 'red';
    ctx.lineWidth = 3;
    ctx.fillRect(alertX, alertY, alertWidth, alertHeight);
    ctx.strokeRect(alertX, alertY, alertWidth, alertHeight);

    alpha += direction * 0.1;
    if (alpha >= 0.8 || alpha <= 0.2) {
      direction *= -1; // Change direction
    }
  }, 100); // Flash every 100ms

  // 停止闪烁，例如 5 秒后
  setTimeout(() => {
    clearInterval(intervalId);
    redrawAreas(); // 停止后重绘一次，清除闪烁效果
  }, 5000);
};


const saveArea = () => {
  if (currentDrawing.length < 3) {
    ElMessage.warning('请至少绘制三个点来形成一个多边形区域！');
    return;
  }
  drawnAreas.push([...currentDrawing]); // 保存当前绘制的多边形
  // 将多边形坐标发送到后端API保存 (例如 /api/cameras/dangerous_areas/)
  // 这里的坐标可能需要转换为后端接受的格式（如相对视频尺寸的百分比）
  const normalizedArea = currentDrawing.map(p => ({
    x: p.x / overlayCanvas.value.width,
    y: p.y / overlayCanvas.value.height
  }));
  // api.post('/cameras/dangerous_areas/', { camera_id: selectedCamera.value, area_coords: normalizedArea });
  ElMessage.success('危险区域已保存！');
  currentDrawing = []; // 清空当前绘制
  isDrawing.value = false;
  overlayCanvas.value.removeEventListener('click', handleCanvasClick);
  redrawAreas(); // 重新绘制所有区域
};

const clearAreas = () => {
  drawnAreas = reactive([]); // 清空所有已保存区域
  currentDrawing = [];
  redrawAreas();
  ElMessage.info('所有危险区域已清除！');
  // 如果需要，通知后端也清除
  // api.delete('/cameras/dangerous_areas/', { data: { camera_id: selectedCamera.value } });
};

const changeCamera = () => {
  ElMessage.info(`切换到 ${selectedCamera.value}`);
  // 实际中可能需要停止当前视频流，加载新摄像头的流，并清除或加载该摄像头对应的危险区域
  realtimeAlerts.splice(0, realtimeAlerts.length); // 清空告警列表
  clearAreas(); // 清空当前绘制区域
};
</script>

<style scoped>
.monitor-center-container {
  padding: 20px;
}
.monitor-center-container h1 {
  text-align: center;
  margin-bottom: 20px;
}
.video-display-card {
  min-height: 500px;
}
.video-display-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 1.1em;
  font-weight: bold;
}
.video-wrapper {
  position: relative;
  width: 100%;
  padding-bottom: 56.25%; /* 16:9 比例 */
  background-color: black;
  overflow: hidden;
}
.video-player, .overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain; /* 保持视频比例 */
}
.overlay-canvas {
  pointer-events: none; /* 默认不响应鼠标事件 */
}
.control-panel {
  margin-top: 20px;
  display: flex;
  justify-content: center;
  gap: 10px;
}
.realtime-alerts-card {
  min-height: 500px;
}
.realtime-alerts-card .card-header {
  font-size: 1.1em;
  font-weight: bold;
  text-align: center;
}
.realtime-alerts-card .el-table {
  margin-top: 10px;
}
</style>
