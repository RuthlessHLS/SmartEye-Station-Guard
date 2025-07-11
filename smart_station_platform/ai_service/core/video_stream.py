# 文件: ai_service/core/video_stream.py
import cv2
import time
import threading
import numpy as np
from typing import List, Callable, Optional, Dict, Tuple
from datetime import datetime
import traceback
import logging
import ffmpeg
import tempfile
import os
import asyncio
import subprocess
from models.alert_models import AIAnalysisResult

logger = logging.getLogger(__name__)

class RTMPServer:
    """RTMP服务器类，用于接收和发送RTMP流"""
    
    def __init__(self, input_url: str, output_url: str):
        self.input_url = input_url
        self.output_url = output_url
        self.process = None
        self.is_running = False
        self.frame_processors = []
        
    def add_frame_processor(self, processor: Callable):
        """添加帧处理器"""
        self.frame_processors.append(processor)
        
    async def start(self):
        """启动RTMP服务器"""
        if self.is_running:
            return
            
        try:
            # 使用ffmpeg创建RTMP服务器
            command = [
                'ffmpeg',
                '-i', self.input_url,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-c:a', 'aac',
                '-f', 'flv',
                self.output_url
            ]
            
            self.process = subprocess.Popen(command)
            self.is_running = True
            
            # 启动视频处理循环
            await self._process_frames()
            
        except Exception as e:
            logger.error(f"启动RTMP服务器失败: {str(e)}")
            self.stop()
            
    async def _process_frames(self):
        """处理视频帧"""
        cap = cv2.VideoCapture(self.input_url)
        
        while self.is_running:
            ret, frame = cap.read()
            if not ret:
                continue
                
            # 应用所有帧处理器
            for processor in self.frame_processors:
                frame = await processor(frame)
                
            # 将处理后的帧推送到输出流
            # 这里需要实现帧推送逻辑
            
        cap.release()
            
    def stop(self):
        """停止RTMP服务器"""
        self.is_running = False
        if self.process:
            self.process.terminate()
            self.process = None

class VideoStream:
    def __init__(self, source: str):
        """
        初始化视频流
        :param source: 视频源（可以是摄像头索引或URL）
        """
        self.source = source
        self.cap = None
        self.is_running = False
        self.frame_count = 0
        self.fps = 0
        self.last_frame_time = 0
        self.frame_times = []
        self.processing_times = []
        
    async def test_connection(self) -> bool:
        """
        测试视频流连接是否可用
        :return: 如果连接成功返回True，否则返回False
        """
        try:
            print(f"正在测试视频流连接: {self.source}")
            
            # 设置OpenCV的超时参数
            if isinstance(self.source, str):
                if self.source.startswith('rtmp://'):
                    # RTMP流需要更长的超时时间
                    os.environ['OPENCV_FFMPEG_READ_ATTEMPT_TIMEOUT'] = '5000'  # 5秒超时
                    os.environ['OPENCV_FFMPEG_READ_TIMEOUT'] = '5000'  # 5秒超时
                    print("检测到RTMP流，设置较长的超时时间")
                elif not self.source.isdigit():
                    # 其他网络流使用较短的超时时间
                    os.environ['OPENCV_FFMPEG_READ_ATTEMPT_TIMEOUT'] = '2000'  # 2秒超时
                    os.environ['OPENCV_FFMPEG_READ_TIMEOUT'] = '2000'  # 2秒超时
            
            # 尝试打开视频流
            if isinstance(self.source, str) and self.source.isdigit():
                cap = cv2.VideoCapture(int(self.source))
            else:
                # 对于RTMP流，添加特殊参数
                cap = cv2.VideoCapture(self.source)
                if self.source.startswith('rtmp://'):
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 设置缓冲区大小为1帧
            
            if not cap.isOpened():
                print(f"无法打开视频流: {self.source}")
                return False
            
            # 尝试读取前3帧，确保流是稳定的
            success = False
            for i in range(3):
                ret, frame = cap.read()
                if ret and frame is not None:
                    success = True
                    print(f"成功读取第{i+1}帧")
                    break
                await asyncio.sleep(0.5)  # 增加重试间隔
            
            # 释放资源
            cap.release()
            
            if success:
                print(f"视频流连接测试成功: {self.source}")
            else:
                print(f"视频流不稳定: {self.source}")
            
            return success
            
        except Exception as e:
            print(f"测试连接失败: {str(e)}")
            return False
    
    async def start(self):
        """启动视频流"""
        if isinstance(self.source, str) and self.source.isdigit():
            self.cap = cv2.VideoCapture(int(self.source))
        else:
            self.cap = cv2.VideoCapture(self.source)
            
        if not self.cap.isOpened():
            raise Exception(f"无法打开视频源: {self.source}")
            
        self.is_running = True
        self.frame_count = 0
        self.last_frame_time = time.time()
        
    async def stop(self):
        """停止视频流"""
        self.is_running = False
        if self.cap:
            self.cap.release()
        self.cap = None
        
    async def get_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        获取下一帧
        :return: (成功标志, 帧数据)
        """
        if not self.is_running or not self.cap:
            return False, None
            
        ret, frame = self.cap.read()
        if ret:
            self.frame_count += 1
            current_time = time.time()
            
            # 计算FPS
            if self.frame_count > 1:  # 跳过第一帧
                frame_time = current_time - self.last_frame_time
                self.frame_times.append(frame_time)
                if len(self.frame_times) > 30:  # 保持最近30帧的时间
                    self.frame_times.pop(0)
                self.fps = 1.0 / (sum(self.frame_times) / len(self.frame_times))
                
            self.last_frame_time = current_time
            
        return ret, frame
        
    def get_fps(self) -> float:
        """获取当前FPS"""
        return self.fps
        
    def get_frame_count(self) -> int:
        """获取已处理的帧数"""
        return self.frame_count
        
    def add_processing_time(self, time_ms: float):
        """
        添加处理时间记录
        :param time_ms: 处理时间（毫秒）
        """
        self.processing_times.append(time_ms)
        if len(self.processing_times) > 30:  # 保持最近30次的处理时间
            self.processing_times.pop(0)
            
    def get_avg_processing_time(self) -> float:
        """获取平均处理时间（毫秒）"""
        if not self.processing_times:
            return 0
        return sum(self.processing_times) / len(self.processing_times)
        
    async def close(self):
        """关闭视频流并释放资源"""
        await self.stop()
        
    def is_active(self) -> bool:
        """检查视频流是否活动"""
        return self.is_running and self.cap is not None and self.cap.isOpened()
        
    def get_resolution(self) -> Tuple[int, int]:
        """获取视频分辨率"""
        if not self.cap:
            return (0, 0)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (width, height)
        
    def get_status(self) -> Dict:
        """获取视频流状态信息"""
        resolution = self.get_resolution()
        return {
            "is_active": self.is_active(),
            "frame_count": self.frame_count,
            "fps": round(self.fps, 2),
            "avg_processing_time": round(self.get_avg_processing_time(), 2),
            "resolution": {
                "width": resolution[0],
                "height": resolution[1]
            }
        }

# 全局视频流管理器
active_streams: Dict[str, VideoStream] = {}