# 文件: ai_service/core/acoustic_detection.py
# 描述: 声学事件检测器，用于分析音频流中的异常声音。
import numpy as np
import librosa
import soundfile as sf
import logging
from datetime import datetime, timedelta
import asyncio
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class AcousticEventDetector:
    def __init__(self, 
                 confidence_threshold: float = 0.75,  # 置信度阈值
                 detection_interval: float = 5.0,     # 检测间隔（秒）
                 event_cooldown: float = 30.0):       # 同类事件冷却时间（秒）
        self.is_running = False
        self.current_audio_file = None
        self.processing_task = None
        
        # 配置参数
        self.confidence_threshold = confidence_threshold
        self.detection_interval = detection_interval
        self.event_cooldown = event_cooldown
        
        # 防重复播报机制
        self.last_events = {}  # 记录每种类型事件的最后发生时间
        
        # 调整检测敏感度 - 降低误报率
        self.volume_multiplier = 3.0      # 从2.0提高到3.0，降低敏感度
        self.frequency_multiplier = 2.0   # 从1.5提高到2.0，降低敏感度  
        self.noise_multiplier = 3.0       # 从2.0提高到3.0，降低敏感度
        
    def _should_report_event(self, event_type: str, confidence: float) -> bool:
        """判断是否应该报告该事件"""
        now = datetime.now()
        
        # 1. 置信度过滤
        if confidence < self.confidence_threshold:
            return False
            
        # 2. 防重复机制 - 检查冷却时间
        if event_type in self.last_events:
            time_since_last = (now - self.last_events[event_type]).total_seconds()
            if time_since_last < self.event_cooldown:
                return False
                
        # 更新最后事件时间
        self.last_events[event_type] = now
        return True
        
    async def process_audio_file(self, audio_file: str) -> List[Dict]:
        """处理音频文件并返回检测结果"""
        try:
            # 加载音频文件
            audio_data, sr = librosa.load(audio_file, sr=None)
            
            # 计算音频特征
            # 1. 音量检测
            rms = librosa.feature.rms(y=audio_data)[0]
            # 2. 频谱质心 - 用于识别声音的"明亮度"
            spectral_centroid = librosa.feature.spectral_centroid(y=audio_data, sr=sr)[0]
            # 3. 过零率 - 用于识别噪声类型
            zero_crossing_rate = librosa.feature.zero_crossing_rate(audio_data)[0]
            
            events = []
            # 分析音频特征
            for i in range(len(rms)):
                timestamp = librosa.samples_to_time(i * len(audio_data) // len(rms), sr=sr)
                
                # 检测异常声音 - 提高阈值，降低敏感度
                if rms[i] > np.mean(rms) * self.volume_multiplier:  # 从2倍提高到3倍
                    confidence = float(rms[i] / np.max(rms))
                    if self._should_report_event("volume_anomaly", confidence):
                        events.append({
                            "type": "volume_anomaly",
                            "timestamp": timestamp,
                            "confidence": confidence,
                            "description": "检测到异常音量"
                        })
                
                # 检测高频噪声 - 提高阈值
                if spectral_centroid[i] > np.mean(spectral_centroid) * self.frequency_multiplier:  # 从1.5倍提高到2倍
                    confidence = float(spectral_centroid[i] / np.max(spectral_centroid))
                    if self._should_report_event("high_frequency_noise", confidence):
                        events.append({
                            "type": "high_frequency_noise",
                            "timestamp": timestamp,
                            "confidence": confidence,
                            "description": "检测到高频噪声"
                        })
                
                # 检测突发性噪声 - 提高阈值
                if zero_crossing_rate[i] > np.mean(zero_crossing_rate) * self.noise_multiplier:  # 从2倍提高到3倍
                    confidence = float(zero_crossing_rate[i] / np.max(zero_crossing_rate))
                    if self._should_report_event("sudden_noise", confidence):
                        events.append({
                            "type": "sudden_noise",
                            "timestamp": timestamp,
                            "confidence": confidence,
                            "description": "检测到突发性噪声"
                        })
            
            return events
            
        except Exception as e:
            logger.error(f"处理音频文件时发生错误: {str(e)}")
            return []
    
    def update_settings(self, 
                       confidence_threshold: Optional[float] = None,
                       detection_interval: Optional[float] = None,
                       event_cooldown: Optional[float] = None,
                       sensitivity: Optional[str] = None):
        """更新检测设置"""
        if confidence_threshold is not None:
            self.confidence_threshold = confidence_threshold
            
        if detection_interval is not None:
            self.detection_interval = detection_interval
            
        if event_cooldown is not None:
            self.event_cooldown = event_cooldown
            
        if sensitivity is not None:
            # 根据敏感度级别调整检测阈值
            if sensitivity == "low":
                self.volume_multiplier = 4.0
                self.frequency_multiplier = 3.0
                self.noise_multiplier = 4.0
            elif sensitivity == "medium":
                self.volume_multiplier = 3.0
                self.frequency_multiplier = 2.0
                self.noise_multiplier = 3.0
            elif sensitivity == "high":
                self.volume_multiplier = 2.0
                self.frequency_multiplier = 1.5
                self.noise_multiplier = 2.0
                
        logger.info(f"音频检测设置已更新: 置信度阈值={self.confidence_threshold}, "
                   f"检测间隔={self.detection_interval}s, 冷却时间={self.event_cooldown}s")
            
    async def start_monitoring(self, audio_file: str):
        """开始监控音频文件"""
        self.is_running = True
        self.current_audio_file = audio_file
        
        while self.is_running:
            try:
                events = await self.process_audio_file(self.current_audio_file)
                if events:
                    logger.info(f"检测到 {len(events)} 个声音事件")
                    for event in events:
                        logger.info(f"声音事件: {event}")
                
                # 使用可配置的检测间隔
                await asyncio.sleep(self.detection_interval)
                
            except Exception as e:
                logger.error(f"音频监控过程中发生错误: {str(e)}")
                await asyncio.sleep(10)  # 发生错误时等待较长时间
                
    def stop_monitoring(self):
        """停止音频监控"""
        self.is_running = False
        self.current_audio_file = None
        logger.info("音频监控已停止")
        
    def reset_event_history(self):
        """重置事件历史（用于测试或手动重置）"""
        self.last_events.clear()
        logger.info("音频事件历史已重置")