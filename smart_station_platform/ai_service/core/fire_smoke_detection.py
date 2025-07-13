# 文件: ai_service/core/fire_smoke_detection.py
# 描述: 火焰与烟雾检测器，使用YOLOv8模型实现实时检测，支持动态配置和辅助颜色检测。

import os
import cv2
import numpy as np
import time
from ultralytics import YOLO  # 确保已安装 ultralytics
from typing import List, Dict, Union, Optional, Any
import torch
import logging

logger = logging.getLogger(__name__)


class FlameSmokeDetector:
    """
    火焰与烟雾检测器，使用YOLOv8模型实现实时检测。
    具备以下功能：
    - 检测图像中的火焰和烟雾
    - 支持视频流检测
    - 提供置信度和位置信息
    - 支持动态配置检测参数
    - 包含辅助的颜色检测逻辑
    """

    def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None):
        """
        初始化火焰烟雾检测器。

        Args:
            model_path (str): YOLOv8模型权重文件的路径 (.pt)。如果为None，将尝试从环境变量中配置的资源路径查找。
            device (str): 使用的设备，可以是'cpu'或'cuda:0'等。为None时自动选择可用设备。
        """
        self.enabled = True  # 控制检测器是否启用

        # 自动检测设备
        if device is None:
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.model: Optional[YOLO] = None
        self.class_names: Dict[int, str] = {}
        self.is_fire_model: bool = False
        self.fire_class_ids: List[int] = []
        self.smoke_class_ids: List[int] = []
        self.fire_related_ids: List[int] = []

        # 内部默认配置 (可被外部覆盖)
        self._default_config = {
            'confidence_threshold': 0.25,  # 基础置信度阈值
            'iou_threshold': 0.5,  # 用于合并检测结果的IoU阈值
            'enable_color_fallback': True  # 是否在YOLO未检测到时尝试颜色检测
        }
        self.current_config = self._default_config.copy()

        # 尝试找到并加载模型
        self._load_model(model_path)

    def _load_model(self, model_path: Optional[str]):
        """内部方法：加载YOLOv8模型。"""
        resolved_model_path = model_path
        if resolved_model_path is None:
            # 检查环境变量中的资源目录
            asset_base_path = os.getenv("G_DRIVE_ASSET_PATH")
            if asset_base_path and os.path.isdir(asset_base_path):
                fire_model_path = os.path.join(asset_base_path, "models", "torch", "yolov8n-fire.pt")
                if os.path.exists(fire_model_path):
                    resolved_model_path = fire_model_path
                    logger.info(f"使用专用火焰检测模型: {resolved_model_path}")
                else:
                    general_model_path = os.path.join(asset_base_path, "models", "torch", "yolov8n.pt")
                    if os.path.exists(general_model_path):
                        resolved_model_path = general_model_path
                        logger.warning(f"未找到专用火焰检测模型，使用通用YOLO模型: {resolved_model_path}")
                    else:
                        logger.warning(f"警告: 未找到任何本地YOLO模型在 '{asset_base_path}/models/torch/'。")
            if resolved_model_path is None:
                logger.warning("未指定模型路径且未找到本地模型，将尝试下载 YOLOv8n 模型。")
                resolved_model_path = 'yolov8n.pt'  # YOLOv8会自动下载此模型

        try:
            self.model = YOLO(resolved_model_path)
            self.model.to(self.device)  # 将模型移至指定设备
            self.class_names = self.model.names  # 获取模型的类别名称

            # 确定模型类型和相关类别ID
            self.is_fire_model = any(name.lower() in ['fire', 'flame', 'smoke'] for name in self.class_names.values())
            self.fire_class_ids = [k for k, v in self.class_names.items() if
                                   any(term in v.lower() for term in ['fire', 'flame'])]
            self.smoke_class_ids = [k for k, v in self.class_names.items() if 'smoke' in v.lower()]

            if not self.is_fire_model:  # 如果是通用模型，添加一些火灾相关物体的类别
                self.fire_related_objects = ['oven', 'stove', 'candle', 'lighter', 'match', 'torch', 'campfire']
                self.fire_related_ids = [k for k, v in self.class_names.items() if
                                         any(obj in v.lower() for obj in self.fire_related_objects)]

            logger.info(f"火焰烟雾检测模型加载成功。使用设备: {self.device}")
            logger.info(f"模型类别: {self.class_names}")
            logger.info(f"火焰类别ID: {self.fire_class_ids}, 烟雾类别ID: {self.smoke_class_ids}")
            if not self.is_fire_model:
                logger.info(f"火灾相关物体类别ID (通用模型): {self.fire_related_ids}")

        except Exception as e:
            self.model = None
            logger.critical(f"FATAL: 火焰烟雾检测模型加载失败: {e}", exc_info=True)
            raise RuntimeError(f"火焰烟雾检测模型加载失败: {e}")

    def update_config(self, new_config: Dict[str, Any]):
        """
        更新检测器的配置参数。
        Args:
            new_config (Dict[str, Any]): 包含要更新的配置项的字典。
        """
        for key, value in new_config.items():
            if key in self.current_config:
                self.current_config[key] = value
                logger.info(f"更新火焰烟雾检测配置: {key} = {value}")
            else:
                logger.warning(f"尝试更新不存在的配置项: {key}")
        logger.info(f"火焰烟雾检测器当前配置: {self.current_config}")

    def set_enabled(self, enabled: bool):
        """启用或禁用检测器。"""
        self.enabled = enabled
        logger.info(f"火焰烟雾检测器已{'启用' if enabled else '禁用'}。")

    def detect(self, image: np.ndarray) -> List[Dict]:
        """
        对图像进行火焰和烟雾检测。
        Args:
            image (np.ndarray): 输入图像 (BGR格式)。
        Returns:
            list: 包含检测结果字典的列表。
        """
        if not self.enabled or self.model is None:
            return []

        processed_results: List[Dict[str, Any]] = []
        confidence_threshold = self.current_config['confidence_threshold']
        iou_threshold = self.current_config['iou_threshold']
        enable_color_fallback = self.current_config['enable_color_fallback']

        try:
            # 增强图像中的火焰颜色特征 (用于提高检测率)
            enhanced_image = self._enhance_fire_colors(image)

            # 对原始图像和增强图像都执行推理
            # 使用列表以便处理多个结果对象 (例如，当模型分批处理时)
            yolo_results = []
            yolo_results.extend(self.model(image, conf=confidence_threshold, verbose=False))
            yolo_results.extend(self.model(enhanced_image, conf=confidence_threshold, verbose=False))

            for r in yolo_results:
                if r is None or not hasattr(r, 'boxes') or r.boxes is None:
                    continue  # 跳过无效结果

                for box in r.boxes:
                    coordinates = box.xyxy[0].cpu().numpy().tolist()
                    class_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())

                    class_name = self.class_names.get(class_id, "unknown")

                    # 如果是通用模型，只保留火焰相关或烟雾相关的目标
                    if not self.is_fire_model:
                        if class_id not in self.fire_related_ids and \
                                'fire' not in class_name.lower() and 'flame' not in class_name.lower() and \
                                'smoke' not in class_name.lower():
                            continue  # 跳过不相关的检测

                    is_fire = class_id in self.fire_class_ids or 'fire' in class_name.lower() or 'flame' in class_name.lower()
                    is_smoke = class_id in self.smoke_class_ids or 'smoke' in class_name.lower()

                    center_x, center_y = (coordinates[0] + coordinates[2]) / 2, (coordinates[1] + coordinates[3]) / 2
                    box_area = (coordinates[2] - coordinates[0]) * (coordinates[3] - coordinates[1])

                    detection_type = "fire" if is_fire else "smoke" if is_smoke else "fire_related"

                    # 避免重复添加同一个检测结果，并保留置信度更高的
                    duplicate_found = False
                    for existing_res in processed_results:
                        existing_box = existing_res["coordinates"]
                        iou = self._calculate_iou(coordinates, existing_box)
                        if iou > iou_threshold:  # IoU 超过阈值认为是同一物体
                            duplicate_found = True
                            if confidence > existing_res["confidence"]:  # 保留置信度更高的
                                existing_res.update({
                                    "type": detection_type, "class_name": class_name,
                                    "confidence": round(confidence, 3),
                                    "coordinates": [round(c, 2) for c in coordinates],
                                    "center": [round(center_x, 2), round(center_y, 2)],
                                    "area": round(box_area, 2)
                                })
                            break

                    if not duplicate_found:
                        processed_results.append({
                            "type": detection_type, "class_name": class_name,
                            "confidence": round(confidence, 3),
                            "coordinates": [round(c, 2) for c in coordinates],
                            "center": [round(center_x, 2), round(center_y, 2)],
                            "area": round(box_area, 2)
                        })

            # 如果YOLO模型没有检测到结果，并且启用了颜色检测作为备用方案
            if not processed_results and enable_color_fallback and self._has_fire_colors(image):
                h, w = image.shape[:2]
                logger.info(f"YOLO未检测到，但颜色检测发现火焰迹象。")
                processed_results.append({
                    "type": "fire", "class_name": "fire_color_detected",
                    "confidence": 0.6,  # 中等置信度
                    "coordinates": [0, 0, w, h],  # 整个图像范围
                    "center": [w / 2, h / 2],
                    "area": w * h
                })

            return processed_results

        except Exception as e:
            logger.error(f"火焰烟雾检测过程中出错: {e}", exc_info=True)
            return []

    def _calculate_iou(self, box1: List[float], box2: List[float]) -> float:
        """计算两个边界框的IOU（交并比）"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        x_left = max(x1_1, x1_2)
        y_top = max(y1_1, y1_2)
        x_right = min(x2_1, x2_2)
        y_bottom = min(y2_1, y2_2)

        if x_right < x_left or y_bottom < y_top:
            return 0.0  # 无交集

        intersection_area = (x_right - x_left) * (y_bottom - y_top)

        box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
        box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)

        union_area = box1_area + box2_area - intersection_area

        return intersection_area / union_area if union_area > 0 else 0.0

    def _enhance_fire_colors(self, image: np.ndarray) -> np.ndarray:
        """增强图像中的火焰颜色特征，用于提高检测模型的灵敏度。"""
        try:
            enhanced = image.copy()
            enhanced = cv2.convertScaleAbs(enhanced, alpha=1.5, beta=10)  # 增强对比度
            gamma = 0.7  # 伽马校正
            lookup_table = np.array([((i / 255.0) ** gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
            enhanced = cv2.LUT(enhanced, lookup_table)
            return enhanced
        except Exception as e:
            logger.warning(f"增强图像失败: {e}", exc_info=True)
            return image

    def _has_fire_colors(self, image: np.ndarray) -> bool:
        """通过颜色分析检测图像中是否包含火焰相关的颜色。"""
        try:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

            # 定义火焰颜色范围（红色、橙色和黄色）
            lower_red1 = np.array([0, 70, 50]);
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([170, 70, 50]);
            upper_red2 = np.array([180, 255, 255])
            lower_orange = np.array([10, 100, 100]);
            upper_orange = np.array([25, 255, 255])
            lower_yellow = np.array([25, 100, 100]);
            upper_yellow = np.array([35, 255, 255])

            mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
            mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)
            mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)

            mask = mask_red1 + mask_red2 + mask_orange + mask_yellow

            # 腐蚀和膨胀消除噪点
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.erode(mask, kernel, iterations=1)
            mask = cv2.dilate(mask, kernel, iterations=2)

            coverage = cv2.countNonZero(mask) / (image.shape[0] * image.shape[1])

            return coverage > 0.1  # 如果火焰颜色覆盖比例超过10%，认为是火焰

        except Exception as e:
            logger.warning(f"颜色检测失败: {e}", exc_info=True)
            return False

