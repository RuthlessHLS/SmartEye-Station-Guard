# 文件: ai_service/core/object_detection.py

import torch
from torchvision.transforms import functional as F
from PIL import Image
from torchvision.ops import nms
import numpy as np
import cv2

# 从我们刚创建的文件中导入模型定义函数
from .ai_models.detector_model import get_model

class GenericPredictor:
    def __init__(self, model_weights_path, num_classes, class_names):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.class_names = class_names
        print(f"通用目标检测器正在使用设备: {self.device}")
        self.model = get_model(num_classes=num_classes)
        try:
            state_dict = torch.load(model_weights_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
        except FileNotFoundError:
            print(f"错误: 找不到模型权重文件 at '{model_weights_path}'。")
            raise
        self.model.to(self.device)
        self.model.eval()

    def predict(self, frame: np.ndarray, confidence_threshold=0.5, nms_iou_threshold=0.3):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(frame_rgb)
        img_tensor = F.to_tensor(img_pil).unsqueeze(0).to(self.device)
        with torch.no_grad():
            predictions = self.model(img_tensor)
        pred = predictions[0]
        keep_indices = pred['scores'] > confidence_threshold
        boxes, scores, labels = pred['boxes'][keep_indices], pred['scores'][keep_indices], pred['labels'][keep_indices]
        nms_indices = nms(boxes, scores, nms_iou_threshold)
        final_boxes = boxes[nms_indices].cpu().numpy()
        final_scores = scores[nms_indices].cpu().numpy()
        final_labels = labels[nms_indices].cpu().numpy()
        results = []
        for box, score, label_id in zip(final_boxes, final_scores, final_labels):
            if int(label_id) < len(self.class_names):
                results.append({
                    "class_id": int(label_id),
                    "class_name": self.class_names[int(label_id)],
                    "confidence": float(score),
                    "coordinates": [round(c, 2) for c in box.tolist()]
                })
        return results