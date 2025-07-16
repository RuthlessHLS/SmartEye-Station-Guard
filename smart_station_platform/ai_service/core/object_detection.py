# 文件: ai_service/core/object_detection.py
# 描述: 使用YOLOv8的通用目标检测器，支持动态配置和过滤。

import os
import torch
import numpy as np
from PIL import Image
import cv2  # <-- 确保导入了 cv2
from typing import List, Dict, Optional, Any
from ultralytics import YOLO
import logging

# 【修改】从正确的工具文件中导入
from .ai_models.torch_utils import non_max_suppression, select_device

# 获取logger实例
logger = logging.getLogger(__name__)


class ObjectDetector:
    """
    使用YOLOv8的通用目标检测器。
    相比Faster R-CNN，具有更好的性能和更快的速度。
    支持从外部配置加载敏感度参数和过滤条件。
    """

    def __init__(self, model_weights_path: str, allowed_classes: List[str]):
        """
        初始化YOLOv8检测器，并根据白名单筛选类别。

        参数:
            model_weights_path (str): 指向模型权重文件的完整路径
            allowed_classes (List[str]): 只应检测的类别名称列表。
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"通用目标检测器正在使用设备: {self.device}")

        # 加载YOLOv8模型
        try:
            if os.path.exists(model_weights_path):
                self.model = YOLO(model_weights_path)
            else:
                logger.warning(f"本地权重文件不存在 ({model_weights_path})，将使用预训练的YOLOv8n。")
                self.model = YOLO('yolov8n.pt')
            self.model.to(self.device)
            logger.info("成功加载YOLOv8模型")
        except Exception as e:
            self.model = None
            logger.critical(f"FATAL: 加载YOLOv8模型失败: {e}")
            raise RuntimeError(f"YOLOv8模型加载失败: {e}")

        # 从模型中获取完整的类别名称
        self.full_class_names = self.model.names if hasattr(self.model, 'names') else []
        if not self.full_class_names:
             logger.error("无法从YOLOv8模型中获取类别名称。")
             # 创建一个从id到name的映射
             self.full_class_names = {i: f'class_{i}' for i in range(80)} # Fallback for COCO

        # 根据白名单筛选出需要检测的类别ID
        self.allowed_class_ids = [
            k for k, v in self.full_class_names.items() if v in allowed_classes
        ]
        
        self.enabled = True
        self.current_config = {
            'confidence_threshold': 0.25,
            'area_ratio_threshold': 0.9,  # 框面积不能超过图像的X%
            'aspect_ratio_limit': 6.0,  # 宽高比不能过于极端 (例如 1:6 或 6:1)
            'enable_size_filter': True,  # 是否启用尺寸过滤
            'enable_aspect_ratio_filter': True,  # 是否启用宽高比过滤
            'special_class_thresholds': {  # 特定类别的置信度要求
                'bicycle': 0.35,
                'sports ball': 0.35,
                'carrot': 0.40,
                'cell phone': 0.35,
                'book': 0.35
            }
        }
        logger.info(f"目标检测器已配置为仅检测以下类别ID: {self.allowed_class_ids}")


    def update_config(self, new_config: Dict[str, Any]):
        """
        更新检测器的配置参数。
        Args:
            new_config (Dict[str, Any]): 包含要更新的配置项的字典。
        """
        for key, value in new_config.items():
            if key in self.current_config:
                self.current_config[key] = value
                logger.info(f"更新目标检测配置: {key} = {value}")
            elif key == 'special_class_thresholds' and isinstance(value, dict):
                # 允许更新或扩展特定类别阈值
                self.current_config['special_class_thresholds'].update(value)
                logger.info(f"更新特定类别置信度阈值: {value}")
            else:
                logger.warning(f"尝试更新不存在的配置项: {key}")
        logger.info(f"目标检测器当前配置: {self.current_config}")

    def predict(self, frame: np.ndarray) -> List[Dict]:
        """
        使用YOLOv8对单个图像帧进行目标检测。
        参数:
            frame (np.ndarray): OpenCV BGR格式的图像
        返回:
            检测结果列表，每个结果包含类别名称、置信度和坐标
        """
        if not self.enabled or self.model is None:
            return []

        base_confidence_threshold = self.current_config.get('confidence_threshold', 0.25)
        
        detections = []
        try:
            # 【核心优化】直接在模型调用中传入筛选后的类别ID
            results = self.model(
                frame, 
                classes=self.allowed_class_ids, 
                conf=base_confidence_threshold, 
                verbose=False
            )

            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    # 使用完整的类别列表来查找名称
                    class_name = self.full_class_names.get(cls_id, 'unknown')
                    confidence = box.conf[0].item()
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)

                    detections.append({
                        "class_name": class_name,
                        "confidence": confidence,
                        "coordinates": [int(c) for c in [x1, y1, x2, y2]]
                    })
            return detections

        except Exception as e:
            logger.error(f"YOLOv8预测过程出错: {e}", exc_info=True)
            return []

    def set_enabled(self, enabled: bool):
        """启用或禁用检测器"""
        self.enabled = enabled
        logger.info(f"通用目标检测器已{'启用' if enabled else '禁用'}")

    # 【新增】一个辅助函数，用于正确地还原坐标
    def scale_coords(self, img1_shape, coords, img0_shape, ratio_pad=None):
        """
        Rescale coords (xyxy) from img1_shape to img0_shape.
        """
        if ratio_pad is None:  # calculate from img0_shape
            gain = min(img1_shape[0] / img0_shape[0], img1_shape[1] / img0_shape[1])  # gain  = old / new
            pad = (img1_shape[1] - img0_shape[1] * gain) / 2, (img1_shape[0] - img0_shape[0] * gain) / 2  # wh padding
        else:
            gain = ratio_pad[0][0]
            pad = ratio_pad[1]

        coords[:, [0, 2]] -= pad[0]  # x padding
        coords[:, [1, 3]] -= pad[1]  # y padding
        coords[:, :4] /= gain
        
        # 限制坐标在图像边界内
        coords[:, [0, 2]] = coords[:, [0, 2]].clamp(0, img0_shape[1])  # x1, x2
        coords[:, [1, 3]] = coords[:, [1, 3]].clamp(0, img0_shape[0])  # y1, y2
        return coords
