# core/object_detection.py (YOLOv8版本)

import torch
import numpy as np
from typing import List, Dict
from ultralytics import YOLO
import os


class GenericPredictor:
    """
    使用YOLOv8的通用目标检测器。
    相比Faster R-CNN，具有更好的性能和更快的速度。
    """

    def __init__(self, model_weights_path: str, num_classes: int, class_names: List[str]):
        """
        初始化YOLOv8检测器。

        参数:
            model_weights_path (str): 指向模型权重文件的完整路径
            num_classes (int): 类别数量（包括背景）
            class_names (List[str]): 类别名称列表
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"通用目标检测器正在使用设备: {self.device}")

        self.class_names = class_names

        # 加载YOLOv8模型
        try:
            # 首先尝试加载指定的权重文件
            if os.path.exists(model_weights_path):
                print(f"INFO: 正在从本地路径加载YOLOv8模型: {model_weights_path}")
                self.model = YOLO(model_weights_path)
            else:
                # 如果本地文件不存在，使用预训练的yolov8n.pt
                print("WARNING: 本地权重文件不存在，使用预训练的YOLOv8n模型")
                self.model = YOLO('yolov8n.pt')
            
            # 将模型移动到指定设备
            self.model.to(self.device)
            print("INFO: 成功加载YOLOv8模型")
        except Exception as e:
            print(f"FATAL: 加载YOLOv8模型失败: {e}")
            raise

    def predict(self, frame: np.ndarray, confidence_threshold: float = 0.3) -> List[Dict]:
        """
        使用YOLOv8对单个图像帧进行目标检测。

        参数:
            frame (np.ndarray): OpenCV BGR格式的图像
            confidence_threshold (float): 基础置信度阈值，YOLOv8默认为0.3

        返回:
            检测结果列表，每个结果包含类别名称、置信度和坐标
        """
        # 设置特定类别的更高置信度要求
        high_confidence_classes = {
            'bicycle': 0.45,
            'sports ball': 0.45,
            'carrot': 0.50,
            'cell phone': 0.45,
            'book': 0.45
        }

        # 获取图像尺寸
        img_height, img_width = frame.shape[:2]
        img_area = img_height * img_width

        try:
            # 使用YOLOv8进行预测
            results = self.model(frame, verbose=False)

            # 解析结果
            detections = []
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    # 获取类别索引和名称
                    cls_id = int(box.cls[0].item())
                    class_name = self.class_names[cls_id] if cls_id < len(self.class_names) else 'unknown'
                    
                    # 获取置信度
                    confidence = box.conf[0].item()
                    
                    # 获取边界框坐标
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    
                    # 获取该类别的置信度阈值
                    class_threshold = high_confidence_classes.get(class_name, confidence_threshold)
                    
                    if confidence > class_threshold:
                        # 计算检测框面积和宽高比
                        box_width = x2 - x1
                        box_height = y2 - y1
                        box_area = box_width * box_height
                        aspect_ratio = max(box_width / box_height, box_height / box_width)
                        
                        # 过滤条件：
                        # 1. 框面积不能过大（超过图像的80%）
                        # 2. 宽高比不能过于极端（超过5:1）
                        if box_area / img_area <= 0.8 and aspect_ratio <= 5:
                            detections.append({
                    "class_name": class_name,
                                "confidence": confidence,
                                "coordinates": [x1, y1, x2, y2]
                })

            return detections

        except Exception as e:
            print(f"ERROR: YOLOv8预测过程出错: {e}")
            return []