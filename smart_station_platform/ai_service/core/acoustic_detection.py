import os
import sys
import asyncio
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict

import ffmpeg
import numpy as np
import requests
import torch
from panns_inference import AudioTagging
from concurrent.futures import ThreadPoolExecutor

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s')
logger = logging.getLogger('SmartAcousticDetector_PANNs_Auto')


class SmartAcousticDetector:
    SAMPLE_RATE = 32000
    CHUNK_BYTES = SAMPLE_RATE * 2  # 16bit音频采样

    def __init__(self,
                 target_events_map: Dict[str, str],
                 camera_id: str,
                 backend_url: str,
                 api_key: str,
                 confidence_threshold: float = 0.4,
                 event_cooldown: float = 10.0):
        self.target_events_map = target_events_map
        self.camera_id = camera_id
        self.backend_url = backend_url
        self.api_key = api_key
        self.confidence_threshold = confidence_threshold
        self.event_cooldown = event_cooldown

        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.last_events = {}
        self.is_running = False
        self.ffmpeg_process = None
        self.processing_task = None
        self.executor = ThreadPoolExecutor(max_workers=1)

        self.alert_api_endpoint = f"{self.backend_url}/api/alert/receive"

        self._load_panns_model()

    def _load_panns_model(self):
        logger.info("正在加载 PANNs 模型 (本地标签文件)...")
        try:
            self.model = AudioTagging(checkpoint_path=None, device=self.device,labels_csv_path='smart_station_platform/ai_service/assets/models/class_labels_indices.csv')
            self.class_names = self.model.labels
            logger.info(f"PANNs 模型加载成功，共 {len(self.class_names)} 个类别。")
        except Exception as e:
            logger.error(f"加载 PANNs 模型时发生严重错误: {e}", exc_info=True)
            raise

    def _should_report_event(self, backend_event_type: str) -> bool:
        now = datetime.now()
        last_time = self.last_events.get(backend_event_type)
        if last_time and (now - last_time).total_seconds() < self.event_cooldown:
            return False
        self.last_events[backend_event_type] = now
        return True

    def _send_alert_to_backend(self, backend_event_type: str, confidence: float):
        payload = {
            "camera_id": self.camera_id,
            "event_type": backend_event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": float(confidence),
            "location": {
                "sensor_type": "acoustic",
                "source_id": self.camera_id
            }
        }
        headers = {"Content-Type": "application/json", "X-API-Key": self.api_key}
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, lambda: requests.post(self.alert_api_endpoint, json=payload, headers=headers, timeout=5))
        except Exception as e:
            logger.error(f"[{self.camera_id}] 提交告警到线程池时出错: {e}")

    def _process_audio_chunk(self, audio_chunk: bytes):
        try:
            waveform = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            if waveform.size == 0:
                return
            clipwise_output, _ = self.model.inference(waveform[None, :])
            scores = clipwise_output[0]
            for i, score in enumerate(scores):
                if score >= self.confidence_threshold:
                    panns_event_name = self.class_names[i]
                    if panns_event_name in self.target_events_map:
                        backend_event_type = self.target_events_map[panns_event_name]
                        if self._should_report_event(backend_event_type):
                            self._send_alert_to_backend(backend_event_type, score)
        except Exception as e:
            logger.error(f"[{self.camera_id}] 处理音频块时发生错误: {e}", exc_info=True)

    async def _run_processing_loop(self):
        loop = asyncio.get_event_loop()
        logger.info(f"[{self.camera_id}] 音频处理循环已启动。")
        while self.is_running and self.ffmpeg_process:
            audio_chunk = await loop.run_in_executor(self.executor, self.ffmpeg_process.stdout.read, self.CHUNK_BYTES)
            if not audio_chunk:
                logger.info(f"[{self.camera_id}] 音频流已结束。")
                break
            self._process_audio_chunk(audio_chunk)
        logger.info(f"[{self.camera_id}] 音频处理循环已终止。")
        await self.stop()

    async def start(self, video_url: str) -> bool:
        if self.is_running:
            return True
        logger.info(f"[{self.camera_id}] 正在启动声学监控，音频源: {video_url}")

        try:
            args = (
                ffmpeg.input(video_url, thread_queue_size=512)
                .output('-', format='s16le', acodec='pcm_s16le', ac=1, ar=self.SAMPLE_RATE, loglevel='error')
                .get_args()
            )
            logger.info(f"FFmpeg 命令参数: ffmpeg {' '.join(args)}")

            self.ffmpeg_process = subprocess.Popen(
                ['ffmpeg'] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )

            self.is_running = True
            self.processing_task = asyncio.create_task(self._run_processing_loop())

            logger.info(f"[{self.camera_id}] FFmpeg进程和音频处理任务已成功启动。")
            return True

        except FileNotFoundError:
            logger.error("系统找不到 'ffmpeg.exe'，请确认已安装并添加到 PATH。")
            return False
        except Exception as e:
            logger.error(f"[{self.camera_id}] 启动声学监控异常: {e}", exc_info=True)
            return False

    async def stop(self):
        if not self.is_running:
            return
        logger.info(f"[{self.camera_id}] 正在停止声学监控...")
        self.is_running = False

        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass

        if self.ffmpeg_process:
            if self.ffmpeg_process.poll() is None:
                self.ffmpeg_process.terminate()
                try:
                    self.ffmpeg_process.wait(timeout=5)
                except Exception:
                    self.ffmpeg_process.kill()
            self.ffmpeg_process = None

        logger.info(f"[{self.camera_id}] 声学监控已完全停止。")


# --- 模块独立测试入口 ---
if __name__ == '__main__':
    async def test_run():
        logger.info("声学检测模块(PANNs本地版)以独立模式运行，启动测试...")
        TEST_VIDEO_URL = "https://www.w3schools.com/html/mov_bbb.mp4"
        TEST_CAMERA_ID = "test_cam_panns_local_01"
        TEST_BACKEND_URL = "http://localhost:8000"
        TEST_API_KEY = "smarteye-ai-service-key-2024"

        TEST_EVENT_MAP = {
            "Screaming": "abnormal_sound_scream",
            "Speech": "other",
            "Music": "other",
            "Glass": "abnormal_sound_glass_break",
            "Clapping": "other"
        }

        detector = SmartAcousticDetector(
            target_events_map=TEST_EVENT_MAP,
            camera_id=TEST_CAMERA_ID,
            backend_url=TEST_BACKEND_URL,
            api_key=TEST_API_KEY,
            confidence_threshold=0.25
        )

        if not await detector.start(TEST_VIDEO_URL):
            logger.error("测试启动失败，程序退出。")
            return

        try:
            logger.info("监控已启动，将运行30秒或直到视频结束。按 Ctrl+C 可提前停止。")
            if detector.processing_task:
                await asyncio.wait_for(detector.processing_task, timeout=30.0)
        except asyncio.TimeoutError:
            logger.info("达到30秒测试时长。")
        except KeyboardInterrupt:
            logger.info("收到用户中断信号。")
        finally:
            await detector.stop()
            logger.info("测试程序已关闭。")

    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(test_run())
    except Exception as e:
        logger.error(f"测试主程序发生错误: {e}", exc_info=True)
