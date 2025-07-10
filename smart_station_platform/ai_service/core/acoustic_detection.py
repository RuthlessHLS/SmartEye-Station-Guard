# 文件: ai_service/core/acoustic_detection.py
# 描述: 声学事件检测器，用于分析音频流中的异常声音。
from typing import Optional, Dict
import sounddevice as sd
import numpy as np
import queue
from typing import Callable, Optional
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
import io
import wave
import threading
import time


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
        self.video_audio_thread = None
        self.stop_video_processing = False

        # 创建一个队列来在线程间传递音频数据
        self.audio_queue = queue.Queue()

    def process_video_audio(self, video_path: str):
        """
        处理视频文件的音频。

        Args:
            video_path (str): 视频文件路径
        """
        try:
            print(f"开始处理视频音频: {video_path}")
            video = VideoFileClip(video_path)
            audio = video.audio
            
            if audio is None:
                print(f"警告: 视频 {video_path} 没有音频轨道")
                return
            
            # 获取音频数据
            audio_frames = audio.to_soundarray(fps=self.sample_rate)
            
            # 如果是立体声，转换为单声道
            if len(audio_frames.shape) > 1 and audio_frames.shape[1] > 1:
                audio_frames = np.mean(audio_frames, axis=1)
            
            # 将音频数据分块处理
            chunk_size = self.block_size
            for i in range(0, len(audio_frames), chunk_size):
                if self.stop_video_processing:
                    break
                    
                chunk = audio_frames[i:i + chunk_size]
                if len(chunk) < chunk_size:
                    # 对于最后一个不完整的块，补零
                    chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
                
                self.audio_queue.put(chunk)
                time.sleep(chunk_size / self.sample_rate)  # 模拟实时播放速度
            
            video.close()
            print(f"视频音频处理完成: {video_path}")
            
        except Exception as e:
            print(f"处理视频音频时出错: {e}")

    def start_video_audio_processing(self, video_path: str):
        """
        开始处理视频音频。

        Args:
            video_path (str): 视频文件路径
        """
        if self.video_audio_thread and self.video_audio_thread.is_alive():
            print("已有视频音频正在处理中")
            return

        self.stop_video_processing = False
        self.video_audio_thread = threading.Thread(
            target=self.process_video_audio,
            args=(video_path,)
        )
        self.video_audio_thread.start()
        self.is_running = True
        print(f"开始处理视频音频: {video_path}")

    def stop_video_audio_processing(self):
        """停止视频音频处理。"""
        self.stop_video_processing = True
        if self.video_audio_thread:
            self.video_audio_thread.join()
        self.is_running = False
        print("视频音频处理已停止")

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