# 文件: ai_service/core/behavior_detection.py
# 描述: 增强版行为检测器，用于分析目标的跌倒、打架等复杂行为。

import numpy as np
import time
from typing import List, Dict, Any
from collections import defaultdict, deque
from scipy.spatial.distance import cdist


# --- SimpleTracker Class ---
# 一个简单且高效的目标追踪器，用于分配和维护检测到的目标的ID。
class SimpleTracker:
    def __init__(self, max_disappeared=50, max_distance=100, history_length=30):
        self.next_object_id = 0
        self.objects = {}
        self.disappeared = {}
        self.history = defaultdict(lambda: deque(maxlen=history_length))
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def register(self, centroid, data):
        """注册一个新的目标。"""
        timestamp = time.time()
        box = data.get('box') or data.get('bbox') or data.get('coordinates')
        # 存储完整的检测数据以及追踪状态信息
        self.objects[self.next_object_id] = {
            'centroid': centroid,
            'data': data,
            'timestamp': timestamp,
            'has_fallen': False,  # 用于跌倒检测的状态
            'is_waving': False,   # 用于挥手检测的状态
        }
        self.disappeared[self.next_object_id] = 0
        self.history[self.next_object_id].append({'centroid': centroid, 'timestamp': timestamp, 'box': box})
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
            box = det.get('box') or det.get('bbox') or det.get('coordinates')
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
                box = detections[col].get('box') or detections[col].get('bbox') or detections[col].get('coordinates')
                
                # 更新目标信息，同时保留状态
                self.objects[object_id]['centroid'] = new_centroid
                self.objects[object_id]['data'] = detections[col]
                self.objects[object_id]['timestamp'] = timestamp
                self.disappeared[object_id] = 0
                
                self.history[object_id].append({'centroid': new_centroid, 'timestamp': timestamp, 'box': box})

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
        """初始化行为检测器（增强版），包含跌倒、打架、挥手检测逻辑。"""
        print("行为检测器初始化中 (增强版)...")
        self.tracker = SimpleTracker(max_disappeared=50, max_distance=100, history_length=30)
        
        # 跌倒检测参数 (进一步放宽以提升灵敏度)
        self.fall_counters = defaultdict(int)
        # 当 bbox 宽高比超过该阈值认为可能躺倒；数值越小越敏感
        self.fall_aspect_ratio_threshold = 1.0  # 宽高比≥1 即视为可能躺倒
        # 连续满足条件的帧数
        self.fall_confidence_threshold = 1      # 由 2 调低
        # 竖直速度阈值 (像素/秒)
        self.vertical_velocity_threshold = 30   # 进一步降低垂直速度阈值

        # 挥手检测参数（放宽条件，提升灵敏度）
        # 连续1帧满足即可确认，极大提高触发概率
        self.waving_confidence_threshold = 1   
        # 水平移动阈值降低
        self.waving_min_motion = 3            # 降低水平移动阈值
        # 垂直速度阈值放宽
        self.waving_max_vertical_motion = 80  # 放宽垂直运动限制
        # bbox宽度变化阈值降低
        self.waving_min_box_width_change = 10 

        # 统计每个追踪目标的连续“挥手候选”帧数
        self.waving_counters = defaultdict(int)

        # 打架检测参数 (阈值已调低便于测试，且允许纯视觉触发告警)
        self.fight_event = None
        # 连续多少帧都满足条件才认为确认打架
        # 打架检测：放宽阈值
        self.fight_confirmation_frames = 1      # 连续1帧即可确认
        self.fight_proximity_threshold = 200    # 允许更远距离
        self.fight_motion_threshold = 40        # 更低运动速度阈值
        # 用于音视频联动的音频事件关键字
        self.fight_audio_events = {"Screaming", "Shouting", "Yell"}

        # 默认仅视觉即可触发打架告警，可按需在配置中开启音视频联动
        self.require_audio_for_fight = False

    def detect_behavior(self, frame: np.ndarray, detections: List[Dict], 
                        audio_events: List[str] = None,
                        enable_fall: bool = True, 
                        enable_fight: bool = True,
                        enable_waving: bool = True) -> List[Dict]:
        """
        分析检测列表，判断跌倒、打架和挥手行为。
        """
        # 1. 筛选出所有 'person' 类型的检测结果
        person_detections = [d for d in detections if d.get('class_name') == 'person']

        # 2. 使用追踪器更新人员状态
        tracked_objects = self.tracker.update(person_detections)
        
        # 3. 初始化行为结果列表
        detected_behaviors = []

        # 4. 检测单人行为（跌倒、挥手）
        if enable_fall:
            fall_results = self._detect_falls(tracked_objects)
            detected_behaviors.extend(fall_results)

        if enable_waving:
            waving_results = self._detect_waving(tracked_objects)
            detected_behaviors.extend(waving_results)

        # 5. 检测多人行为（打架）
        if enable_fight:
            fight_result = self._detect_fights(tracked_objects, audio_events or [])
            if fight_result:
                detected_behaviors.append(fight_result)

        # 6. 为未参与特殊事件的人员添加默认的 'active' 状态
        active_ids_in_events = set()
        for beh in detected_behaviors:
            if beh['behavior'] in ('fall_down', 'waving_hand'):
                active_ids_in_events.add(beh['person_id'])
            elif beh['behavior'] in ('fighting', 'fighting_suspicious'):
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
            box = obj_data['data'].get('box') or obj_data['data'].get('bbox') or obj_data['data'].get('coordinates')
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
                    "is_abnormal": True, "need_alert": True, "confidence": 0.85,
                    "event_type": "fall_detected"  # 为告警系统提供事件类型
                })
                self.fall_counters[obj_id] = 0 # 确认后重置计数器

        # 清理已消失目标的计数器
        stale_ids = set(self.fall_counters.keys()) - active_ids
        for stale_id in stale_ids:
            del self.fall_counters[stale_id]
            
        return fall_behaviors
        
    def _detect_waving(self, tracked_objects: Dict) -> List[Dict]:
        """分析被追踪目标，判断是否挥手。"""
        waving_behaviors = []
        active_ids = set(tracked_objects.keys())
        
        for obj_id, obj_data in tracked_objects.items():
            # 仅对人员目标进行挥手检测，忽略其它类别
            obj_label = (obj_data.get('data', {}).get('class_name') or '').lower()
            if obj_label != 'person':
                # 将非人目标的计数器清零，避免误报
                if obj_id in self.waving_counters:
                    self.waving_counters[obj_id] = 0
                continue

            # 如果目标已被确认为挥手，则保持该状态
            if obj_data.get('is_waving', False):
                box_ref = obj_data['data'].get('box') or obj_data['data'].get('bbox') or obj_data['data'].get('coordinates')
                waving_behaviors.append({
                    "person_id": obj_id, "box": box_ref, "behavior": "waving_hand",
                    "is_abnormal": True, "need_alert": True, "confidence": 0.90,
                    "event_type": "waving_detected"
                })
                continue

            history = self.tracker.history.get(obj_id)
            if not history or len(history) < 5:  # 需要足够的历史数据来判断
                self.waving_counters[obj_id] = 0
                continue
            
            # --- 速度计算 ---
            p1 = history[-1]['centroid']
            t1 = history[-1]['timestamp']
            p0 = history[-5]['centroid']
            t0 = history[-5]['timestamp']
            
            delta_t = t1 - t0
            if delta_t < 1e-6:
                continue

            vy = (p1[1] - p0[1]) / delta_t
            speed = np.linalg.norm(np.array(p1) - np.array(p0)) / delta_t

            # --- BBox宽度变化计算 ---
            current_box = history[-1]['box']
            prev_box = history[-2]['box']
            width_change = abs((current_box[2] - current_box[0]) - (prev_box[2] - prev_box[0]))

            # --- 挥手条件判断 ---
            is_waving_candidate = False
            # 条件: 目标有一定速度 & 垂直移动不快 & BBox宽度有明显变化
            if speed > self.waving_min_motion and abs(vy) < self.waving_max_vertical_motion:
                if width_change > self.waving_min_box_width_change:
                    is_waving_candidate = True

            if is_waving_candidate:
                self.waving_counters[obj_id] += 1
            else:
                self.waving_counters[obj_id] = 0
            
            if self.waving_counters[obj_id] >= self.waving_confidence_threshold:
                self.tracker.objects[obj_id]['is_waving'] = True
                waving_behaviors.append({
                    "person_id": obj_id, "box": current_box, "behavior": "waving_hand",
                    "is_abnormal": True, "need_alert": True, "confidence": 0.85,
                    "event_type": "waving_detected"
                })
                self.waving_counters[obj_id] = 0

        # 清理已消失目标的计数器
        stale_ids = set(self.waving_counters.keys()) - active_ids
        for stale_id in stale_ids:
            del self.waving_counters[stale_id]
            
        return waving_behaviors
        
    def _detect_fights(self, tracked_objects: Dict, audio_events: List[str]) -> Dict:
        """
        分析追踪目标，结合音频事件判断是否发生打架。
        - 视觉判断: 多个高速运动且彼此靠近的目标。
        - 音频判断: 是否检测到尖叫、大吼等声音。
        - 联动决策: 只有在音视频都满足条件时，才触发高置信度的打架告警。
        """
        # 筛选出未跌倒的活跃人员进行分析
        active_persons = {oid: data for oid, data in tracked_objects.items() if not data.get('has_fallen')}

        if len(active_persons) < 2:
            self.fight_event = None # 人数不足，重置打架事件
            return None

        # --- 音频事件判断 ---
        has_audio_cue = any(event in self.fight_audio_events for event in audio_events)

        # --- 视觉事件判断 ---
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
        
        if not candidate_pairs:
            self.fight_event = None
            return None
        
        current_candidate_group = set()
        for p1, p2 in candidate_pairs:
            current_candidate_group.add(p1)
            current_candidate_group.add(p2)

        if self.fight_event and self.fight_event['person_ids'] == current_candidate_group:
            self.fight_event['counter'] += 1
        else:
            self.fight_event = {'person_ids': current_candidate_group, 'counter': 1}
        
        # --- 联动决策 ---
        if self.fight_event['counter'] >= self.fight_confirmation_frames:
            involved_boxes = [
                (active_persons[pid]['data'].get('box') or active_persons[pid]['data'].get('bbox') or active_persons[pid]['data'].get('coordinates'))
                for pid in self.fight_event['person_ids']
            ]
            # 视觉条件已满足，现在根据音频信号决定告警级别
            if has_audio_cue:
                # 音视频联动确认 -> 高置信度告警，并生成组合框 (包围所有相关人员)
                xs = [b[0] for b in involved_boxes] + [b[2] for b in involved_boxes]
                ys = [b[1] for b in involved_boxes] + [b[3] for b in involved_boxes]
                group_box = [min(xs), min(ys), max(xs), max(ys)]

                return {
                    "person_ids": list(self.fight_event['person_ids']),
                    "boxes": involved_boxes,
                    "group_box": group_box,
                    "behavior": "fighting",
                    "is_abnormal": True,
                    "need_alert": True,
                    "confidence": 0.90,
                    "event_type": "fighting_detected_av"
                }
            else:
                # 仅视觉满足; 若不强制音频，也视为告警
                return {
                    "person_ids": list(self.fight_event['person_ids']),
                    "boxes": involved_boxes,
                    "behavior": "fighting_suspicious" if self.require_audio_for_fight else "fighting",
                    "is_abnormal": True,
                    "need_alert": not self.require_audio_for_fight,
                    "confidence": 0.80 if not self.require_audio_for_fight else 0.70,
                    "event_type": "fighting_detected_visual_only"
            }
            
        return None