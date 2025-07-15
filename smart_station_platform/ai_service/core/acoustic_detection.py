# 文件: ai_service/core/acoustic_detection.py
# 描述: 智能声学事件检测器模块。
#       功能: 从视频流实时提取音频，使用YAMNet模型识别特定声音事件，并通过API上报。
#       特点: 封装良好，异步设计，支持与主应用并行运行。

import asyncio
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, Set, Optional

import ffmpeg
import numpy as np
import pandas as pd
import requests
import tensorflow as tf
import tensorflow_hub as hub

# --- 模块级日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SmartAcousticDetector')


class SmartAcousticDetector:
    """
    一个封装良好的智能声学检测器。
    它能从指定的视频URL中实时提取音频流，使用YAMNet模型进行分析，
    并将检测到的目标事件通过HTTP POST请求上报给后端服务。
    """

    def __init__(self,
                 target_events_map: Dict[str, str],
                 camera_id: str,
                 backend_url: str,
                 api_key: str,
                 confidence_threshold: float = 0.4,
                 event_cooldown: float = 10.0):
        """
        初始化智能声学检测器。

        Args:
            target_events_map (Dict[str, str]):
                一个字典，将YAMNet事件名映射到后端可识别的事件类型。
                示例: {"Screaming": "abnormal_sound_scream", "Glass": "abnormal_sound_glass_break"}
            camera_id (str):
                此声学传感器关联的摄像头ID，用于音视频联动。
            backend_url (str):
                用于接收告警的后端服务器地址 (例如 "http://localhost:8000")。
            api_key (str):
                与后端通信的API密钥。
            confidence_threshold (float, optional):
                识别事件所需的最低置信度。默认为 0.4。
            event_cooldown (float, optional):
                同一类型事件的冷却时间（秒）。默认为 10.0。
        """
        # --- 核心属性 ---
        self.is_running = False
        self.ffmpeg_process: Optional[asyncio.subprocess.Process] = None
        self.processing_task: Optional[asyncio.Task] = None

        # --- 配置参数 ---
        self.target_events_map = target_events_map
        self.confidence_threshold = confidence_threshold
        self.event_cooldown = event_cooldown

        # --- 联动与上报配置 ---
        self.camera_id = camera_id
        self.alert_api_endpoint = f"{backend_url.rstrip('/')}/api/alerts/ai-results/"
        self.api_key = api_key

        # --- 事件冷却机制 ---
        self.last_events: Dict[str, datetime] = {}

        # --- 模型与音频参数 (YAMNet固定) ---
        self.yamnet_model = None
        self.class_names: list = []
        self.SAMPLE_RATE = 16000
        self.CHUNK_BYTES = int(self.SAMPLE_RATE * 1.0 * 2)  # 1秒的16-bit单声道音频数据

        # --- 在初始化时就加载模型，避免在启动时延迟 ---
        self._load_yamnet_and_class_map()

    def _load_yamnet_and_class_map(self):
        """
        加载YAMNet模型和配套的类别映射文件。
        这是一个耗时操作，建议在服务启动时调用。
        """
        if self.yamnet_model and self.class_names:
            logger.info("YAMNet模型和类别映射已加载。")
            return

        logger.info("正在加载YAMNet模型和类别映射...")
        try:
            # 1. 加载模型 (使用KerasLayer接口，更稳定)
            self.yamnet_model = hub.KerasLayer("https://tfhub.dev/google/yamnet/1", trainable=False)
            logger.info("YAMNet模型加载成功！")

            # 2. 从官方源获取类别映射CSV文件
            class_map_url = "https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv"
            self.class_names = pd.read_csv(class_map_url)['display_name'].tolist()
            logger.info(f"YAMNet类别映射加载成功！共 {len(self.class_names)} 个类别。")

        except Exception as e:
            logger.error(f"加载YAMNet时发生严重错误: {e}", exc_info=True)
            logger.error("请确保 TensorFlow, TensorFlow Hub 和 pandas 已正确安装，并且网络连接正常。")
            raise  # 抛出异常，让上层调用者知道初始化失败

    def _should_report_event(self, backend_event_type: str) -> bool:
        """判断是否应该报告该事件（冷却机制）。"""
        now = datetime.now()
        last_time = self.last_events.get(backend_event_type)
        if last_time and (now - last_time).total_seconds() < self.event_cooldown:
            return False
        self.last_events[backend_event_type] = now
        return True

    def _send_alert_to_backend(self, backend_event_type: str, confidence: float):
        """将检测到的告警事件通过HTTP POST发送到后端。"""
        payload = {
            "camera_id": self.camera_id,
            "event_type": backend_event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": float(confidence),
            "location": {"sensor_type": "acoustic", "source_id": self.camera_id},
        }
        headers = {"Content-Type": "application/json", "X-API-Key": self.api_key}

        try:
            # 使用同步的requests库，但在线程池中运行以避免阻塞事件循环
            loop = asyncio.get_running_loop()
            loop.run_in_executor(
                None,  # 使用默认线程池
                lambda: requests.post(self.alert_api_endpoint, json=payload, headers=headers, timeout=5)
            )
            logger.info(f"[{self.camera_id}] 告警事件 '{backend_event_type}' 已异步发送到后端。")
        except Exception as e:
            logger.error(f"[{self.camera_id}] 提交告警到线程池时出错: {e}")

    def _process_audio_chunk(self, audio_chunk: bytes):
        """分析单个音频数据块，并在检测到目标事件时触发上报。"""
        # 1. 将原始字节数据 (16-bit PCM) 转换为YAMNet需要的 float32 格式 (-1.0 to 1.0)
        waveform = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        if waveform.size == 0:
            return

        # 2. 模型推理
        scores_tensor, _, _ = self.yamnet_model(waveform)
        scores = np.mean(scores_tensor.numpy(), axis=0)

        # 3. 遍历结果，寻找目标事件
        for i, score in enumerate(scores):
            if score >= self.confidence_threshold:
                yamnet_event_name = self.class_names[i]
                if yamnet_event_name in self.target_events_map:
                    backend_event_type = self.target_events_map[yamnet_event_name]
                    if self._should_report_event(backend_event_type):
                        self._send_alert_to_backend(backend_event_type, score)

    async def _run_processing_loop(self):
        """
        一个持续从FFmpeg管道读取和处理音频的异步循环。
        这个任务在 start() 方法中被创建和启动。
        """
        logger.info(f"[{self.camera_id}] 音频处理循环已启动。")
        while self.is_running and self.ffmpeg_process:
            try:
                # 异步地从FFmpeg的标准输出管道读取一块音频数据
                audio_chunk = await self.ffmpeg_process.stdout.read(self.CHUNK_BYTES)
                if not audio_chunk:
                    logger.info(f"[{self.camera_id}] 音频流已结束。")
                    break  # 流结束，退出循环

                # 处理这一块数据
                self._process_audio_chunk(audio_chunk)

            except asyncio.CancelledError:
                logger.info(f"[{self.camera_id}] 音频处理任务被取消。")
                break
            except Exception as e:
                logger.error(f"[{self.camera_id}] 音频处理循环中发生错误: {e}", exc_info=True)
                await asyncio.sleep(1)  # 发生错误时稍作等待

        logger.info(f"[{self.camera_id}] 音频处理循环已终止。")
        # 确保在循环结束后也调用停止逻辑
        await self.stop()

    async def start(self, video_url: str) -> bool:
        """
        异步启动声学监控。

        此方法会启动一个后台FFmpeg进程来从视频URL提取音频，并创建一个
        并行的asyncio任务来处理音频数据。此方法会立即返回。

        Args:
            video_url (str): 视频源的URL (例如 "rtsp://..." 或本地文件路径)。

        Returns:
            bool: 如果成功启动则返回 True，否则返回 False。
        """
        if self.is_running:
            logger.warning(f"[{self.camera_id}] 声学监控已在运行中。")
            return True

        logger.info(f"[{self.camera_id}] 正在启动声学监控，音频源: {video_url}")
        try:
            # 构建FFmpeg命令
            args = (
                ffmpeg.input(video_url, thread_queue_size=512)
                .output('-', format='s16le', acodec='pcm_s16le', ac=1, ar=self.SAMPLE_RATE, loglevel='error')
                .get_args()
            )

            # 异步地创建和启动FFmpeg子进程
            self.ffmpeg_process = await asyncio.create_subprocess_exec(
                'ffmpeg', *args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            self.is_running = True

            # 创建并启动后台处理任务
            self.processing_task = asyncio.create_task(self._run_processing_loop())

            logger.info(f"[{self.camera_id}] FFmpeg进程和音频处理任务已成功启动。")
            return True
        except Exception as e:
            logger.error(f"[{self.camera_id}] 启动声学监控失败: {e}", exc_info=True)
            return False

    async def stop(self):
        """
        异步停止声学监控并清理所有相关资源。
        """
        if not self.is_running:
            return

        logger.info(f"[{self.camera_id}] 正在停止声学监控...")
        self.is_running = False

        # 1. 取消后台处理任务
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass  # 任务被取消是预期的行为

        # 2. 终止FFmpeg进程
        if self.ffmpeg_process and self.ffmpeg_process.returncode is None:
            try:
                self.ffmpeg_process.terminate()
                # 异步等待进程结束
                await self.ffmpeg_process.wait()
                logger.info(f"[{self.camera_id}] FFmpeg进程已终止。")
            except Exception as e:
                logger.error(f"[{self.camera_id}] 关闭FFmpeg进程时出错: {e}")
                self.ffmpeg_process.kill()  # 如果优雅终止失败，则强制杀死

        self.ffmpeg_process = None
        self.processing_task = None
        logger.info(f"[{self.camera_id}] 声学监控已完全停止。")


# --- 模块独立测试入口 ---
if __name__ == '__main__':
    async def test_run():
        """用于独立测试 SmartAcousticDetector 模块的异步函数。"""
        logger.info("声学检测模块以独立模式运行，启动测试...")

        # --- 测试配置 ---
        TEST_VIDEO_URL = "https://www.w3schools.com/html/mov_bbb.mp4"
        TEST_CAMERA_ID = "test_cam_01"
        TEST_BACKEND_URL = "http://localhost:8000"  # 假设后端服务正在运行
        TEST_API_KEY = "smarteye-ai-service-key-2024"

        # 定义我们关心的事件及其映射
        TEST_EVENT_MAP = {
            "Screaming": "abnormal_sound_scream",
            "Shout": "abnormal_sound_scream",
            "Speech": "other",  # "说话"事件
            "Music": "other",  # "音乐"事件
            "Glass": "abnormal_sound_glass_break"
        }

        # 1. 创建检测器实例
        detector = SmartAcousticDetector(
            target_events_map=TEST_EVENT_MAP,
            camera_id=TEST_CAMERA_ID,
            backend_url=TEST_BACKEND_URL,
            api_key=TEST_API_KEY,
            confidence_threshold=0.3
        )

        # 2. 启动监控
        success = await detector.start(TEST_VIDEO_URL)
        if not success:
            logger.error("测试启动失败，程序退出。")
            return

        # 3. 模拟主程序运行一段时间
        try:
            logger.info("监控已启动，将运行30秒或直到视频结束。按 Ctrl+C 可提前停止。")
            # 等待处理任务自然结束或被中断
            if detector.processing_task:
                await asyncio.wait_for(detector.processing_task, timeout=30.0)
        except asyncio.TimeoutError:
            logger.info("达到30秒测试时长。")
        except KeyboardInterrupt:
            logger.info("收到用户中断信号。")
        finally:
            # 4. 停止监控
            logger.info("正在停止测试监控...")
            await detector.stop()
            logger.info("测试程序已关闭。")


    # 运行测试
    try:
        asyncio.run(test_run())
    except Exception as e:
        print(f"测试主程序发生错误: {e}")