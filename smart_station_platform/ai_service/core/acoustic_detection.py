# 文件: ai_service/core/acoustic_detection.py
# 描述: 智能声学事件检测器，用于分析音频流中的异常声音，支持动态敏感度配置。

import numpy as np
import librosa  # 确保已安装 librosa
import soundfile as sf  # 确保已安装 soundfile
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class AcousticEventDetector:
    """
    声学事件检测器，用于分析音频文件中的异常声音事件。
    支持动态配置置信度阈值、检测间隔、事件冷却时间及整体敏感度。
    """

    def __init__(self,
                 confidence_threshold: float = 0.75,  # 默认置信度阈值
                 detection_interval: float = 5.0,  # 默认检测间隔（秒）
                 event_cooldown: float = 30.0):  # 默认同类事件冷却时间（秒）
        self.is_running = False  # 控制后台监控任务是否运行
        self.current_audio_file = None  # 当前正在监控的音频文件路径

        # 可配置参数
        self.confidence_threshold = confidence_threshold
        self.detection_interval = detection_interval
        self.event_cooldown = event_cooldown
        self.enabled = True  # 控制检测器是否启用

        # 防重复播报机制
        self.last_events: Dict[str, datetime] = {}  # 记录每种类型事件的最后发生时间

        # 敏感度调整乘数 (可被 update_settings 动态修改)
        self.volume_multiplier = 3.0  # 音量异常检测乘数
        self.frequency_multiplier = 2.0  # 高频噪声检测乘数
        self.noise_multiplier = 3.0  # 突发性噪声检测乘数

        logger.info(f"AcousticEventDetector 初始化完成。")
        self._log_current_settings()

    def _log_current_settings(self):
        """记录当前的检测设置。"""
        logger.info(f"当前声学检测设置: "
                    f"置信度阈值={self.confidence_threshold}, "
                    f"检测间隔={self.detection_interval}s, "
                    f"冷却时间={self.event_cooldown}s, "
                    f"音量乘数={self.volume_multiplier}, "
                    f"频率乘数={self.frequency_multiplier}, "
                    f"噪声乘数={self.noise_multiplier}")

    def _should_report_event(self, event_type: str, confidence: float) -> bool:
        """判断是否应该报告该事件，基于置信度和冷却时间。"""
        if not self.enabled:
            return False

        now = datetime.now()

        # 1. 置信度过滤
        if confidence < self.confidence_threshold:
            logger.debug(
                f"事件 '{event_type}' (置信度 {confidence:.2f}) 未达到置信度阈值 {self.confidence_threshold:.2f}，不报告。")
            return False

        # 2. 防重复机制 - 检查冷却时间
        if event_type in self.last_events:
            time_since_last = (now - self.last_events[event_type]).total_seconds()
            if time_since_last < self.event_cooldown:
                logger.debug(
                    f"事件 '{event_type}' 仍在冷却中 ({time_since_last:.1f}s / {self.event_cooldown:.1f}s)，不报告。")
                return False

        # 更新最后事件时间
        self.last_events[event_type] = now
        logger.info(f"事件 '{event_type}' (置信度 {confidence:.2f}) 满足报告条件。")
        return True

    async def process_audio_file(self, audio_file: str) -> List[Dict[str, Any]]:
        """
        处理单个音频文件并返回检测到的事件列表。
        Args:
            audio_file (str): 音频文件路径。
        Returns:
            List[Dict[str, Any]]: 包含检测到的事件信息的字典列表。
        """
        if not self.enabled:
            logger.debug("声学检测器已禁用，跳过音频文件处理。")
            return []

        if not os.path.exists(audio_file):
            logger.warning(f"音频文件不存在: {audio_file}。跳过处理。")
            return []

        events = []
        try:
            # 确保文件可读且不为空
            if os.path.getsize(audio_file) == 0:
                logger.warning(f"音频文件为空: {audio_file}。跳过处理。")
                return []

            # librosa.load 可能会因为文件被写入而报错，添加重试机制
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    audio_data, sr = librosa.load(audio_file, sr=None, mono=True)
                    break
                except Exception as e:
                    logger.warning(f"加载音频文件 '{audio_file}' 失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.1 * (attempt + 1))  # 短暂等待后重试
                    else:
                        raise  # 最后一次尝试失败则抛出

            if audio_data.size == 0:  # 即使加载成功，也可能没有音频数据
                logger.warning(f"加载的音频数据为空或无效: {audio_file}。")
                return []

            # 分帧处理，减少内存占用和提高实时性
            frame_length = int(sr * 0.1)  # 100毫秒一帧
            hop_length = int(sr * 0.05)  # 50毫秒跳跃

            # 计算音频特征
            rms_frames = librosa.feature.rms(y=audio_data, frame_length=frame_length, hop_length=hop_length)[0]
            spectral_centroid_frames = \
            librosa.feature.spectral_centroid(y=audio_data, sr=sr, frame_length=frame_length, hop_length=hop_length)[0]
            zero_crossing_rate_frames = \
            librosa.feature.zero_crossing_rate(y=audio_data, frame_length=frame_length, hop_length=hop_length)[0]

            if rms_frames.size == 0:
                logger.debug(f"RMS特征计算为空，音频可能过短或无声音。")
                return []

            # 计算平均值以作为基线
            mean_rms = np.mean(rms_frames) if rms_frames.size > 0 else 0
            mean_centroid = np.mean(spectral_centroid_frames) if spectral_centroid_frames.size > 0 else 0
            mean_zcr = np.mean(zero_crossing_rate_frames) if zero_crossing_rate_frames.size > 0 else 0

            # 避免除以零或无穷大
            max_rms = np.max(rms_frames) if rms_frames.size > 0 else 1e-6
            max_centroid = np.max(spectral_centroid_frames) if spectral_centroid_frames.size > 0 else 1e-6
            max_zcr = np.max(zero_crossing_rate_frames) if zero_crossing_rate_frames.size > 0 else 1e-6

            # 分析音频特征
            for i in range(len(rms_frames)):
                # 计算当前帧的时间戳
                current_timestamp_sec = librosa.frames_to_time(i, sr=sr, hop_length=hop_length)

                # 检测异常音量
                if mean_rms > 1e-6 and rms_frames[i] > mean_rms * self.volume_multiplier:
                    confidence = float(rms_frames[i] / max_rms)
                    if self._should_report_event("volume_anomaly", confidence):
                        events.append({
                            "type": "volume_anomaly",
                            "timestamp": time.time() - (len(audio_data) / sr) + current_timestamp_sec,  # 估算绝对时间
                            "confidence": confidence,
                            "description": "检测到异常音量",
                            "details": {"rms": float(rms_frames[i]), "mean_rms": float(mean_rms)}
                        })

                # 检测高频噪声 (频谱质心)
                if mean_centroid > 1e-6 and spectral_centroid_frames[i] > mean_centroid * self.frequency_multiplier:
                    confidence = float(spectral_centroid_frames[i] / max_centroid)
                    if self._should_report_event("high_frequency_noise", confidence):
                        events.append({
                            "type": "high_frequency_noise",
                            "timestamp": time.time() - (len(audio_data) / sr) + current_timestamp_sec,
                            "confidence": confidence,
                            "description": "检测到高频噪声",
                            "details": {"centroid": float(spectral_centroid_frames[i]),
                                        "mean_centroid": float(mean_centroid)}
                        })

                # 检测突发性噪声 (过零率)
                if mean_zcr > 1e-6 and zero_crossing_rate_frames[i] > mean_zcr * self.noise_multiplier:
                    confidence = float(zero_crossing_rate_frames[i] / max_zcr)
                    if self._should_report_event("sudden_noise", confidence):
                        events.append({
                            "type": "sudden_noise",
                            "timestamp": time.time() - (len(audio_data) / sr) + current_timestamp_sec,
                            "confidence": confidence,
                            "description": "检测到突发性噪声",
                            "details": {"zcr": float(zero_crossing_rate_frames[i]), "mean_zcr": float(mean_zcr)}
                        })

            return events

        except Exception as e:
            logger.error(f"处理音频文件 '{audio_file}' 时发生错误: {str(e)}", exc_info=True)
            return []

    def update_settings(self,
                        confidence_threshold: Optional[float] = None,
                        detection_interval: Optional[float] = None,
                        event_cooldown: Optional[float] = None,
                        sensitivity: Optional[str] = None):
        """
        更新声学检测的配置参数。
        Args:
            confidence_threshold (Optional[float]): 新的置信度阈值。
            detection_interval (Optional[float]): 新的检测间隔（秒）。
            event_cooldown (Optional[float]): 新的同类事件冷却时间（秒）。
            sensitivity (Optional[str]): 敏感度级别 ("low", "medium", "high")。
        """
        if confidence_threshold is not None:
            self.confidence_threshold = confidence_threshold

        if detection_interval is not None:
            self.detection_interval = detection_interval

        if event_cooldown is not None:
            self.event_cooldown = event_cooldown

        if sensitivity is not None:
            if sensitivity == "low":
                self.volume_multiplier = 4.0
                self.frequency_multiplier = 3.0
                self.noise_multiplier = 4.0
                logger.info("声学检测敏感度设置为 '低'。")
            elif sensitivity == "medium":
                self.volume_multiplier = 3.0
                self.frequency_multiplier = 2.0
                self.noise_multiplier = 3.0
                logger.info("声学检测敏感度设置为 '中'。")
            elif sensitivity == "high":
                self.volume_multiplier = 2.0
                self.frequency_multiplier = 1.5
                self.noise_multiplier = 2.0
                logger.info("声学检测敏感度设置为 '高'。")
            else:
                logger.warning(f"未知的敏感度设置: {sensitivity}。保持当前乘数不变。")

        self._log_current_settings()

    def set_enabled(self, enabled: bool):
        """启用或禁用声学事件检测器。"""
        self.enabled = enabled
        logger.info(f"声学事件检测器已{'启用' if enabled else '禁用'}。")

    def stop_monitoring(self):
        """停止音频监控。"""
        self.is_running = False
        self.current_audio_file = None
        logger.info("声学监控已停止。")

    def reset_event_history(self):
        """重置事件历史（用于测试或手动重置冷却时间）。"""
        self.last_events.clear()
        logger.info("声学事件历史已重置。")