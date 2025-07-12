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

# 导入AI处理器
from .face_recognition import FaceRecognizer
from .object_detection import GenericPredictor
from .fire_smoke_detection import FlameSmokeDetector

logger = logging.getLogger(__name__)

class RTMPServer:
    """RTMP服务器类，用于接收和发送RTMP流"""
    
    def __init__(self, input_url: str, output_url: str):
        self.input_url = input_url
        self.output_url = output_url
        self.process = None
        self.is_running = False
        self.frame_processors = []
        self.frame_buffer = []
        self.buffer_size = 5  # 缓存5帧用于平滑处理
        
    def add_frame_processor(self, processor: Callable):
        """添加帧处理器"""
        self.frame_processors.append(processor)
        
    async def start(self):
        """启动RTMP服务器"""
        if self.is_running:
            return
            
        try:
            # 使用ffmpeg创建RTMP服务器，添加低延迟参数
            command = [
                'ffmpeg',
                '-i', self.input_url,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-profile:v', 'baseline',
                '-x264opts', 'no-scenecut',
                '-g', '30',  # GOP大小
                '-keyint_min', '30',
                '-r', '30',  # 帧率
                '-bufsize', '1000k',
                '-maxrate', '1000k',
                '-c:a', 'aac',
                '-ar', '44100',
                '-b:a', '128k',
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
                
            # 应用所有帧处理器并获取结果
            processed_frame = frame.copy()
            detection_results = {}
            
            for processor in self.frame_processors:
                try:
                    result = await processor(processed_frame)
                    if isinstance(result, tuple):
                        processed_frame, detection = result
                        detection_results.update(detection)
                except Exception as e:
                    logger.error(f"处理器执行错误: {str(e)}")
            
            # 将处理后的帧添加到缓冲区
            self.frame_buffer.append({
                'frame': processed_frame,
                'results': detection_results
            })
            
            # 保持缓冲区大小
            if len(self.frame_buffer) > self.buffer_size:
                self.frame_buffer.pop(0)
            
            # 将处理后的帧推送到输出流
            try:
                # 创建内存缓冲区
                ret, buffer = cv2.imencode('.jpg', processed_frame)
                if ret:
                    # 将图像数据写入管道
                    self.process.stdin.write(buffer.tobytes())
                    self.process.stdin.flush()
            except Exception as e:
                logger.error(f"推送处理后的帧失败: {str(e)}")
        
        cap.release()

    def stop(self):
        """停止RTMP服务器"""
        self.is_running = False
        if self.process:
            self.process.terminate()
            self.process = None
            
    def get_latest_results(self) -> Dict:
        """获取最新的检测结果"""
        if not self.frame_buffer:
            return {}
        return self.frame_buffer[-1]['results']

class VideoStream:
    """
    视频流处理类，负责管理视频流的捕获和AI处理
    """
    
    def __init__(self, stream_url: str, predictor=None, face_recognizer=None):
        """初始化视频流处理器
        Args:
            stream_url: 视频流URL
            predictor: 已初始化的目标检测器实例
            face_recognizer: 已初始化的人脸识别器实例
        """
        self.stream_url = stream_url
        self.predictor = predictor  # 使用传入的目标检测器实例
        self.face_recognizer = face_recognizer  # 使用传入的人脸识别器实例
        self.fire_detector = None  # 火焰检测器实例
        self.cap = None
        self.is_running = False
        self.frame_count = 0
        self.last_frame = None
        self.last_frame_time = None
        self.fps = 0
        self.frame_lock = asyncio.Lock()
        self.camera_id = f"rtmp_{int(time.time() * 1000)}"  # 生成唯一的camera_id
        self.processors = []  # 处理器列表
        self.lock = threading.Lock()  # 线程锁
        self.rtmp_server = None  # RTMP服务器实例
        self._current_frame = None  # 当前帧缓存
        self._current_results = None  # 当前检测结果缓存

    async def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        异步读取一帧视频
        Returns:
            Tuple[bool, Optional[np.ndarray]]: (是否成功, 视频帧)
        """
        if not self.cap or not self.cap.isOpened():
            return False, None
            
        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                return False, None
            return True, frame
        except Exception as e:
            logger.error(f"读取视频帧时发生错误: {str(e)}")
            return False, None

    async def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """
        处理单帧视频
        Args:
            frame: 输入视频帧
        Returns:
            Tuple[np.ndarray, Dict]: (处理后的帧, 检测结果)
        """
        results = {}
        processed_frame = frame.copy()
        
        try:
            # 如果有目标检测器，执行目标检测
            if self.predictor:
                detection_results = await asyncio.get_event_loop().run_in_executor(
                    None, self.predictor.detect_objects, processed_frame
                )
                results['objects'] = detection_results
                
                # 在帧上绘制检测结果
                for obj in detection_results:
                    box = obj['bbox']
                    label = obj['label']
                    conf = obj['confidence']
                    cv2.rectangle(processed_frame, 
                                (int(box[0]), int(box[1])), 
                                (int(box[2]), int(box[3])), 
                                (0, 255, 0), 2)
                    cv2.putText(processed_frame, 
                              f"{label} {conf:.2f}", 
                              (int(box[0]), int(box[1])-10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # 如果有人脸识别器，执行人脸识别
            if self.face_recognizer:
                face_results = await asyncio.get_event_loop().run_in_executor(
                    None, self.face_recognizer.recognize_faces, processed_frame
                )
                results['faces'] = face_results
                
                # 在帧上绘制人脸识别结果
                for face in face_results:
                    box = face['bbox']
                    name = face['name']
                    conf = face['confidence']
                    cv2.rectangle(processed_frame, 
                                (int(box[0]), int(box[1])), 
                                (int(box[2]), int(box[3])), 
                                (255, 0, 0), 2)
                    cv2.putText(processed_frame, 
                              f"{name} {conf:.2f}", 
                              (int(box[0]), int(box[1])-10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            
        except Exception as e:
            logger.error(f"处理视频帧时发生错误: {str(e)}")
            traceback.print_exc()
            
        return processed_frame, results

    async def _process_frames(self):
        """处理视频帧的异步循环"""
        logger.info(f"开始处理视频流: {self.stream_url}")
        while self.is_running:
            try:
                async with self.frame_lock:
                    success, frame = await self.read_frame()
                    if not success:
                        logger.warning("读取帧失败，等待重试...")
                        await asyncio.sleep(1)
                        continue

                    # 处理帧
                    processed_frame, results = await self.process_frame(frame)
                    
                    # 更新缓存
                    self._current_frame = processed_frame
                    self._current_results = results
                    
                    # 更新帧计数和FPS
                    self.frame_count += 1
                    current_time = time.time()
                    if self.last_frame_time:
                        time_diff = current_time - self.last_frame_time
                        if time_diff > 0:
                            self.fps = 1 / time_diff
                    self.last_frame_time = current_time
                    self.last_frame = processed_frame

                # 控制帧率
                await asyncio.sleep(0.01)  # 约100fps的处理速率限制
                
            except Exception as e:
                logger.error(f"处理帧时发生错误: {str(e)}")
                traceback.print_exc()
                await asyncio.sleep(1)  # 发生错误时等待1秒再继续

    def get_current_frame(self) -> Tuple[Optional[np.ndarray], Optional[Dict]]:
        """获取当前帧和检测结果"""
        return self._current_frame, self._current_results

    async def start(self) -> bool:
        """
        启动视频流处理

        Returns:
            bool: 如果启动成功返回 True，否则返回 False
        """
        if self.is_running:
            return True

        try:
            # 初始化AI处理器
            await self.initialize_ai_processors()
            
            # 尝试打开视频流
            self.cap = cv2.VideoCapture(self.stream_url)
            if not self.cap.isOpened():
                logger.error(f"无法打开视频流: {self.stream_url}")
                return False

            # 设置视频流为运行状态
            self.is_running = True
            
            # 启动异步处理循环
            asyncio.create_task(self._process_frames())
            logger.info(f"视频流处理任务已启动: {self.stream_url}")
            
            return True
            
        except Exception as e:
            logger.error(f"启动视频流失败: {str(e)}")
            traceback.print_exc()
            self.is_running = False
            if self.cap:
                self.cap.release()
            return False

    async def start_audio_extraction(self):
        """
        启动音频提取任务。
        如果不需要音频分析，这个方法可以是空实现。
        """
        try:
            logger.info(f"音频提取功能暂未实现，跳过音频处理")
            return True
        except Exception as e:
            logger.error(f"启动音频提取时出错: {str(e)}")
            return False

    async def test_connection(self) -> bool:
        """
        测试视频流连接是否可用

        Returns:
            bool: 如果连接成功返回 True，否则返回 False
        """
        try:
            # 尝试打开视频流
            cap = cv2.VideoCapture(self.stream_url)
            if not cap.isOpened():
                logger.error(f"无法打开视频流: {self.stream_url}")
                return False

            # 尝试读取一帧
            ret, frame = cap.read()
            if not ret:
                logger.error(f"无法从视频流读取帧: {self.stream_url}")
                return False

            # 关闭视频流
            cap.release()
            return True

        except Exception as e:
            logger.error(f"测试视频流连接时出错: {str(e)}")
            return False
            
    async def initialize_ai_processors(self):
        """初始化AI处理器检查"""
        try:
            # 检查是否已经有可用的处理器实例
            if not self.predictor or not self.face_recognizer:
                logger.warning("AI处理器未完全初始化，某些功能可能不可用")
                logger.debug(f"目标检测器状态: {'可用' if self.predictor else '未初始化'}")
                logger.debug(f"人脸识别器状态: {'可用' if self.face_recognizer else '未初始化'}")
            else:
                logger.info("AI处理器检查完成，所有处理器可用")
            
            return True
        except Exception as e:
            logger.error(f"AI处理器检查失败: {str(e)}")
            return False
            
    def stop(self):
        """停止视频流处理"""
        logger.info(f"正在停止视频流: {self.stream_url}")
        self.is_running = False
        if self.cap:
            self.cap.release()
        if self.rtmp_server:
            self.rtmp_server.stop()
            self.rtmp_server = None
            
    def get_latest_results(self) -> Dict:
        """获取最新的检测结果"""
        if self.rtmp_server:
            return self.rtmp_server.get_latest_results()
        return {}