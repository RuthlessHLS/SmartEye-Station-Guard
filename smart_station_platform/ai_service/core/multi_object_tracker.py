"""
多目标追踪模块 - 基于Deep SORT算法
实现专业的多目标追踪功能，为检测到的目标分配持久性的track_id
"""

import os
import numpy as np
import torch
import cv2
from typing import List, Dict, Tuple, Optional
import logging

try:
    from deep_sort import DeepSort
except ImportError:
    try:
        from deep_sort_pytorch import DeepSort
    except ImportError:
        logging.warning("Deep SORT库未安装，将使用备用追踪方案")
        DeepSort = None

class DeepSORTTracker:
    """
    基于Deep SORT的多目标追踪器
    
    功能：
    - 为检测到的目标分配持久性的track_id
    - 处理目标的出现、消失和重新出现
    - 提供比简单稳定化更准确的目标追踪
    """
    
    def __init__(self, 
                 max_dist: float = 0.2,
                 min_confidence: float = 0.3,
                 nms_max_overlap: float = 1.0,
                 max_iou_distance: float = 0.7,
                 max_age: int = 30,
                 n_init: int = 3):
        """
        初始化Deep SORT追踪器
        
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
        
        # 初始化Deep SORT追踪器
        self.tracker = None
        self._init_tracker()
        
        # 类别映射（COCO数据集）
        self.class_names = {
            0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 4: 'airplane',
            5: 'bus', 6: 'train', 7: 'truck', 8: 'boat', 9: 'traffic light',
            10: 'fire hydrant', 11: 'stop sign', 12: 'parking meter', 13: 'bench',
            14: 'bird', 15: 'cat', 16: 'dog', 17: 'horse', 18: 'sheep', 19: 'cow',
            20: 'elephant', 21: 'bear', 22: 'zebra', 23: 'giraffe', 24: 'backpack',
            25: 'umbrella', 26: 'handbag', 27: 'tie', 28: 'suitcase', 29: 'frisbee',
            30: 'skis', 31: 'snowboard', 32: 'sports ball', 33: 'kite',
            34: 'baseball bat', 35: 'baseball glove', 36: 'skateboard',
            37: 'surfboard', 38: 'tennis racket', 39: 'bottle', 40: 'wine glass',
            41: 'cup', 42: 'fork', 43: 'knife', 44: 'spoon', 45: 'bowl',
            46: 'banana', 47: 'apple', 48: 'sandwich', 49: 'orange', 50: 'broccoli',
            51: 'carrot', 52: 'hot dog', 53: 'pizza', 54: 'donut', 55: 'cake',
            56: 'chair', 57: 'couch', 58: 'potted plant', 59: 'bed',
            60: 'dining table', 61: 'toilet', 62: 'tv', 63: 'laptop', 64: 'mouse',
            65: 'remote', 66: 'keyboard', 67: 'cell phone', 68: 'microwave',
            69: 'oven', 70: 'toaster', 71: 'sink', 72: 'refrigerator', 73: 'book',
            74: 'clock', 75: 'vase', 76: 'scissors', 77: 'teddy bear',
            78: 'hair drier', 79: 'toothbrush'
        }
        
        # 备用追踪器（当Deep SORT不可用时）
        self.fallback_tracker = FallbackTracker()
        
        print(f"DeepSORTTracker 初始化完成，使用{'Deep SORT' if self.tracker else '备用追踪器'}")
    
    def _init_tracker(self):
        """初始化Deep SORT追踪器"""
        if DeepSort is None:
            print("⚠️ Deep SORT库不可用，将使用备用追踪方案")
            return
            
        try:
            # 检查是否有CUDA可用
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            
            # 初始化Deep SORT
            # 注意：可能需要根据实际安装的deep_sort_pytorch版本调整参数
            self.tracker = DeepSort(
                model_path='./weights/ckpt.t7',  # 默认Re-ID模型路径
                max_dist=self.max_dist,
                min_confidence=self.min_confidence,
                nms_max_overlap=self.nms_max_overlap,
                max_iou_distance=self.max_iou_distance,
                max_age=self.max_age,
                n_init=self.n_init,
                use_cuda=torch.cuda.is_available()
            )
            print(f"✅ Deep SORT追踪器初始化成功，使用设备: {device}")
        except Exception as e:
            print(f"⚠️ Deep SORT初始化失败: {e}")
            print("将使用备用追踪器")
            self.tracker = None
    
    def update(self, detections: List[Dict], original_frame: np.ndarray) -> List[Dict]:
        """
        更新追踪器并返回追踪结果
        
        Args:
            detections: YOLOv8检测结果列表，每个元素包含：
                       {coordinates: [x1, y1, x2, y2], confidence: float, class_name: str, class_id: int}
            original_frame: 原始图像帧，用于特征提取
            
        Returns:
            追踪结果列表，每个元素包含：
            {coordinates: [x1, y1, x2, y2], confidence: float, class_name: str, 
             class_id: int, tracking_id: str, type: str}
        """
        if not detections:
            return []
        
        # 如果Deep SORT可用，使用Deep SORT
        if self.tracker is not None:
            return self._update_with_deepsort(detections, original_frame)
        else:
            # 使用备用追踪器
            return self._update_with_fallback(detections)
    
    def _update_with_deepsort(self, detections: List[Dict], original_frame: np.ndarray) -> List[Dict]:
        """使用Deep SORT进行追踪"""
        try:
            # 转换检测格式为Deep SORT需要的格式
            bbox_xywh = []
            confidences = []
            class_ids = []
            
            for det in detections:
                coords = det['coordinates']  # [x1, y1, x2, y2]
                
                # 转换为 (center_x, center_y, width, height)
                x1, y1, x2, y2 = coords
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                width = x2 - x1
                height = y2 - y1
                
                bbox_xywh.append([center_x, center_y, width, height])
                confidences.append(det['confidence'])
                class_ids.append(det.get('class_id', 0))
            
            # 转换为numpy数组
            bbox_xywh = np.array(bbox_xywh)
            confidences = np.array(confidences)
            class_ids = np.array(class_ids)
            
            # 调用Deep SORT更新
            tracks = self.tracker.update(bbox_xywh, confidences, original_frame)
            
            # 转换追踪结果
            tracked_objects = []
            for track in tracks:
                # Deep SORT返回格式: [x1, y1, x2, y2, track_id]
                x1, y1, x2, y2, track_id = track[:5]
                
                # 找到对应的类别信息
                # 这里需要将追踪结果与原始检测进行匹配
                class_info = self._match_track_to_detection(
                    [x1, y1, x2, y2], detections)
                
                tracked_obj = {
                    'coordinates': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': class_info['confidence'],
                    'class_name': class_info['class_name'],
                    'class_id': class_info['class_id'],
                    'tracking_id': f"DS_{int(track_id)}",
                    'type': 'object'
                }
                tracked_objects.append(tracked_obj)
            
            return tracked_objects
            
        except Exception as e:
            print(f"⚠️ Deep SORT追踪过程出错: {e}")
            # 回退到备用追踪器
            return self._update_with_fallback(detections)
    
    def _update_with_fallback(self, detections: List[Dict]) -> List[Dict]:
        """使用备用追踪器"""
        return self.fallback_tracker.update(detections)
    
    def _match_track_to_detection(self, track_bbox: List[float], detections: List[Dict]) -> Dict:
        """
        将追踪结果匹配到原始检测，获取类别信息
        
        Args:
            track_bbox: 追踪框 [x1, y1, x2, y2]
            detections: 原始检测结果列表
            
        Returns:
            匹配的检测信息 {confidence, class_name, class_id}
        """
        best_iou = 0
        best_match = {
            'confidence': 0.5,
            'class_name': 'unknown',
            'class_id': -1
        }
        
        for det in detections:
            iou = self._calculate_iou(track_bbox, det['coordinates'])
            if iou > best_iou:
                best_iou = iou
                best_match = {
                    'confidence': det['confidence'],
                    'class_name': det['class_name'],
                    'class_id': det.get('class_id', 0)
                }
        
        return best_match
    
    def _calculate_iou(self, box1: List[float], box2: List[float]) -> float:
        """计算两个边界框的IoU"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        # 计算交集区域
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i <= x1_i or y2_i <= y1_i:
            return 0.0
        
        # 交集面积
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        
        # 并集面积
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def reset(self):
        """重置追踪器"""
        if self.tracker is not None:
            try:
                # 重新初始化Deep SORT
                self._init_tracker()
            except Exception as e:
                print(f"重置Deep SORT追踪器失败: {e}")
        
        # 重置备用追踪器
        self.fallback_tracker.reset()


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