# 文件: ai_service/core/acoustic_detection.py
# 描述: 声学事件检测器，用于分析音频流中的异常声音。

import sounddevice as sd
import numpy as np
import queue
from typing import Callable, Optional


class AcousticDetector:
    def __init__(self, device_index: Optional[int] = None, sample_rate: int = 44100, block_size: int = 1024):
        """
        初始化声学事件检测器。

        Args:
            device_index (Optional[int]): 要使用的麦克风设备索引。如果为None，则使用默认输入设备。
            sample_rate (int): 采样率 (Hz)。
            block_size (int): 每次读取的音频帧大小。
        """
        print("正在初始化声学事件检测器...")
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.stream = None
        self.is_running = False

        # 创建一个队列来在线程间传递音频数据
        self.audio_queue = queue.Queue()

        # 检查是否有可用的麦克风设备
        try:
            sd.query_devices(kind='input')
        except Exception as e:
            print(f"错误: 无法找到音频输入设备: {e}")
            raise

    def _audio_callback(self, indata, frames, time, status):
        """这是音频流的回调函数，当有新的音频数据时，sounddevice会自动调用它。"""
        if status:
            print(f"音频流状态警告: {status}")
        # 将获取到的音频数据放入队列
        self.audio_queue.put(indata.copy())

    def start_listening(self):
        """启动音频监听流。"""
        if self.is_running:
            print("音频监听已在运行中。")
            return

        try:
            # 创建并启动一个非阻塞的音频输入流
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                device=self.device_index,
                channels=1,  # 单声道
                callback=self._audio_callback
            )
            self.stream.start()
            self.is_running = True
            print("音频监听已启动。")
        except Exception as e:
            print(f"启动音频监听失败: {e}")
            self.is_running = False

    def stop_listening(self):
        """停止音频监听流。"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.is_running = False
            print("音频监听已停止。")

    def analyze_audio_chunk(self, volume_threshold: float = 0.1) -> Optional[Dict]:
        """
        从队列中取出一块音频数据进行分析。

        Args:
            volume_threshold (float): 音量阈值，超过此值则判定为异常。范围 0.0 - 1.0。

        Returns:
            Optional[Dict]: 如果检测到异常，返回一个包含事件信息的字典，否则返回None。
        """
        try:
            # 从队列中获取音频数据，非阻塞
            audio_chunk = self.audio_queue.get_nowait()

            # 计算音量 (均方根 RMS)
            volume = np.sqrt(np.mean(audio_chunk ** 2))

            if volume > volume_threshold:
                return {
                    "event_type": "abnormal_sound_detected",
                    "is_abnormal": True,
                    "need_alert": True,
                    "details": {
                        "volume": round(volume, 3)
                    },
                    "confidence": min(1.0, volume / volume_threshold * 0.5)  # 模拟置信度
                }
        except queue.Empty:
            # 队列为空是正常情况，表示没有新的音频数据
            return None
        return None