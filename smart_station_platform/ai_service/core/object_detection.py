# core/object_detection.py (修改后的最终版本)

import torch
import torchvision
from torchvision.transforms import functional as F
import numpy as np
from typing import List, Dict


class GenericPredictor:
    """
    一个通用的目标检测器，使用预训练的 Faster R-CNN 模型。
    这个版本被修改为强制从本地文件路径加载模型权重。
    """

    def __init__(self, model_weights_path: str, num_classes: int, class_names: List[str]):
        """
        初始化检测器。

        参数:
            model_weights_path (str): 指向 .pth 模型权重文件的完整路径。
            num_classes (int): 数据集中的类别数量 (包括背景)。
            class_names (List[str]): 按索引排序的类别名称列表。
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"通用目标检测器正在使用设备: {self.device}")

        self.class_names = class_names

        # --- 【核心修改】 ---
        # 1. 加载模型结构，但不加载预训练权重 (pretrained=False)
        #    我们使用原始的COCO类别数(91)来初始化，以匹配我们下载的权重文件结构。
        # 新代码 (最终修复版)
        self.model = torchvision.models.detection.fasterrcnn_resnet50_fpn(weights=None, weights_backbone=None,
                                                                          num_classes=91)

        # 2. 从我们指定的本地 G 盘路径加载权重
        print(f"INFO: 正在从本地路径强制加载模型权重: {model_weights_path}")
        try:
            # 加载权重文件，并确保它被映射到正确的设备 (CPU 或 CUDA)
            self.model.load_state_dict(torch.load(model_weights_path, map_location=self.device))
            print("INFO: 成功从本地文件加载模型权重。")
        except Exception as e:
            print(f"FATAL: 从 '{model_weights_path}' 加载模型权重失败: {e}")
            raise

        # 3. 将模型转移到目标设备并设置为评估模式
        self.model.to(self.device)
        self.model.eval()
        # --------------------

    def predict(self, frame: np.ndarray, confidence_threshold: float = 0.5) -> List[Dict]:
        """
        对单个图像帧进行目标检测。

        参数:
            frame (np.ndarray): OpenCV BGR 格式的图像。
            confidence_threshold (float): 用于过滤检测结果的置信度阈值。

        返回:
            一个字典列表，每个字典包含一个检测到的对象信息。
            例如: [{'class_name': 'person', 'confidence': 0.98, 'coordinates': [x1, y1, x2, y2]}]
        """
        # 1. 图像预处理
        image_tensor = F.to_tensor(frame).to(self.device)
        image_tensor = image_tensor.unsqueeze(0)  # 添加 batch 维度

        # 2. 模型推理
        with torch.no_grad():
            predictions = self.model(image_tensor)

        # 3. 解析并格式化结果
        results = []
        # predictions[0] 包含 'boxes', 'labels', 'scores'
        for i in range(len(predictions[0]['scores'])):
            score = predictions[0]['scores'][i].item()
            if score > confidence_threshold:
                box = predictions[0]['boxes'][i].cpu().numpy().astype(int)
                label_index = predictions[0]['labels'][i].item()

                # 确保标签索引在 class_names 列表范围内
                class_name = self.class_names[label_index] if 0 <= label_index < len(self.class_names) else 'Unknown'

                results.append({
                    "class_name": class_name,
                    "confidence": score,
                    "coordinates": box.tolist()  # [x_min, y_min, x_max, y_max]
                })

        return results