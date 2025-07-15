# 文件: ai_service/core/behavior_detection.py
# 描述: 增强版行为检测器，用于分析目标的跌倒、打架等复杂行为。

import numpy as np
import time
from typing import List, Dict, Any
from collections import defaultdict
from scipy.spatial.distance import cdist


# --- SimpleTracker Class ---
# 一个简单且高效的目标追踪器，用于分配和维护检测到的目标的ID。
class SimpleTracker:
    def __init__(self, max_disappeared=50, max_distance=100):
        self.next_object_id = 0
        self.objects = {}
        self.disappeared = {}
        self.history = defaultdict(list)
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def register(self, centroid, data):
        """注册一个新的目标。"""
        timestamp = time.time()
        # 存储完整的检测数据以及追踪状态信息
        self.objects[self.next_object_id] = {
            'centroid': centroid,
            'data': data,
            'timestamp': timestamp,
            'has_fallen': False  # 用于跌倒检测的状态
        }
        self.disappeared[self.next_object_id] = 0
        self.history[self.next_object_id].append({'centroid': centroid, 'timestamp': timestamp})
        self.next_object_id += 1

    def deregister(self, object_id):
        """注销一个消失的目标。"""
        if object_id in self.objects:
            del self.objects[object_id]
        if object_id in self.disappeared:
            del self.disappeared[object_id]
        if object_id in self.history:
            del self.history[object_id]

    def update(self, detections: List[Dict]) -> Dict[int, Any]:
        """
        用新一帧的检测结果更新追踪器。
        detections: 来自目标检测器的字典列表。
        """
        if len(detections) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self.objects

        # 从输入检测中准备质心数据
        input_centroids = np.zeros((len(detections), 2), dtype="int")
        for i, det in enumerate(detections):
            box = det.get('box') or det.get('bbox')
            if box:
                x1, y1, x2, y2 = box
                cX = int((x1 + x2) / 2.0)
                cY = int((y1 + y2) / 2.0)
                input_centroids[i] = (cX, cY)

        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i], detections[i])
        else:
            object_ids = list(self.objects.keys())
            object_centroids = np.array([d['centroid'] for d in self.objects.values()])

            # 计算距离并匹配
            D = cdist(object_centroids, input_centroids)
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows = set()
            used_cols = set()

            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue
                if D[row, col] > self.max_distance:
                    continue

                object_id = object_ids[row]
                new_centroid = input_centroids[col]
                timestamp = time.time()
                
                # 更新目标信息，同时保留 'has_fallen' 状态
                has_fallen_state = self.objects[object_id].get('has_fallen', False)
                
                self.objects[object_id]['centroid'] = new_centroid
                self.objects[object_id]['data'] = detections[col]
                self.objects[object_id]['timestamp'] = timestamp
                self.objects[object_id]['has_fallen'] = has_fallen_state
                self.disappeared[object_id] = 0
                
                self.history[object_id].append({'centroid': new_centroid, 'timestamp': timestamp})
                # 保持历史记录的长度可控
                if len(self.history[object_id]) > 15:
                    self.history[object_id].pop(0)

                used_rows.add(row)
                used_cols.add(col)

            unused_rows = set(range(len(self.objects))).difference(used_rows)
            unused_cols = set(range(len(input_centroids))).difference(used_cols)

            for row_idx in unused_rows:
                object_id = object_ids[row_idx]
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)

            for col_idx in unused_cols:
                self.register(input_centroids[col_idx], detections[col_idx])
        return self.objects


# --- BehaviorDetector Class ---
# 集成追踪器与跌倒、打架检测逻辑。
class BehaviorDetector:
    def __init__(self):
        """初始化行为检测器（增强版），包含跌倒和打架检测逻辑。"""
        print("行为检测器初始化中 (增强版)...")
        self.tracker = SimpleTracker(max_disappeared=50, max_distance=100)
        
        # 跌倒检测参数
        self.fall_counters = defaultdict(int)
        self.fall_aspect_ratio_threshold = 1.4
        self.fall_confidence_threshold = 3  # 连续3帧满足条件才确认跌倒
        self.vertical_velocity_threshold = 150 # 垂直速度阈值（像素/秒）

        # 打架检测参数
        self.fight_event = None
        self.fight_confirmation_frames = 5 # 连续5帧满足条件才确认打架
        self.fight_proximity_threshold = 100 # 打架人员之间的最大距离
        self.fight_motion_threshold = 120 # 打架人员的最低移动速度

    def detect_behavior(self, frame: np.ndarray, detections: List[Dict]) -> List[Dict]:
        """
        分析检测列表，判断跌倒和打架行为。
        """
        # 1. 筛选出所有 'person' 类型的检测结果
        person_detections = [d for d in detections if d.get('class_name') == 'person']

        # 2. 使用追踪器更新人员状态
        tracked_objects = self.tracker.update(person_detections)
        
        # 3. 初始化行为结果列表
        detected_behaviors = []

        # 4. 检测单人行为（跌倒）
        fall_results = self._detect_falls(tracked_objects)
        detected_behaviors.extend(fall_results)

        # 5. 检测多人行为（打架）
        fight_result = self._detect_fights(tracked_objects)
        if fight_result:
            detected_behaviors.append(fight_result)

        # 6. 为未参与特殊事件的人员添加默认的 'active' 状态
        active_ids_in_events = set()
        for beh in detected_behaviors:
            if beh['behavior'] == 'fall_down':
                active_ids_in_events.add(beh['person_id'])
            elif beh['behavior'] == 'fighting':
                active_ids_in_events.update(beh['person_ids'])
        
        for obj_id, obj_data in tracked_objects.items():
            if obj_id not in active_ids_in_events:
                detected_behaviors.append({
                    "person_id": obj_id,
                    "box": obj_data['data'].get('box') or obj_data['data'].get('bbox'),
                    "behavior": "active",
                    "is_abnormal": False,
                    "need_alert": False,
                    "confidence": 0.7
                })

        return detected_behaviors

    def _detect_falls(self, tracked_objects: Dict) -> List[Dict]:
        """分析被追踪目标，判断是否跌倒。"""
        fall_behaviors = []
        active_ids = set(tracked_objects.keys())
        
        for obj_id, obj_data in tracked_objects.items():
            box = obj_data['data'].get('box') or obj_data['data'].get('bbox')
            x1, y1, x2, y2 = box

            # 如果一个目标已被确认为跌倒，则保持该状态
            if obj_data.get('has_fallen', False):
                fall_behaviors.append({
                    "person_id": obj_id, "box": box, "behavior": "fall_down",
                    "is_abnormal": True, "need_alert": True, "confidence": 0.95
                })
                continue

            # 计算跌倒指标：高宽比和垂直速度
            box_width = x2 - x1
            box_height = y2 - y1
            aspect_ratio = box_width / max(box_height, 1)

            vertical_velocity = 0
            history = self.tracker.history.get(obj_id, [])
            if len(history) > 1:
                last_point = history[-1]
                prev_point = history[-2]
                delta_y = last_point['centroid'][1] - prev_point['centroid'][1]
                delta_t = last_point['timestamp'] - prev_point['timestamp']
                if delta_t > 1e-6:
                    vertical_velocity = delta_y / delta_t

            # 判断是否为“疑似跌倒”
            is_fall_candidate = False
            if vertical_velocity > self.vertical_velocity_threshold:
                is_fall_candidate = True
            elif aspect_ratio > self.fall_aspect_ratio_threshold:
                is_fall_candidate = True
            
            # 使用计数器确认跌倒，防止误判
            if is_fall_candidate:
                self.fall_counters[obj_id] += 1
            else:
                self.fall_counters[obj_id] = 0
            
            if self.fall_counters[obj_id] >= self.fall_confidence_threshold:
                self.tracker.objects[obj_id]['has_fallen'] = True
                fall_behaviors.append({
                    "person_id": obj_id, "box": box, "behavior": "fall_down",
                    "is_abnormal": True, "need_alert": True, "confidence": 0.85
                })
                self.fall_counters[obj_id] = 0 # 确认后重置计数器

        # 清理已消失目标的计数器
        stale_ids = set(self.fall_counters.keys()) - active_ids
        for stale_id in stale_ids:
            del self.fall_counters[stale_id]
            
        return fall_behaviors
        
    def _detect_fights(self, tracked_objects: Dict) -> Dict:
        """
        分析追踪目标，判断是否发生打架。
        这是一个基础实现，检测多个高速运动且彼此靠近的目标。
        """
        # 筛选出未跌倒的活跃人员进行分析
        active_persons = {oid: data for oid, data in tracked_objects.items() if not data.get('has_fallen')}

        if len(active_persons) < 2:
            self.fight_event = None # 人数不足，重置打架事件
            return None

        # 计算每个人的当前速度
        velocities = {}
        for obj_id in active_persons.keys():
            speed = 0
            history = self.tracker.history.get(obj_id, [])
            if len(history) > 1:
                p1 = history[-1]['centroid']
                t1 = history[-1]['timestamp']
                p0 = history[-2]['centroid']
                t0 = history[-2]['timestamp']
                if t1 - t0 > 1e-6:
                    speed = np.linalg.norm(np.array(p1) - np.array(p0)) / (t1 - t0)
            velocities[obj_id] = speed
        
        # 寻找满足条件的打架候选组
        candidate_pairs = []
        person_ids = list(active_persons.keys())
        for i in range(len(person_ids)):
            for j in range(i + 1, len(person_ids)):
                id1, id2 = person_ids[i], person_ids[j]
                p1 = active_persons[id1]['centroid']
                p2 = active_persons[id2]['centroid']
                
                distance = np.linalg.norm(np.array(p1) - np.array(p2))

                # 条件：距离近 且 双方速度快
                if distance < self.fight_proximity_threshold:
                    if velocities[id1] > self.fight_motion_threshold and velocities[id2] > self.fight_motion_threshold:
                        candidate_pairs.append(tuple(sorted((id1, id2))))
        
        # 如果没有候选组，重置事件
        if not candidate_pairs:
            self.fight_event = None
            return None
        
        # 使用连续帧确认逻辑更新打架事件
        current_candidate_group = set()
        for p1, p2 in candidate_pairs:
            current_candidate_group.add(p1)
            current_candidate_group.add(p2)

        if self.fight_event and self.fight_event['person_ids'] == current_candidate_group:
            self.fight_event['counter'] += 1
        else:
            # 发现新的候选组，重置计数器
            self.fight_event = {
                'person_ids': current_candidate_group,
                'counter': 1
            }
        
        # 如果事件持续时间达到阈值，则确认并返回打架事件
        if self.fight_event['counter'] >= self.fight_confirmation_frames:
            involved_boxes = [active_persons[pid]['data']['box'] for pid in self.fight_event['person_ids']]
            return {
                "person_ids": list(self.fight_event['person_ids']),
                "boxes": involved_boxes,
                "behavior": "fighting",
                "is_abnormal": True,
                "need_alert": True,
                "confidence": 0.80,
                "details": "检测到多个目标在近距离内高速移动。"
            }
            
        return None