# ai_service/core/fire_smoke_detection.py

from ultralytics import YOLO


class FlameSmokeDetector:
    def __init__(self, model_path, device=None):
        """
        初始化火焰烟雾检测器。

        Args:
            model_path (str): YOLOv8模型权重文件的路径 (.pt)。
        """
        # 1. 加载YOLOv8模型
        #    ultralytics库会自动处理设备选择 (CPU/GPU)
        try:
            self.model = YOLO(model_path)
            # 获取模型的类别名称
            self.class_names = self.model.names
            print("Flame and Smoke detection model loaded successfully.")
            print(f"  - Model classes: {self.class_names}")
        except Exception as e:
            self.model = None
            print(f"Failed to load Flame and Smoke detection model: {e}")

    def detect(self, image_path, confidence_threshold=0.4):
        """
        对单张图片进行火焰和烟雾检测。

        Args:
            image_path (str): 输入图片的路径。
            confidence_threshold (float): 置信度阈值。

        Returns:
            list: 包含检测结果字典的列表。
        """
        if self.model is None:
            print("Flame/Smoke model not loaded, skipping detection.")
            return []

        # 2. 执行推理
        #    设置 stream=True 可以更高效地处理视频流，但对单图也适用
        results = self.model(image_path, conf=confidence_threshold, stream=True)

        processed_results = []
        # 3. 解析结果
        for r in results:
            boxes = r.boxes
            for box in boxes:
                # 获取边界框坐标 [x1, y1, x2, y2]
                coordinates = box.xyxy[0].tolist()
                # 获取类别ID和置信度
                class_id = int(box.cls)
                confidence = float(box.conf)

                processed_results.append({
                    "class_name": self.class_names.get(class_id, "unknown"),
                    "confidence": round(confidence, 3),
                    "coordinates": [round(c, 2) for c in coordinates]
                })

        return processed_results