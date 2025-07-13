# 文件: ai_service/core/video_stream.py
# 描述: 负责视频流的捕获、帧的缓存、以及音频的提取。

import cv2
import time
import threading
import numpy as np
import ffmpeg  # 确保安装 ffmpeg-python
import tempfile
import os
import asyncio
import subprocess
import logging
import queue  # 用于帧缓存
from typing import Optional, Dict, Tuple, Any

# 设置日志
logger = logging.getLogger(__name__)
# 配置日志级别和格式，确保能在控制台看到详细信息
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class VideoStream:
    """
    视频流处理类，负责管理视频流的捕获、帧的缓存和音频的提取。
    它将原始帧提供给外部AI分析器，自身不直接执行复杂的AI处理。
    """

    def __init__(self, stream_url: str, camera_id: str,
                 predictor: Optional[Any] = None,  # 传入的AI检测器实例，但在此类中不再直接使用
                 face_recognizer: Optional[Any] = None,
                 fire_detector: Optional[Any] = None):
        """
        初始化视频流处理器。
        Args:
            stream_url: 视频流URL (e.g., rtmp://localhost/live/stream_name)
            camera_id: 唯一的摄像头ID
            predictor: 已初始化的目标检测器实例 (仅为兼容性传入，此处不再直接调用)
            face_recognizer: 已初始化的人脸识别器实例 (仅为兼容性传入)
            fire_detector: 已初始化的火焰烟雾检测器实例 (仅为兼容性传入)
        """
        self.stream_url = stream_url
        self.camera_id = camera_id
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running: bool = False
        self.frame_read_thread: Optional[threading.Thread] = None
        self.audio_extraction_process: Optional[subprocess.Popen] = None
        self.audio_file_path: Optional[str] = None  # 用于存储提取的音频文件路径

        # 使用线程安全的队列来缓存最新帧，供外部读取
        self._frame_buffer: queue.Queue[np.ndarray] = queue.Queue(maxsize=1)  # 只保留最新一帧

        logger.info(f"VideoStream 初始化: Camera ID={self.camera_id}, URL={self.stream_url}")

    async def test_connection(self) -> bool:
        """
        测试视频流连接是否可用。
        Returns:
            bool: 如果连接成功返回 True，否则返回 False。
        """
        try:
            logger.info(f"测试视频流连接: {self.stream_url}")
            cap = cv2.VideoCapture(self.stream_url)
            if not cap.isOpened():
                logger.error(f"无法打开视频流: {self.stream_url}")
                return False

            ret, frame = cap.read()
            if not ret or frame is None:
                logger.error(f"无法从视频流读取帧: {self.stream_url}")
                cap.release()
                return False

            cap.release()
            logger.info(f"视频流连接成功: {self.stream_url}")
            return True
        except Exception as e:
            logger.error(f"测试视频流连接时出错: {str(e)}")
            return False

    def _read_frames_thread(self):
        """
        独立的线程，负责从视频流中持续读取帧并放入缓冲区。
        """
        logger.info(f"帧读取线程启动 for {self.camera_id}.")
        self.cap = cv2.VideoCapture(self.stream_url)

        if not self.cap.isOpened():
            logger.error(f"帧读取线程无法打开视频流: {self.stream_url}")
            self.is_running = False
            return

        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                logger.warning(f"从视频流读取帧失败，可能流已结束或中断 for {self.camera_id}。尝试重新连接...")
                self.cap.release()
                time.sleep(1)  # 等待一秒后尝试重新连接
                self.cap = cv2.VideoCapture(self.stream_url)
                if not self.cap.isOpened():
                    logger.error(f"重新连接视频流失败 for {self.camera_id}，停止帧读取线程。")
                    self.is_running = False
                continue

            # 清空旧帧，放入新帧
            if not self._frame_buffer.empty():
                try:
                    self._frame_buffer.get_nowait()  # 移除旧帧
                except queue.Empty:
                    pass  # 队列已空
            self._frame_buffer.put(frame)  # 放入新帧

            # 控制帧率，避免过度消耗CPU
            # 根据实际需要调整，这里假设帧率由读取速度决定，可以增加一个sleep来限制FPS
            # time.sleep(0.01) # 例如，限制为100 FPS的读取速度

        self.cap.release()
        logger.info(f"帧读取线程停止 for {self.camera_id}.")

    def get_raw_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        获取最新读取的原始视频帧。
        Returns:
            Tuple[bool, Optional[np.ndarray]]: (是否成功获取帧, 视频帧)。
        """
        try:
            # get_nowait() 非阻塞获取，如果队列为空会抛出 Empty 异常
            frame = self._frame_buffer.get_nowait()
            return True, frame
        except queue.Empty:
            return False, None

    async def start(self) -> bool:
        """
        启动视频流处理器。
        Returns:
            bool: 如果启动成功返回 True，否则返回 False。
        """
        if self.is_running:
            logger.info(f"视频流 {self.camera_id} 已经在运行。")
            return True

        self.is_running = True
        # 启动独立的帧读取线程
        self.frame_read_thread = threading.Thread(target=self._read_frames_thread, daemon=True)
        self.frame_read_thread.start()

        # 启动后稍作等待，确保视频捕获器初始化
        await asyncio.sleep(0.5)

        if not self.cap or not self.cap.isOpened():
            logger.error(f"启动视频流失败，捕获器未成功打开 for {self.camera_id}.")
            self.is_running = False
            return False

        logger.info(f"视频流处理任务已启动: {self.stream_url} for {self.camera_id}")
        return True

    async def start_audio_extraction(self):
        """
        启动音频提取任务，使用FFmpeg从视频流中提取音频并保存到临时文件。
        该临时文件将不断被覆盖更新，以提供实时音频数据。
        """
        if self.audio_extraction_process and self.audio_extraction_process.poll() is None:
            logger.info(f"音频提取进程已在运行 for {self.camera_id}。")
            return

        # 创建临时文件来存储音频流
        # 使用 mkstemp 创建一个唯一的文件名，并立即关闭文件描述符，只保留路径
        fd, path = tempfile.mkstemp(suffix=".aac", prefix=f"audio_{self.camera_id}_", dir=None)
        os.close(fd)  # 关闭文件描述符

        self.audio_file_path = path
        logger.info(f"音频将提取到临时文件: {self.audio_file_path}")

        try:
            # 使用 ffmpeg 持续提取音频并覆盖到临时文件
            # -i input_url: 输入流
            # -vn: 不包含视频流
            # -acodec aac: 音频编码为 AAC
            # -ar 44100: 采样率 44100 Hz
            # -b:a 128k: 音频比特率 128 kbps
            # -f adts: 输出格式为 ADTS (AAC的传输流格式)
            # -y: 覆盖输出文件
            # -map 0:a: 只映射第一个输入流的音频部分
            # -loglevel quiet: 减少 ffmpeg 的输出信息
            # -copyts: 复制时间戳，避免pts问题
            # -vsync 0: 不强制视频同步，以保持音频连续性
            command = [
                'ffmpeg',
                '-i', self.stream_url,
                '-vn',  # no video
                '-acodec', 'aac',
                '-ar', '44100',
                '-b:a', '128k',
                '-f', 'adts',  # ADTS格式以便于实时写入和读取
                '-y',  # overwrite output file
                '-map', '0:a',  # only map audio stream from input
                '-loglevel', 'error',  # only show errors from ffmpeg
                '-copyts',  # copy timestamps
                '-vsync', '0',  # Disable video sync, just stream audio
                self.audio_file_path
            ]

            # 使用 subprocess.Popen 启动 ffmpeg 进程
            self.audio_extraction_process = subprocess.Popen(command,
                                                             stdout=subprocess.PIPE,
                                                             stderr=subprocess.PIPE)
            logger.info(f"FFmpeg 音频提取进程已启动 for {self.camera_id}。PID: {self.audio_extraction_process.pid}")

            # 启动一个独立协程来监控 FFmpeg 错误输出
            asyncio.create_task(self._monitor_ffmpeg_stderr())

        except Exception as e:
            logger.error(f"启动FFmpeg音频提取时出错 for {self.camera_id}: {str(e)}")
            self.audio_extraction_process = None
            self.audio_file_path = None
            return False
        return True

    async def _monitor_ffmpeg_stderr(self):
        """监控FFmpeg进程的错误输出"""
        if self.audio_extraction_process and self.audio_extraction_process.stderr:
            for line in self.audio_extraction_process.stderr:
                decoded_line = line.decode(errors='ignore').strip()
                if decoded_line:
                    logger.warning(f"FFmpeg stderr ({self.camera_id}): {decoded_line}")
            await self.audio_extraction_process.wait()  # 等待进程结束
            logger.info(f"FFmpeg stderr 监控器停止 for {self.camera_id}.")

    def get_audio_file(self) -> Optional[str]:
        """
        获取当前音频文件的路径。
        Returns:
            Optional[str]: 音频文件的路径，如果未启动则为 None。
        """
        return self.audio_file_path

    async def stop(self):
        """
        停止视频流处理和音频提取进程，并清理资源。
        """
        logger.info(f"正在停止视频流: {self.stream_url} for {self.camera_id}")
        self.is_running = False  # 停止帧读取线程

        if self.frame_read_thread and self.frame_read_thread.is_alive():
            self.frame_read_thread.join(timeout=5)  # 等待线程结束
            if self.frame_read_thread.is_alive():
                logger.warning(f"帧读取线程未能正常停止 for {self.camera_id}.")

        if self.cap:
            self.cap.release()
            self.cap = None
            logger.info(f"视频捕获器已释放 for {self.camera_id}.")

        if self.audio_extraction_process:
            try:
                self.audio_extraction_process.terminate()  # 尝试终止进程
                await asyncio.sleep(0.5)  # 等待进程结束
                if self.audio_extraction_process.poll() is None:
                    self.audio_extraction_process.kill()  # 如果未终止，强制杀死
                logger.info(f"FFmpeg 音频提取进程已终止 for {self.camera_id}.")
            except Exception as e:
                logger.error(f"终止FFmpeg进程时出错 for {self.camera_id}: {str(e)}")
            self.audio_extraction_process = None

        if self.audio_file_path and os.path.exists(self.audio_file_path):
            try:
                os.remove(self.audio_file_path)  # 清理临时音频文件
                logger.info(f"临时音频文件已删除: {self.audio_file_path}")
            except Exception as e:
                logger.error(f"删除临时音频文件时出错: {str(e)}")
            self.audio_file_path = None

        logger.info(f"视频流 {self.camera_id} 资源清理完成。")

    def update_settings(self, settings: Dict) -> bool:
        """
        更新AI分析设置（此方法在此类中不再有直接作用，但为兼容性保留）。
        Args:
            settings: 包含AI分析设置的字典
        Returns:
            bool: 更新是否成功
        """
        logger.info(f"VideoStream收到了更新AI分析设置的请求，但本类不直接处理AI逻辑。设置: {settings}")
        return True

