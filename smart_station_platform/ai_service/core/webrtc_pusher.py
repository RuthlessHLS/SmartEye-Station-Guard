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
# aiortc 旧版本提供 MediaStreamError，新版本已移除；这里做兼容处理

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack

# 尝试从 aiortc 导入 MediaStreamError，如不存在则定义为通用 Exception
try:
    from aiortc import MediaStreamError  # type: ignore
except ImportError:  # pragma: no cover
    class MediaStreamError(Exception):
        """Fallback 兼容 aiortc 版本无 MediaStreamError 时使用"""
        pass

from aiortc.contrib.media import MediaPlayer, MediaRelay, MediaStreamTrack
from av import VideoFrame
# 导入Fraction
from fractions import Fraction

# 提前初始化 logger，避免在后续代码块中引用时报 NameError
logger = logging.getLogger(__name__)

# 可选：默认设置本模块日志级别
logger.setLevel(logging.INFO)

# --- 优先启用 H.264 / OpenH264 软编编码 ---
try:
    from aiortc import RTCRtpSender
    from aiortc.codecs import get_capabilities
    
    # 获取可用的编解码器
    video_caps = get_capabilities('video')
    h264_codecs = [c for c in video_caps.codecs if c.name == 'H264']
    
    if h264_codecs:
        # 将 H.264 编解码器移到最前面
        other_codecs = [c for c in video_caps.codecs if c.name != 'H264']
        video_caps.codecs = h264_codecs + other_codecs
        
        # 重写 getCapabilities 方法以优先返回 H.264
        _orig_get_caps = RTCRtpSender.getCapabilities
        
        def _get_caps_h264(kind: str):
            caps = _orig_get_caps(kind)
            if kind == "video":
                # 将 H.264 编解码器提到最前
                h264_codes = [c for c in caps.codecs if c.name == 'H264']
                other_codes = [c for c in caps.codecs if c.name != 'H264']
                caps.codecs = h264_codes + other_codes
            return caps
        
        RTCRtpSender.getCapabilities = staticmethod(_get_caps_h264)
        logger.info(f"已配置 aiortc 优先使用 H.264 编码，可用 H.264 编解码器: {len(h264_codecs)} 个")
    else:
        logger.warning("未找到可用的 H.264 编解码器，将使用默认编码")
        
except Exception as _e:
    logger.warning(f"无法启用 H.264 优先编码: {_e}")

# 增加日志级别，便于调试
logging.getLogger('smart_station_platform.ai_service.core.webrtc_pusher').setLevel(logging.DEBUG)  # 打开DEBUG级别帧发送日志

# 全局变量，存储所有活跃的WebRTC连接
active_connections = {}
# 全局帧缓冲区，用于存储最新的处理过的帧
frame_buffers = {}

class FrameTransformer(VideoStreamTrack):
    """
    自定义视频流轨道，用于将处理过的OpenCV帧转换为WebRTC可用的格式
    """
    kind = "video"
    
    def __init__(self, camera_id: str, target_fps: int = 18):
        super().__init__()
        self.camera_id = camera_id
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.last_frame_time = 0
        self.frame_count = 0
        self.is_running = True
        
        # --- 新增: 性能监控 ---
        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.last_fps_log = time.time()
        
        logger.info(f"FrameTransformer 初始化完成，摄像头: {camera_id}, 目标帧率: {target_fps} FPS")
    
    async def recv(self):
        """
        接收并转换帧，实现帧率控制
        """
        if not self.is_running:
            raise MediaStreamError("FrameTransformer已停止")
        
        current_time = time.time()
        
        # --- 优化: 更稳定的帧率控制 ---
        time_since_last_frame = current_time - self.last_frame_time
        
        # 确保帧间隔在合理范围内（15-20 FPS）
        min_interval = 0.05  # 50ms (20 FPS)
        max_interval = 0.067  # 67ms (15 FPS)
        
        if time_since_last_frame < min_interval:
            # 如果太快，等待到最小间隔
            await asyncio.sleep(min_interval - time_since_last_frame)
            current_time = time.time()
        elif time_since_last_frame > max_interval:
            # 如果太慢，记录警告但继续处理
            if self.frame_count % 30 == 0:
                logger.warning(f"[{self.camera_id}] FrameTransformer帧间隔过长: {time_since_last_frame*1000:.1f}ms")
        
        self.last_frame_time = current_time
        self.frame_count += 1
        
        # --- 自适应帧率调整 ---
        if self.frame_count % 60 == 0:  # 每60帧检查一次
            elapsed = current_time - self.fps_start_time
            if elapsed > 0:
                current_fps = self.frame_count / elapsed
                # 如果实际FPS远低于目标，适当降低目标
                if current_fps < self.target_fps * 0.7:
                    self.target_fps = max(15, int(current_fps * 1.2))  # 最低15fps
                    self.frame_interval = 1.0 / self.target_fps
                    logger.info(f"[{self.camera_id}] 自适应调整帧率: {self.target_fps} FPS")
                logger.debug(f"[{self.camera_id}] 当前FPS: {current_fps:.1f} (目标: {self.target_fps})")
        
        # 获取最新帧
        frame = frame_buffers.get(self.camera_id)
        
        if frame is None:
            # 如果没有帧，创建黑色帧
            logger.warning(f"摄像头 {self.camera_id} 等待新帧超时，使用黑色帧")
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 确保帧尺寸合适（WebRTC推荐尺寸）
        h, w = frame.shape[:2]
        if w > 1280 or h > 720:
            # 如果分辨率过高，缩放到720p
            scale = min(1280 / w, 720 / h)
            new_w, new_h = int(w * scale), int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
        # 转换为RGB格式（WebRTC需要）
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            frame_rgb = frame
        
        # 创建VideoFrame
        video_frame = VideoFrame.from_ndarray(frame_rgb, format="rgb24")

        # 设置时间戳
        video_frame.pts = int(current_time * 1000000)  # 微秒
        video_frame.time_base = Fraction(1, 1000000)
        
        # --- 新增: 每30帧输出一次调试信息 ---
        if self.frame_count % 30 == 0:
            try:
                logger.debug(f"[{self.camera_id}] 发送帧 #{self.frame_count}, 尺寸: {frame_rgb.shape}, 均值: {frame_rgb.mean():.1f}")
            except Exception:
                pass

        # 始终返回当前帧，确保 WebRTC 正常工作
        return video_frame
    
    def stop(self):
        """停止帧转换器"""
        self.is_running = False
        logger.info(f"FrameTransformer 已停止，摄像头: {self.camera_id}")


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
            

            
        # 直接覆盖最新帧（上一帧若未被消费会被覆盖），避免额外拷贝
        frame_buffers[camera_id] = frame

    async def push_frame_async(self, camera_id: str, frame: np.ndarray):
        """异步包装，直接调用同步方法放入线程池，避免阻塞事件循环。"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.push_frame, camera_id, frame)
    
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