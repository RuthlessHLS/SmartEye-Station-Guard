import os
import sys
import asyncio
import logging
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple
from collections import deque
import threading
import time

import ffmpeg
import numpy as np
import scipy.fft
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
                 confidence_threshold: float = 0.2,
                 event_cooldown: float = 5.0,
                 event_history_seconds: int = 3):
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

        # --- 新增: 用于音视频联动的事件缓存 ---
        # 元素结构: (timestamp, event_name, confidence)
        self.recent_events_queue = deque(maxlen=100)  # 存储最近的事件，限制最大数量
        self.event_history_seconds = event_history_seconds  # 事件有效时长
        self._lock = threading.Lock()  # 线程锁，确保队列操作安全

        # 与其他AI告警保持一致，统一使用 Django 后端 alerts/ai-results 接口
        self.alert_api_endpoint = f"{self.backend_url}/api/alert/receive"

        # 上次属性广播时间
        self._last_prop_ts = 0.0
        self.last_props = {}  # <== 新增: 存储最近一次计算的声学属性

        self._load_panns_model()
        # 移除自动模拟线程
        # self._simulate_thread = threading.Thread(target=self._simulate_loop, daemon=True)
        # self._simulate_thread.start()

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
        headers = {
            "Content-Type": "application/json",
            # 与 InternalAPIMiddleware 一致的内部鉴权头
            "X-Internal-API-Key": self.api_key,
        }
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, lambda: requests.post(self.alert_api_endpoint, json=payload, headers=headers, timeout=5))
        except Exception as e:
            logger.error(f"[{self.camera_id}] 提交告警到线程池时出错: {e}")

    def _process_audio_chunk(self, audio_chunk: bytes):
        logger.info(f"[{self.camera_id}] _process_audio_chunk 被调用")
        try:
            waveform = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            if waveform.size == 0:
                logger.info(f"[{self.camera_id}] waveform.size == 0，跳过处理")
                return
            clipwise_output, _ = self.model.inference(waveform[None, :])
            scores = clipwise_output[0]
            now = datetime.now()

            for i, score in enumerate(scores):
                if score >= self.confidence_threshold:
                    panns_event_name = self.class_names[i]
                    if panns_event_name in self.target_events_map:
                        
                        # 1. 缓存事件用于音视频联动
                        with self._lock:
                            self.recent_events_queue.append((now, panns_event_name, float(score)))

                        # 2. 对非打架相关的特定事件，仍然可以立即发送告警
                        #    打架告警将由行为分析模块根据音视频融合结果决定
                        fight_related_cues = {"Screaming", "Shouting", "Yell"}
                        if panns_event_name not in fight_related_cues:
                            backend_event_type = self.target_events_map[panns_event_name]
                            if self._should_report_event(backend_event_type):
                                self._send_alert_to_backend(backend_event_type, score)
        except Exception as e:
            logger.error(f"[{self.camera_id}] 处理音频块时发生错误: {e}", exc_info=True)

        # --- 定时广播声学信息，每秒一次 ---
        now_ts = time.time()
        if now_ts - self._last_prop_ts >= 1.0:
            props = self._extract_wave_props(waveform)
            logger.info(f"[{self.camera_id}] waveform.size={waveform.size}, props(before check)={props}")
            if props is None:
                props = {}
            # 新增: 记录最近一次声学属性，供外部查询
            self.last_props = props or {}
            recent = self.get_recent_events(self.event_history_seconds)
            logger.info(f"[{self.camera_id}] props: {props}, events: {recent}")
            message = {
                "type": "acoustic_events",
                "data": {
                    "timestamp": now_ts,
                    "props": props,      # rms / db / freq
                    "events": recent     # [{'name':..., 'confidence':...}, ...]
                },
            }
            try:
                self._broadcast_ws(message)
            except Exception as e:
                logger.debug(f"[{self.camera_id}] 广播声学信息失败: {e}")
            self._last_prop_ts = now_ts

    # ---------------- 声波属性提取与广播 ----------------
    def _extract_wave_props(self, waveform: np.ndarray) -> Dict[str, float]:
        """计算 RMS、dB 以及主频"""
        rms = float(np.sqrt(np.mean(np.square(waveform))))
        db = 20 * np.log10(rms + 1e-12)

        # 主频 (简易)：对前 2048 样本做 FFT
        N = 2048
        if len(waveform) < N:
            return {"rms": rms, "db": db, "freq": 0.0}

        window = np.hanning(N)
        fft_vals = np.abs(scipy.fft.rfft(waveform[:N] * window))
        freqs = scipy.fft.rfftfreq(N, 1 / self.SAMPLE_RATE)
        dom_idx = int(np.argmax(fft_vals))
        dom_freq = float(freqs[dom_idx])
        return {"rms": rms, "db": db, "freq": dom_freq}

    def _broadcast_ws(self, payload: Dict):
        """通过后端广播接口推送 WebSocket 消息"""
        try:
            url = f"{self.backend_url}/api/alerts/websocket/broadcast/"
            requests.post(url, json={
                "camera_id": self.camera_id,
                "payload": payload,
            }, headers={"X-Internal-API-Key": self.api_key}, timeout=2)
        except Exception as e:
            logger.debug(f"[{self.camera_id}] _broadcast_ws error: {e}")

    def get_recent_events(self, since_seconds: int = 3) -> List[Dict[str, float]]:
        """
        获取指定时间窗口内发生过的所有声音事件及置信度。
        此方法是线程安全的，专为音视频联动分析提供数据。
        """
        recent_events = []
        cutoff_time = datetime.now() - timedelta(seconds=since_seconds)
        
        with self._lock:
            # 清理过期事件
            while self.recent_events_queue and self.recent_events_queue[0][0] < cutoff_time:
                self.recent_events_queue.popleft()
            
            # 提取仍在有效期内的事件
            for timestamp, event_name, conf in self.recent_events_queue:
                recent_events.append({"name": event_name, "confidence": conf})

        # 去重，取最高置信度
        dedup: Dict[str, float] = {}
        for ev in recent_events:
            n, c = ev["name"], ev["confidence"]
            if n not in dedup or c > dedup[n]:
                dedup[n] = c

        return [{"name": n, "confidence": dedup[n]} for n in dedup]

    # ----------------------- 调试辅助 -----------------------
    def simulate_event(self, panns_event_name: str, force_alert: bool = True):
        """
        人工注入一个声音事件，便于测试无需真正发声。

        Args:
            panns_event_name: 与 PANNs 标签一致的事件名，例如 "Screaming"。
            force_alert: 是否立即按普通流程发送后端告警（若该事件在 target_events_map 中）。
        """
        now = datetime.now()
        with self._lock:
            self.recent_events_queue.append((now, panns_event_name, 0.99)) # 模拟置信度

        if force_alert and panns_event_name in self.target_events_map:
            backend_event_type = self.target_events_map[panns_event_name]
            if self._should_report_event(backend_event_type):
                self._send_alert_to_backend(backend_event_type, confidence=0.99)
        logger.info(f"[SIMULATION] 已人工注入声音事件 '{panns_event_name}' (camera={self.camera_id})")

    def _simulate_loop(self):
        import time
        while True:
            time.sleep(5)
            self.simulate_event('Screaming', force_alert=True)
            # 推送props测试数据
            now_ts = time.time()
            props = {"rms": 0.12, "db": 45.0, "freq": 1200.0}
            recent = self.get_recent_events(self.event_history_seconds)
            message = {
                "type": "acoustic_events",
                "data": {
                    "timestamp": now_ts,
                    "props": props,
                    "events": recent
                },
            }
            try:
                self._broadcast_ws(message)
            except Exception as e:
                logger.debug(f"[{self.camera_id}] (simulate) 广播声学信息失败: {e}")

    async def _run_processing_loop(self):
        loop = asyncio.get_event_loop()
        logger.info(f"[{self.camera_id}] 音频处理循环已启动。")
        audio_chunk_count = 0
        while self.is_running and self.ffmpeg_process:
            audio_chunk = await loop.run_in_executor(self.executor, self.ffmpeg_process.stdout.read, self.CHUNK_BYTES)
            if not audio_chunk:
                logger.error(f"[{self.camera_id}] 音频流已结束或无音频数据，请检查推流端是否有音频轨道！")
                break
            else:
                audio_chunk_count += 1
                logger.info(f"[{self.camera_id}] 读取到音频块 #{audio_chunk_count}，长度: {len(audio_chunk)}")
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


class SimpleAudioProcessor:
    """
    简单音频处理器：拉取RTMP音频流，实时提取音频特征并推送到WebSocket。
    """
    def __init__(self, stream_url, camera_id, backend_url, api_key, sample_rate=32000, chunk_duration=1.0):
        self.stream_url = stream_url
        self.camera_id = camera_id
        self.backend_url = backend_url
        self.api_key = api_key
        self.sample_rate = sample_rate
        self.chunk_bytes = int(sample_rate * 2 * chunk_duration)  # 16bit单声道
        self.is_running = False
        self.ffmpeg_process = None
        self.thread = None
        self.last_props = {}  # <== 新增: 存储最近一次计算的声学属性

    def start(self):
        import subprocess
        import threading
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"[SimpleAudioProcessor] 启动音频处理线程，流地址: {self.stream_url}")

    def stop(self):
        self.is_running = False
        if self.ffmpeg_process:
            self.ffmpeg_process.terminate()
            self.ffmpeg_process = None
        logger.info(f"[SimpleAudioProcessor] 停止音频处理线程。")

    def _run(self):
        import numpy as np
        import scipy.fft
        import time
        ffmpeg_cmd = [
            'ffmpeg', '-i', self.stream_url,
            '-vn', '-acodec', 'pcm_s16le', '-ac', '1', '-ar', str(self.sample_rate),
            '-f', 's16le', '-loglevel', 'error', '-'
        ]
        try:
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**8
            )
            logger.info(f"[SimpleAudioProcessor] FFmpeg进程已启动。命令: {' '.join(ffmpeg_cmd)}")
        except Exception as e:
            logger.error(f"[SimpleAudioProcessor] 启动FFmpeg失败: {e}")
            return
        last_push = 0
        while self.is_running:
            try:
                audio_bytes = self.ffmpeg_process.stdout.read(self.chunk_bytes)
                if not audio_bytes or len(audio_bytes) < self.chunk_bytes:
                    logger.warning(f"[SimpleAudioProcessor] 音频流中断或数据不足。bytes={len(audio_bytes) if audio_bytes else 0}")
                    time.sleep(1)
                    continue
                waveform = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                rms = float(np.sqrt(np.mean(np.square(waveform))))
                db = 20 * np.log10(rms + 1e-12)
                N = min(2048, len(waveform))
                if N > 0:
                    window = np.hanning(N)
                    fft_vals = np.abs(scipy.fft.rfft(waveform[:N] * window))
                    freqs = scipy.fft.rfftfreq(N, 1 / self.sample_rate)
                    dom_idx = int(np.argmax(fft_vals))
                    dom_freq = float(freqs[dom_idx])
                else:
                    dom_freq = 0.0
                props = {"rms": rms, "db": db, "freq": dom_freq}
                # 新增: 保存最近一次计算结果
                self.last_props = props
                logger.info(f"[SimpleAudioProcessor] props: {props}")
                now_ts = time.time()
                if now_ts - last_push >= 1.0:
                    self._push_props(props, now_ts)
                    last_push = now_ts
            except Exception as e:
                logger.error(f"[SimpleAudioProcessor] 音频处理异常: {e}")
                time.sleep(1)
        logger.info(f"[SimpleAudioProcessor] 处理循环已退出。")

    def _push_props(self, props, now_ts):
        message = {
            "type": "acoustic_events",
            "data": {
                "timestamp": now_ts,
                "props": props,
                "events": []
            },
        }
        try:
            url = f"{self.backend_url}/api/alerts/websocket/broadcast/"
            requests.post(url, json={
                "camera_id": self.camera_id,
                "payload": message,
            }, headers={"X-Internal-API-Key": self.api_key}, timeout=2)
            logger.info(f"[SimpleAudioProcessor] 已推送props到WebSocket: {props}")
        except Exception as e:
            logger.error(f"[SimpleAudioProcessor] 推送props失败: {e}")

# 用法示例（可集成到你的流启动逻辑中）
# processor = SimpleAudioProcessor(
#     stream_url="rtmp://localhost:1935/live/test",
#     camera_id="camera_test",
#     backend_url="http://127.0.0.1:8000",
#     api_key="your_api_key"
# )
# processor.start()

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
            "Clapping": "other",
            "Shouting": "abnormal_sound_shout", # 新增用于测试的事件
            "Yell": "abnormal_sound_shout",     # 新增用于测试的事件
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
            
            # --- 新增测试代码：模拟主程序轮询音频事件 ---
            test_interval = 5
            end_time = time.time() + 30
            while time.time() < end_time:
                await asyncio.sleep(test_interval)
                recent = detector.get_recent_events(since_seconds=test_interval)
                if recent:
                    logger.info(f"[测试轮询] 在过去 {test_interval} 秒内检测到以下事件: {recent}")

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
