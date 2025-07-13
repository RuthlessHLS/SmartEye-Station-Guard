# 文件: ai_service/core/object_detection.py
# 描述: 使用YOLOv8的通用目标检测器，支持动态配置和过滤。

import torch
import numpy as np
from typing import List, Dict, Optional, Any
from ultralytics import YOLO
import os
import logging

# 获取logger实例
logger = logging.getLogger(__name__)


class GenericPredictor:
    """
    使用YOLOv8的通用目标检测器。
    相比Faster R-CNN，具有更好的性能和更快的速度。
    支持从外部配置加载敏感度参数和过滤条件。
    """

    def __init__(self, model_weights_path: str, num_classes: int, class_names: List[str]):
        """
        初始化YOLOv8检测器。

        参数:
            model_weights_path (str): 指向模型权重文件的完整路径
            num_classes (int): 类别数量（包括背景，COCO数据集通常为80+1）
            class_names (List[str]): 类别名称列表，与模型类别ID对应
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"通用目标检测器正在使用设备: {self.device}")

        self.class_names = class_names
        self.enabled = True  # 控制检测器是否启用

        self.model: Optional[YOLO] = None  # 初始化为None，以便在加载失败时判断

        # 内部默认过滤参数 (可被外部配置覆盖)
        self._default_config = {
            'confidence_threshold': 0.25,  # 基础置信度阈值
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
        self.current_config = self._default_config.copy()  # 当前生效的配置

        # 加载YOLOv8模型
        try:
            if os.path.exists(model_weights_path):
                logger.info(f"正在从本地路径加载YOLOv8模型: {model_weights_path}")
                self.model = YOLO(model_weights_path)
            else:
                logger.warning(f"本地权重文件不存在 ({model_weights_path})，尝试使用预训练的YOLOv8n模型。")
                self.model = YOLO('yolov8n.pt')  # 这将从Ultralytics下载预训练模型

            self.model.to(self.device)
            logger.info("成功加载YOLOv8模型")
        except Exception as e:
            self.model = None  # 确保模型为None如果加载失败
            logger.critical(f"FATAL: 加载YOLOv8模型失败: {e}")
            # 在生产环境中，这里可能需要更优雅的失败处理，例如抛出异常或退出
            raise RuntimeError(f"YOLOv8模型加载失败: {e}")

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

        # 获取当前配置
        base_confidence_threshold = self.current_config['confidence_threshold']
        special_class_thresholds = self.current_config['special_class_thresholds']
        area_ratio_threshold = self.current_config['area_ratio_threshold']
        aspect_ratio_limit = self.current_config['aspect_ratio_limit']
        enable_size_filter = self.current_config['enable_size_filter']
        enable_aspect_ratio_filter = self.current_config['enable_aspect_ratio_filter']

        img_height, img_width = frame.shape[:2]
        img_area = img_height * img_width

        detections = []
        try:
            # 使用YOLOv8进行预测
            # conf 参数设置为基础置信度，后续会根据类别调整
            results = self.model(frame, conf=base_confidence_threshold, verbose=False)

            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    class_name = self.class_names[cls_id] if cls_id < len(self.class_names) else 'unknown'
                    confidence = box.conf[0].item()
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)

                    # 获取该类别的最终置信度阈值
                    class_specific_threshold = special_class_thresholds.get(class_name, base_confidence_threshold)

                    if confidence >= class_specific_threshold:
                        box_width = x2 - x1
                        box_height = y2 - y1
                        box_area = box_width * box_height

                        # 过滤条件
                        passed_filters = True
                        if enable_size_filter and (box_area <= 0 or box_area / img_area > area_ratio_threshold):
                            passed_filters = False

                        if enable_aspect_ratio_filter and (box_width <= 0 or box_height <= 0):
                            passed_filters = False  # 避免除以零
                        elif enable_aspect_ratio_filter:
                            aspect_ratio = max(box_width / box_height, box_height / box_width)
                            if aspect_ratio > aspect_ratio_limit:
                                passed_filters = False

                        if passed_filters:
                            detections.append({
                                "class_name": class_name,
                                "confidence": confidence,
                                "coordinates": [x1, y1, x2, y2]
                            })
            return detections

        except Exception as e:
            logger.error(f"YOLOv8预测过程出错: {e}", exc_info=True)  # 打印堆栈信息
            return []

    def set_enabled(self, enabled: bool):
        """启用或禁用检测器"""
        self.enabled = enabled
        logger.info(f"通用目标检测器已{'启用' if enabled else '禁用'}")