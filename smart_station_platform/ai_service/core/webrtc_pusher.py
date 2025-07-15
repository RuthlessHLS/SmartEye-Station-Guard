# 文件: ai_service/core/webrtc_pusher.py
# 描述: 使用WebRTC将处理后的视频帧推送到前端

import asyncio
import logging
import threading
import time
import uuid
import cv2
import numpy as np
from typing import Dict, Optional, List, Any
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer, MediaRelay, MediaStreamTrack
from av import VideoFrame

logger = logging.getLogger(__name__)

# 增加日志级别，便于调试
logger.setLevel(logging.DEBUG)

# 全局变量，存储所有活跃的WebRTC连接
active_connections = {}
# 全局帧缓冲区，用于存储最新的处理过的帧
frame_buffers = {}

class FrameTransformer(VideoStreamTrack):
    """
    自定义视频流轨道，用于将处理过的OpenCV帧转换为WebRTC可用的格式
    """
    kind = "video"
    
    def __init__(self, camera_id: str):
        super().__init__()
        self.camera_id = camera_id
        self.pts = 0
        self.frame_rate = 30  # 默认帧率
        self.frame_time = 1 / self.frame_rate
        self.last_frame = None
        self.running = True
        self._start_time = time.time()
        self.frame_count = 0
        logger.info(f"为摄像头 {camera_id} 创建FrameTransformer")
    
    async def recv(self):
        """
        从帧缓冲区获取最新帧并转换为WebRTC格式
        """
        # 计算下一帧的时间戳
        self.pts += int(self.frame_time * 90000)  # WebRTC使用90kHz时钟
        
        # 等待直到有新帧或者超时
        start_wait = time.time()
        while self.running:
            # 从全局帧缓冲区获取当前摄像头的最新帧
            frame = frame_buffers.get(self.camera_id)
            if frame is not None:
                self.last_frame = frame.copy()  # 确保深拷贝帧数据
                self.frame_count += 1
                if self.frame_count % 30 == 0:  # 每30帧记录一次日志
                    logger.debug(f"摄像头 {self.camera_id} 接收到新帧，已处理 {self.frame_count} 帧")
                break
                
            # 如果没有新帧但有上一帧，使用上一帧
            if self.last_frame is not None:
                break
                
            # 如果等待时间超过100ms，使用黑色帧
            if time.time() - start_wait > 0.1:
                logger.warning(f"摄像头 {self.camera_id} 等待新帧超时，使用黑色帧")
                self.last_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                break
                
            await asyncio.sleep(0.001)  # 短暂休眠，避免CPU空转
        
        # 如果流已停止，返回黑色帧
        if not self.running:
            logger.info(f"摄像头 {self.camera_id} 已停止运行，发送黑色帧")
            blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            video_frame = VideoFrame.from_ndarray(blank_frame, format="bgr24")
            video_frame.pts = self.pts
            video_frame.time_base = 1 / 90000
            return video_frame
        
        # 确保我们有帧可以发送
        if self.last_frame is None:
            logger.warning(f"摄像头 {self.camera_id} 无可用帧，使用黑色帧")
            self.last_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 记录帧尺寸和类型
        height, width = self.last_frame.shape[:2]
        if self.frame_count % 30 == 0:  # 每30帧记录一次日志
            logger.debug(f"摄像头 {self.camera_id} 发送帧，尺寸: {width}x{height}, 类型: {self.last_frame.dtype}")
            
        # 确保帧是BGR格式
        if len(self.last_frame.shape) != 3 or self.last_frame.shape[2] != 3:
            logger.warning(f"摄像头 {self.camera_id} 帧格式不是BGR，尝试转换")
            if len(self.last_frame.shape) == 2:  # 灰度图
                self.last_frame = cv2.cvtColor(self.last_frame, cv2.COLOR_GRAY2BGR)
        
        # 将OpenCV BGR格式转换为WebRTC可用的格式
        try:
            video_frame = VideoFrame.from_ndarray(self.last_frame, format="bgr24")
            video_frame.pts = self.pts
            video_frame.time_base = 1 / 90000
            return video_frame
        except Exception as e:
            logger.error(f"摄像头 {self.camera_id} 转换帧失败: {str(e)}")
            # 出错时返回黑色帧
            blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            video_frame = VideoFrame.from_ndarray(blank_frame, format="bgr24")
            video_frame.pts = self.pts
            video_frame.time_base = 1 / 90000
            return video_frame
    
    def stop(self):
        """停止视频流"""
        logger.info(f"摄像头 {self.camera_id} FrameTransformer停止，共处理 {self.frame_count} 帧")
        self.running = False


class WebRTCPusher:
    """
    WebRTC推流器，负责建立WebRTC连接并推送处理过的视频帧
    """
    def __init__(self):
        self.peer_connections = {}  # 存储每个摄像头的所有对等连接
        self.transformers = {}  # 存储每个摄像头的帧转换器
        logger.info("WebRTCPusher初始化")
        
    async def create_offer(self, camera_id: str) -> Dict:
        """
        为指定摄像头创建WebRTC连接offer
        
        Args:
            camera_id: 摄像头ID
            
        Returns:
            包含offer SDP和连接ID的字典
        """
        # 创建新的对等连接
        pc = RTCPeerConnection()
        connection_id = str(uuid.uuid4())
        
        # 创建或获取帧转换器
        if camera_id not in self.transformers:
            self.transformers[camera_id] = FrameTransformer(camera_id)
        
        # 将视频轨道添加到连接
        pc.addTrack(self.transformers[camera_id])
        
        # 创建offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        # 存储连接
        if camera_id not in self.peer_connections:
            self.peer_connections[camera_id] = {}
        self.peer_connections[camera_id][connection_id] = pc
        
        # 将连接添加到全局活跃连接列表
        active_connections[connection_id] = {
            "pc": pc,
            "camera_id": camera_id,
            "created_at": time.time()
        }
        
        logger.info(f"为摄像头 {camera_id} 创建了WebRTC offer，连接ID: {connection_id}")
        
        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
            "connection_id": connection_id
        }
    
    async def process_answer(self, connection_id: str, answer_sdp: str, answer_type: str) -> bool:
        """
        处理来自浏览器的WebRTC应答
        
        Args:
            connection_id: 连接ID
            answer_sdp: 应答SDP
            answer_type: 应答类型
            
        Returns:
            处理是否成功
        """
        # 查找连接
        connection_data = active_connections.get(connection_id)
        if not connection_data:
            logger.error(f"未找到连接ID: {connection_id}")
            return False
        
        pc = connection_data["pc"]
        
        # 设置远程描述
        try:
            answer = RTCSessionDescription(sdp=answer_sdp, type=answer_type)
            await pc.setRemoteDescription(answer)
            logger.info(f"已为连接 {connection_id} 设置远程描述")
            return True
        except Exception as e:
            logger.error(f"设置远程描述时出错: {e}")
            return False
    
    def push_frame(self, camera_id: str, frame: np.ndarray):
        """
        将处理过的帧推送到指定摄像头的所有WebRTC连接
        
        Args:
            camera_id: 摄像头ID
            frame: 处理过的OpenCV帧
        """
        # 检查帧是否有效
        if frame is None or frame.size == 0:
            logger.warning(f"摄像头 {camera_id} 收到无效帧，跳过")
            return
            
        # 检查帧类型和尺寸，每100帧记录一次
        if camera_id in frame_buffers and len(frame_buffers) % 100 == 0:
            height, width = frame.shape[:2]
            logger.debug(f"摄像头 {camera_id} 推送帧，尺寸: {width}x{height}, 类型: {frame.dtype}")
            
        # 将帧存储到全局帧缓冲区
        frame_buffers[camera_id] = frame.copy()
    
    async def close_connection(self, connection_id: str):
        """
        关闭指定的WebRTC连接
        
        Args:
            connection_id: 连接ID
        """
        connection_data = active_connections.get(connection_id)
        if not connection_data:
            logger.warning(f"尝试关闭不存在的连接: {connection_id}")
            return
        
        pc = connection_data["pc"]
        camera_id = connection_data["camera_id"]
        
        # 关闭连接
        await pc.close()
        
        # 从存储中移除
        if camera_id in self.peer_connections and connection_id in self.peer_connections[camera_id]:
            del self.peer_connections[camera_id][connection_id]
        
        # 从全局活跃连接中移除
        if connection_id in active_connections:
            del active_connections[connection_id]
        
        logger.info(f"已关闭连接 {connection_id}")
    
    async def close_all_camera_connections(self, camera_id: str):
        """
        关闭指定摄像头的所有WebRTC连接
        
        Args:
            camera_id: 摄像头ID
        """
        if camera_id not in self.peer_connections:
            return
        
        # 获取该摄像头的所有连接ID
        connection_ids = list(self.peer_connections[camera_id].keys())
        
        # 关闭每个连接
        for connection_id in connection_ids:
            await self.close_connection(connection_id)
        
        # 停止帧转换器
        if camera_id in self.transformers:
            self.transformers[camera_id].stop()
            del self.transformers[camera_id]
        
        # 清除帧缓冲区
        if camera_id in frame_buffers:
            del frame_buffers[camera_id]
        
        logger.info(f"已关闭摄像头 {camera_id} 的所有WebRTC连接")
    
    async def cleanup_old_connections(self, max_age_seconds: int = 300):
        """
        清理超过指定时间的旧连接
        
        Args:
            max_age_seconds: 最大连接存活时间（秒）
        """
        current_time = time.time()
        connection_ids_to_close = []
        
        # 找出所有需要关闭的连接
        for connection_id, connection_data in active_connections.items():
            age = current_time - connection_data["created_at"]
            if age > max_age_seconds:
                connection_ids_to_close.append(connection_id)
        
        # 关闭每个过时的连接
        for connection_id in connection_ids_to_close:
            await self.close_connection(connection_id)
        
        if connection_ids_to_close:
            logger.info(f"已清理 {len(connection_ids_to_close)} 个超时连接")


# 创建全局WebRTC推送器实例
webrtc_pusher = WebRTCPusher()

# 启动定期清理任务
async def start_cleanup_task():
    """启动定期清理任务，清理过时的WebRTC连接"""
    while True:
        try:
            await webrtc_pusher.cleanup_old_connections()
        except Exception as e:
            logger.error(f"清理WebRTC连接时出错: {str(e)}")
        await asyncio.sleep(60)  # 每分钟运行一次 