# 文件: ai_service/core/behavior_detection.py
# 描述: 行为检测器，用于分析目标的姿态和动作。

import numpy as np
from typing import List, Dict, Tuple


class BehaviorDetector:
    def __init__(self):
        """
        初始化行为检测器。
        在真实项目中，这里会加载行为识别模型（例如基于姿态估计的模型）。
        目前，我们使用一个字典来跟踪每个目标的状态，以进行基于逻辑的判断。
        """
        print("行为检测器已初始化 (当前使用逻辑判断模式)。")
        self.previous_states = {}  # 用于存储每个追踪目标上一帧的状态

    def detect_behavior(self, frame: np.ndarray, person_boxes: List[List[float]]) -> List[Dict]:
        """
        对检测到的人员进行行为分析。

        Args:
            frame (np.ndarray): 当前的视频帧。
            person_boxes (List[List[float]]): 一个包含多个人边界框的列表，
                                              每个边界框格式为 [x1, y1, x2, y2]。

        Returns:
            List[Dict]: 一个包含每个被分析人员行为结果的字典列表。
        """
        detected_behaviors = []

        for i, box in enumerate(person_boxes):
            x1, y1, x2, y2 = map(int, box)

            # --- 1. 跌倒检测 (Heuristic: 基于边界框的高宽比) ---
            # 计算边界框的宽度和高度
            box_w = x2 - x1
            box_h = y2 - y1

            # 避免除以零的错误
            if box_h == 0: continue

            # 计算高宽比
            aspect_ratio = box_w / box_h

            is_fallen = False
            # 通常站立的人高宽比小于1 (例如 0.4-0.8)
            # 如果高宽比大于某个阈值 (例如 1.2)，我们认为他可能摔倒了
            if aspect_ratio > 1.2:
                is_fallen = True
                detected_behaviors.append({
                    "person_id": i,  # 临时ID
                    "box": [x1, y1, x2, y2],
                    "behavior": "fall_down",
                    "is_abnormal": True,
                    "need_alert": True,  # 跌倒需要立即告警
                    "confidence": 0.85  # 这是一个模拟的置信度
                })

            # --- 2. 奔跑检测 (Heuristic: 基于位置的快速变化) ---
            # (这是一个简化的示例，完整的实现需要目标追踪)
            # 在没有目标追踪的情况下，我们可以简化为：如果画面中有人，就认为他在活动
            # 在这里，我们只添加一个占位的 "active" 行为
            if not is_fallen:  # 如果没摔倒，就认为在活动
                detected_behaviors.append({
                    "person_id": i,
                    "box": [x1, y1, x2, y2],
                    "behavior": "active",  # 正常活动
                    "is_abnormal": False,
                    "need_alert": False,
                    "confidence": 0.7
                })

        return detected_behaviors