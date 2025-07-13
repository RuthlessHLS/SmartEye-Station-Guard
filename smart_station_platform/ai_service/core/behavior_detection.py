# 文件: ai_service/core/behavior_detection.py
# 描述: 行为检测器，用于分析目标的姿态和动作。
#       当前实现基于启发式规则和目标追踪信息。

import numpy as np
from typing import List, Dict, Tuple, Any, Optional
import time
import logging

logger = logging.getLogger(__name__)


class BehaviorDetector:
    """
    行为检测器，对检测到的人员进行行为分析。
    目前基于边界框特征和目标追踪信息进行启发式判断。
    """

    def __init__(self):
        logger.info("行为检测器已初始化 (当前使用启发式判断模式)。")
        # previous_states 字典将存储每个追踪ID的历史信息
        # 结构: {tracking_id: {
        #   'last_bbox': [x1, y1, x2, y2],
        #   'last_center': [cx, cy],
        #   'last_timestamp': float,
        #   'fall_start_time': Optional[float], # 记录跌倒开始时间
        #   'is_fallen': bool,                  # 当前帧是否被判定为跌倒
        #   'fall_duration': float,             # 跌倒持续时间
        #   'moving_avg_speed': float,          # 移动平均速度
        #   'active_start_time': Optional[float], # 记录活跃行为开始时间
        #   'is_active': bool,                  # 当前帧是否被判定为活跃
        # }}
        self.previous_states: Dict[str, Dict[str, Any]] = {}
        self.enabled = True  # 添加启用/禁用标志

        # 可配置的行为判断阈值
        self._default_config = {
            'fall_aspect_ratio_threshold': 1.2,  # 跌倒判断的宽高比阈值 (宽/高)
            'min_fall_duration': 0.5,  # 判定为跌倒行为所需的最小持续时间 (秒)
            'movement_speed_threshold_active': 15.0,  # 判定为活跃行为的最小移动速度 (像素/帧)
            'movement_speed_threshold_running': 50.0,  # 判定为奔跑行为的最小移动速度 (像素/帧)
            'max_idle_duration': 2.0,  # 判定为静止或不活跃的最大持续时间 (秒)
            'detection_interval': 0.1  # 行为分析的最小时间间隔（秒），避免过度频繁更新状态
        }
        self.current_config = self._default_config.copy()

    def update_config(self, new_config: Dict[str, Any]):
        """
        更新行为检测器的配置参数。
        Args:
            new_config (Dict[str, Any]): 包含要更新的配置项的字典。
        """
        for key, value in new_config.items():
            if key in self.current_config:
                self.current_config[key] = value
                logger.info(f"更新行为检测配置: {key} = {value}")
            else:
                logger.warning(f"尝试更新不存在的配置项: {key}")
        logger.info(f"行为检测器当前配置: {self.current_config}")

    def set_enabled(self, enabled: bool):
        """启用或禁用行为检测器。"""
        self.enabled = enabled
        logger.info(f"行为检测器已{'启用' if enabled else '禁用'}。")

    def detect_behavior(self,
                        frame: np.ndarray,
                        tracked_persons: List[Dict],
                        current_timestamp: float) -> List[Dict]:
        """
        对检测到并追踪到的人员进行行为分析。
        Args:
            frame (np.ndarray): 当前的视频帧。
            tracked_persons (List[Dict]): 一个包含多个人员追踪信息的列表，
                                         每个元素应包含 'tracking_id' 和 'bbox'。
            current_timestamp (float): 当前帧的时间戳 (秒)。
        Returns:
            List[Dict]: 一个包含每个被分析人员行为结果的字典列表。
        """
        if not self.enabled:
            return []

        detected_behaviors = []

        # 清理过期的追踪状态
        self._cleanup_old_states(current_timestamp)

        for person_data in tracked_persons:
            tracking_id = person_data.get('tracking_id')
            bbox = person_data.get('bbox')

            if not tracking_id or not bbox or len(bbox) != 4:
                logger.warning(f"跳过无效的人员追踪数据: {person_data}")
                continue

            x1, y1, x2, y2 = map(int, bbox)

            # 初始化或更新当前人员的状态
            if tracking_id not in self.previous_states:
                self.previous_states[tracking_id] = {
                    'last_bbox': bbox,
                    'last_center': [(x1 + x2) / 2, (y1 + y2) / 2],
                    'last_timestamp': current_timestamp,
                    'fall_start_time': None,
                    'is_fallen': False,
                    'fall_duration': 0.0,
                    'moving_avg_speed': 0.0,  # 像素/秒
                    'active_start_time': None,
                    'is_active': False,
                    'idle_start_time': None  # 用于判断长时间静止
                }

            person_state = self.previous_states[tracking_id]

            # 计算时间差
            time_diff = current_timestamp - person_state['last_timestamp']

            # 避免过快更新，基于detection_interval
            if time_diff < self.current_config['detection_interval']:
                continue  # 跳过，等待足够的时间间隔

            # --- 1. 跌倒检测 (Heuristic: 基于边界框的高宽比及持续时间) ---
            box_w = x2 - x1
            box_h = y2 - y1

            is_fallen_current_frame = False
            if box_h > 0 and box_w / box_h > self.current_config['fall_aspect_ratio_threshold']:
                is_fallen_current_frame = True

            if is_fallen_current_frame:
                if not person_state['is_fallen']:  # 刚开始跌倒
                    person_state['fall_start_time'] = current_timestamp
                person_state['fall_duration'] = current_timestamp - person_state['fall_start_time'] if person_state[
                    'fall_start_time'] else 0.0
                person_state['is_fallen'] = True

                if person_state['fall_duration'] >= self.current_config['min_fall_duration']:
                    detected_behaviors.append({
                        "tracking_id": tracking_id,
                        "bbox": bbox,
                        "behavior": "fall_down",
                        "is_abnormal": True,
                        "need_alert": True,  # 跌倒需要立即告警
                        "confidence": min(1.0, 0.7 + person_state['fall_duration'] * 0.1),  # 置信度随持续时间增加
                        "duration_s": round(person_state['fall_duration'], 2),
                        "aspect_ratio": round(box_w / box_h, 2)
                    })
                    logger.info(
                        f"🚨 [行为告警] 人员 {tracking_id} 检测到跌倒行为 (持续: {person_state['fall_duration']:.2f}s, 置信度: {detected_behaviors[-1]['confidence']:.2f})")
            else:
                person_state['is_fallen'] = False
                person_state['fall_start_time'] = None
                person_state['fall_duration'] = 0.0

            # --- 2. 移动速度检测 (奔跑/静止/活跃) ---
            current_center = [(x1 + x2) / 2, (y1 + y2) / 2]

            # 计算瞬时移动距离
            instant_distance = np.sqrt(
                (current_center[0] - person_state['last_center'][0]) ** 2 +
                (current_center[1] - person_state['last_center'][1]) ** 2
            )

            # 计算瞬时速度 (像素/秒)
            instant_speed = instant_distance / time_diff if time_diff > 0 else 0.0

            # 更新移动平均速度 (平滑处理，避免抖动)
            alpha = 0.2  # 平滑因子，越小越平滑
            person_state['moving_avg_speed'] = (1 - alpha) * person_state['moving_avg_speed'] + alpha * instant_speed

            # 判断活跃状态
            if person_state['moving_avg_speed'] > self.current_config['movement_speed_threshold_active']:
                if not person_state['is_active']:
                    person_state['active_start_time'] = current_timestamp
                person_state['is_active'] = True
                person_state['idle_start_time'] = None  # 不再静止
            else:
                person_state['is_active'] = False
                if person_state['idle_start_time'] is None:
                    person_state['idle_start_time'] = current_timestamp  # 开始静止计时

            # 行为报告
            if not is_fallen_current_frame:  # 如果没有跌倒，才判断其他行为
                if person_state['moving_avg_speed'] >= self.current_config['movement_speed_threshold_running']:
                    detected_behaviors.append({
                        "tracking_id": tracking_id,
                        "bbox": bbox,
                        "behavior": "running",
                        "is_abnormal": False,  # 奔跑本身不异常，但可根据场景定义
                        "need_alert": False,
                        "confidence": min(1.0, person_state['moving_avg_speed'] / self.current_config[
                            'movement_speed_threshold_running']),
                        "speed_px_per_s": round(person_state['moving_avg_speed'], 2)
                    })
                    logger.debug(
                        f"🏃 人员 {tracking_id} 检测到奔跑行为 (速度: {person_state['moving_avg_speed']:.2f} px/s)")
                elif person_state['is_active']:
                    detected_behaviors.append({
                        "tracking_id": tracking_id,
                        "bbox": bbox,
                        "behavior": "walking/active",
                        "is_abnormal": False,
                        "need_alert": False,
                        "confidence": min(1.0, person_state['moving_avg_speed'] / self.current_config[
                            'movement_speed_threshold_active']),
                        "speed_px_per_s": round(person_state['moving_avg_speed'], 2)
                    })
                    logger.debug(
                        f"🚶 人员 {tracking_id} 检测到活跃行为 (速度: {person_state['moving_avg_speed']:.2f} px/s)")
                else:  # 不活跃/静止
                    idle_duration = (current_timestamp - person_state['idle_start_time']) if person_state[
                        'idle_start_time'] else 0.0
                    if idle_duration >= self.current_config['max_idle_duration']:
                        # 只报告一次长时间静止，直到重新移动
                        if not person_state.get('reported_idle_alert', False):
                            detected_behaviors.append({
                                "tracking_id": tracking_id,
                                "bbox": bbox,
                                "behavior": "long_idle",
                                "is_abnormal": True,  # 长时间静止在某些场景可能是异常
                                "need_alert": True,
                                "confidence": min(1.0, idle_duration / 5.0),  # 停留越久置信度越高
                                "idle_duration_s": round(idle_duration, 2)
                            })
                            logger.info(f"⏳ [行为告警] 人员 {tracking_id} 长时间静止 (持续: {idle_duration:.2f}s)")
                            person_state['reported_idle_alert'] = True
                    else:
                        person_state['reported_idle_alert'] = False

            # 更新状态信息以用于下一帧
            person_state['last_bbox'] = bbox
            person_state['last_center'] = current_center
            person_state['last_timestamp'] = current_timestamp

        return detected_behaviors

    def _cleanup_old_states(self, current_timestamp: float, timeout_s: float = 10.0):
        """
        清理长时间未见的人员追踪状态，防止内存泄漏。
        Args:
            current_timestamp (float): 当前时间戳。
            timeout_s (float): 对象从缓存中移除前的最大不活跃时间（秒）。
        """
        to_remove = []
        for tracking_id, state in self.previous_states.items():
            if current_timestamp - state['last_timestamp'] > timeout_s:
                to_remove.append(tracking_id)

        for tracking_id in to_remove:
            del self.previous_states[tracking_id]
            logger.debug(f"清理过期行为状态: {tracking_id}")

    def reset(self):
        """重置所有人员的行为状态历史。"""
        self.previous_states.clear()
        logger.info("行为检测器状态已重置。")