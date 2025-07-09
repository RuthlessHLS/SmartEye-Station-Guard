# ai_service/core/object_detection.py

import torch
from torchvision.transforms import functional as F
from PIL import Image
from torchvision.ops import nms

# 从我们刚创建的文件中导入模型定义函数
# 注意这里的相对导入路径 '.'
from .ai_models.detector_model import get_model


class GenericPredictor:
    def __init__(self, model_weights_path, num_classes, class_names):
        """
        初始化通用预测器。
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.class_names = class_names
        print(f"Object Detector using device: {self.device}")

        # 1. 实例化模型结构
        self.model = get_model(num_classes=num_classes)

        # 2. 加载模型权重
        state_dict = torch.load(model_weights_path, map_location=self.device)
        self.model.load_state_dict(state_dict)

        self.model.to(self.device)
        self.model.eval()

    def predict(self, image_path, confidence_threshold=0.5, nms_iou_threshold=0.3):
        """
        对单张图片进行预测，并进行完整的后处理。
        """
        img = Image.open(image_path).convert("RGB")
        img_tensor = F.to_tensor(img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            predictions = self.model(img_tensor)

        pred = predictions[0]

        # 按置信度过滤
        keep_indices = pred['scores'] > confidence_threshold
        boxes, scores, labels = pred['boxes'][keep_indices], pred['scores'][keep_indices], pred['labels'][keep_indices]

        # 应用NMS
        nms_indices = nms(boxes, scores, nms_iou_threshold)

        final_boxes = boxes[nms_indices].cpu().numpy()
        final_scores = scores[nms_indices].cpu().numpy()
        final_labels = labels[nms_indices].cpu().numpy()

        # 格式化输出
        results = []
        for box, score, label_id in zip(final_boxes, final_scores, final_labels):
            results.append({
                "class_id": int(label_id),
                "class_name": self.class_names[int(label_id)],
                "confidence": float(score),
                "coordinates": [round(c, 2) for c in box.tolist()]  # [x1, y1, x2, y2]
            })

        return results