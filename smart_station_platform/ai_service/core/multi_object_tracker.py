# 文件: ai_service/core/multi_object_tracker.py
# 描述: 多目标追踪模块 - 提供轻量级基于IoU的追踪功能，为检测到的目标分配持久性track_id。

import numpy as np
import cv2 # 尽管这里不直接使用cv2，但一些图像操作库可能会用到
from typing import List, Dict, Tuple, Optional
import logging
import time # 用于跟踪对象的年龄

logger = logging.getLogger(__name__)

class DeepSORTTracker:
    """
    多目标追踪器 (包装器/备用方案)
    
    此类主要作为 Deep SORT 追踪器的接口层，
    但目前使用一个轻量级的 FallbackTracker 作为其实现。
    未来可在此处集成完整的 Deep SORT 算法。
    """
    
    def __init__(self, 
                 max_dist: float = 0.2,          # 最大余弦距离阈值 (Deep SORT参数，FallbackTracker不使用)
                 min_confidence: float = 0.3,    # 最小检测置信度 (Deep SORT参数，FallbackTracker可能间接使用)
                 nms_max_overlap: float = 1.0,   # NMS最大重叠阈值 (Deep SORT参数，FallbackTracker不使用)
                 max_iou_distance: float = 0.7,  # 最大IoU距离 (Deep SORT参数，FallbackTracker使用IoU阈值)
                 max_age: int = 30,              # 目标最大生存时间（帧数）
                 n_init: int = 3):               # 确认轨道所需的连续检测次数
        """
        初始化追踪器。
        
        Args:
            max_dist: 最大余弦距离阈值。
            min_confidence: 最小检测置信度。
            nms_max_overlap: NMS最大重叠阈值。
            max_iou_distance: 最大IoU距离。
            max_age: 目标最大消失帧数（超出此帧数未检测到则移除）。
            n_init: 确认一个新轨道所需的连续检测帧数。
        """
        self.max_dist = max_dist
        self.min_confidence = min_confidence
        self.nms_max_overlap = nms_max_overlap
        self.max_iou_distance = max_iou_distance
        self.max_age = max_age
        self.n_init = n_init
        
        # 使用备用追踪器作为当前实现
        self.tracker = FallbackTracker(
            iou_threshold=1 - self.max_iou_distance, # 将max_iou_distance转换为iou_threshold
            max_disappeared_frames=self.max_age
        )
        
        logger.info("DeepSORTTracker 初始化完成，使用 FallbackTracker 作为当前追踪器实现。")
    
    def update(self, detections: List[Dict], original_frame: Optional[np.ndarray] = None) -> List[Dict]:
        """
        更新追踪器并返回追踪结果。
        
        Args:
            detections: 检测结果列表，每个元素包含：
                       {coordinates: [x1, y1, x2, y2], confidence: float, class_name: str, class_id: int}
            original_frame: 原始图像帧 (可选，用于某些追踪器内部处理，但FallbackTracker不需要)
            
        Returns:
            追踪结果列表，每个元素包含：
            {coordinates: [x1, y1, x2, y2], confidence: float, class_name: str, 
             class_id: int, tracking_id: str, type: str}
        """
        if not detections:
            # 如果没有检测结果，更新追踪器内部状态并返回当前所有仍在追踪的对象（即使是消失状态的）
            # FallbackTracker 的 update 方法在没有新的 detections 时也能处理 tracks 的消失计数
            self.tracker.update([]) 
            # 过滤掉完全消失的轨道，返回剩余的
            return [t for t in self.tracker.get_active_tracks().values() if t.get('disappeared_count', 0) <= self.tracker.max_disappeared_frames]


        tracked_results = self.tracker.update(detections)
        return tracked_results
    
    def reset(self):
        """重置追踪器状态。"""
        self.tracker.reset()
        logger.info("追踪器状态已重置。")


class FallbackTracker:
    """
    备用追踪器 - 当更复杂的追踪算法 (如 Deep SORT) 不可用时使用。
    基于 IoU (Intersection over Union) 匹配和简单的ID分配策略。
    此追踪器为每个被追踪的对象分配一个持久性的 ID，并处理其在帧间的关联。
    """
    
    def __init__(self, iou_threshold: float = 0.3, max_disappeared_frames: int = 10):
        """
        初始化备用追踪器。
        Args:
            iou_threshold (float): IoU 匹配阈值。两个边界框的 IoU 超过此阈值才被认为是同一对象。
            max_disappeared_frames (int): 一个对象在被移除追踪之前可以连续消失的帧数。
        """
        self.tracks: Dict[str, Dict] = {}  # track_id -> track_info (bbox, disappeared_count, class_name, confidence, last_seen_time, etc.)
        self.next_id = 1  # 下一个可用的追踪ID
        self.iou_threshold = iou_threshold
        self.max_disappeared_frames = max_disappeared_frames
        logger.info(f"FallbackTracker 初始化: IoU阈值={self.iou_threshold}, 最大消失帧数={self.max_disappeared_frames}")
    
    def update(self, detections: List[Dict]) -> List[Dict]:
        """
        更新备用追踪器，处理新检测和现有轨道。
        
        Args:
            detections: YOLOv8检测结果列表，每个元素包含：
                        {coordinates: [x1, y1, x2, y2], confidence: float, class_name: str, class_id: int}
                        注意：这里假设 'coordinates' 是 bbox，'class_name' 和 'confidence' 是标准字段。
            
        Returns:
            追踪结果列表，每个元素包含：
            {coordinates: [x1, y1, x2, y2], confidence: float, class_name: str, 
             class_id: int (可选), tracking_id: str, type: str}
        """
        current_active_track_ids = set()
        tracked_objects_output: List[Dict] = []
        
        # 遍历当前帧的所有检测结果
        for det in detections:
            det_bbox = det['coordinates']
            best_match_id = None
            best_iou = 0.0
            
            # 寻找与当前检测结果最佳匹配的现有轨道
            # 考虑所有未被本帧检测匹配过的活跃轨道
            for track_id, track_info in self.tracks.items():
                # 只有在最大消失帧数内且未被当前帧匹配过的轨道才参与匹配
                if track_info['disappeared_count'] <= self.max_disappeared_frames:
                    iou = self._calculate_iou(det_bbox, track_info['bbox'])
                    if iou > best_iou and iou >= self.iou_threshold:
                        best_iou = iou
                        best_match_id = track_id
            
            if best_match_id is not None:
                # 匹配到现有轨道：更新轨道信息
                track_info = self.tracks[best_match_id]
                track_info['bbox'] = det_bbox
                track_info['confidence'] = det['confidence']
                track_info['class_name'] = det['class_name']
                track_info['disappeared_count'] = 0 # 重置消失计数
                track_info['last_seen_time'] = time.time()
                track_info['tracked_count'] += 1 # 增加追踪到的帧数
                current_active_track_ids.add(best_match_id)
                logger.debug(f"🔍 匹配到现有轨道: ID=FB_{best_match_id}, Class={det['class_name']}, Conf={det['confidence']:.2f}")
            else:
                # 未匹配到现有轨道：创建新轨道
                new_track_id = str(self.next_id)
                self.next_id += 1
                self.tracks[new_track_id] = {
                    'bbox': det_bbox,
                    'confidence': det['confidence'],
                    'class_name': det['class_name'],
                    'disappeared_count': 0,
                    'first_seen_time': time.time(),
                    'last_seen_time': time.time(),
                    'tracked_count': 1, # 首次追踪到
                }
                current_active_track_ids.add(new_track_id)
                best_match_id = new_track_id
                logger.debug(f"🆕 创建新轨道: ID=FB_{new_track_id}, Class={det['class_name']}, Conf={det['confidence']:.2f}")

            # 将追踪结果添加到输出列表
            tracked_obj = det.copy()
            tracked_obj['tracking_id'] = f"FB_{best_match_id}" # 添加追踪ID
            tracked_obj['type'] = det.get('type', 'object') # 保持原始类型或默认'object'
            tracked_objects_output.append(tracked_obj)
        
        # 处理未在当前帧中检测到的现有轨道 (更新消失计数或移除)
        tracks_to_remove = []
        for track_id, track_info in self.tracks.items():
            if track_id not in current_active_track_ids:
                track_info['disappeared_count'] += 1
                if track_info['disappeared_count'] > self.max_disappeared_frames:
                    tracks_to_remove.append(track_id)
                    logger.debug(f"🗑️ 轨道移除: ID=FB_{track_id} (消失 {track_info['disappeared_count']} 帧)")
                else:
                    # 将消失但未被移除的轨道也添加到输出，使用其上次已知位置
                    # 可以在这里添加位置预测逻辑，但为了简单，目前只返回上次位置
                    tracked_obj_ghost = {
                        'coordinates': track_info['bbox'],
                        'confidence': track_info['confidence'] * (1 - track_info['disappeared_count'] / (self.max_disappeared_frames + 1)), # 置信度逐渐降低
                        'class_name': track_info['class_name'],
                        'tracking_id': f"FB_{track_id}",
                        'type': track_info.get('type', 'object'),
                        'is_disappeared': True, # 标记为消失的轨道
                        'disappeared_frames': track_info['disappeared_count']
                    }
                    tracked_objects_output.append(tracked_obj_ghost)
                    logger.debug(f"👻 轨道消失计数: ID=FB_{track_id}, Count={track_info['disappeared_count']}")

        # 移除过期的轨道
        for track_id in tracks_to_remove:
            del self.tracks[track_id]
        
        return tracked_objects_output
    
    def _calculate_iou(self, box1: List[float], box2: List[float]) -> float:
        """计算两个边界框的IoU（Intersection over Union）。"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        x_left = max(x1_1, x1_2)
        y_top = max(y1_1, y1_2)
        x_right = min(x2_1, x2_2)
        y_bottom = min(y2_1, y2_2)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0 # 无交集
        
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        
        box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
        box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
        
        union_area = box1_area + box2_area - intersection_area
        
        return intersection_area / union_area if union_area > 0 else 0.0
    
    def reset(self):
        """重置备用追踪器状态。"""
        self.tracks = {}
        self.next_id = 1
        logger.info("FallbackTracker 状态已重置。")

    def get_active_tracks(self) -> Dict[str, Dict]:
        """获取所有当前活跃（未被移除）的轨道信息。"""
        return self.tracks