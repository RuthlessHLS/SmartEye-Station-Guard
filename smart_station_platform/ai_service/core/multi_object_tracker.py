"""
多目标追踪模块 - 使用备用追踪器
实现基本的多目标追踪功能，为检测到的目标分配持久性的track_id
"""

import os
import numpy as np
import cv2
from typing import List, Dict, Tuple, Optional
import logging

class DeepSORTTracker:
    """
    多目标追踪器（使用备用方案）
    
    功能：
    - 为检测到的目标分配持久性的track_id
    - 处理目标的出现、消失和重新出现
    - 使用IoU匹配的简单追踪算法
    """
    
    def __init__(self, 
                 max_dist: float = 0.2,
                 min_confidence: float = 0.3,
                 nms_max_overlap: float = 1.0,
                 max_iou_distance: float = 0.7,
                 max_age: int = 30,
                 n_init: int = 3):
        """
        初始化追踪器
        
        Args:
            max_dist: 最大余弦距离阈值
            min_confidence: 最小检测置信度
            nms_max_overlap: NMS最大重叠阈值
            max_iou_distance: 最大IoU距离
            max_age: 目标最大生存时间（帧数）
            n_init: 确认轨道所需的连续检测次数
        """
        self.max_dist = max_dist
        self.min_confidence = min_confidence
        self.nms_max_overlap = nms_max_overlap
        self.max_iou_distance = max_iou_distance
        self.max_age = max_age
        self.n_init = n_init
        
        # 使用备用追踪器
        self.tracker = FallbackTracker()
        
        print("DeepSORTTracker 初始化完成，使用备用追踪器")
    
    def update(self, detections: List[Dict], original_frame: np.ndarray = None) -> List[Dict]:
        """
        更新追踪器并返回追踪结果
        
        Args:
            detections: YOLOv8检测结果列表，每个元素包含：
                       {coordinates: [x1, y1, x2, y2], confidence: float, class_name: str, class_id: int}
            original_frame: 原始图像帧（备用追踪器不需要）
            
        Returns:
            追踪结果列表，每个元素包含：
            {coordinates: [x1, y1, x2, y2], confidence: float, class_name: str, 
             class_id: int, tracking_id: str, type: str}
        """
        return self.tracker.update(detections)
    
    def reset(self):
        """重置追踪器"""
        self.tracker.reset()


class FallbackTracker:
    """
    备用追踪器 - 当Deep SORT不可用时使用
    基于IoU匹配和简单的ID分配策略
    """
    
    def __init__(self):
        self.tracks = {}  # track_id -> track_info
        self.next_id = 1
        self.max_disappeared = 10  # 最大消失帧数
        self.iou_threshold = 0.3   # IoU匹配阈值
    
    def update(self, detections: List[Dict]) -> List[Dict]:
        """更新备用追踪器"""
        current_tracks = {}
        tracked_objects = []
        
        # 为每个检测分配或匹配track_id
        for det in detections:
            det_bbox = det['coordinates']
            best_match_id = None
            best_iou = 0
            
            # 寻找最佳匹配的现有轨道
            for track_id, track_info in self.tracks.items():
                if track_info['disappeared'] > self.max_disappeared:
                    continue
                    
                iou = self._calculate_iou(det_bbox, track_info['bbox'])
                if iou > best_iou and iou > self.iou_threshold:
                    best_iou = iou
                    best_match_id = track_id
            
            if best_match_id is not None:
                # 更新现有轨道
                track_id = best_match_id
                current_tracks[track_id] = {
                    'bbox': det_bbox,
                    'disappeared': 0,
                    'class_name': det['class_name'],
                    'confidence': det['confidence']
                }
            else:
                # 创建新轨道
                track_id = self.next_id
                self.next_id += 1
                current_tracks[track_id] = {
                    'bbox': det_bbox,
                    'disappeared': 0,
                    'class_name': det['class_name'],
                    'confidence': det['confidence']
                }
            
            # 添加到结果中
            tracked_obj = det.copy()
            tracked_obj['tracking_id'] = f"FB_{track_id}"
            tracked_obj['type'] = 'object'
            tracked_objects.append(tracked_obj)
        
        # 更新消失的轨道
        for track_id, track_info in self.tracks.items():
            if track_id not in current_tracks:
                track_info['disappeared'] += 1
                if track_info['disappeared'] <= self.max_disappeared:
                    current_tracks[track_id] = track_info
        
        # 更新轨道字典
        self.tracks = current_tracks
        
        return tracked_objects
    
    def _calculate_iou(self, box1: List[float], box2: List[float]) -> float:
        """计算IoU（与主类相同的实现）"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i <= x1_i or y2_i <= y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def reset(self):
        """重置备用追踪器"""
        self.tracks = {}
        self.next_id = 1 