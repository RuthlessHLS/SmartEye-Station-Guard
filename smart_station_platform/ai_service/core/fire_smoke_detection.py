# ai_service/core/fire_smoke_detection.py

import os
import sys
import torch
import logging
import numpy as np
import cv2

# 【核心修复】将包含YOLOv5自定义模型的目录添加到sys.path
# 这解决了 'No module named models.yolo' 的问题
fire_model_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'fire'))
if fire_model_dir not in sys.path:
    sys.path.insert(0, fire_model_dir)

# 【核心修复】不再使用 ultralytics.YOLO，而是导入项目内的YOLOv5加载逻辑
from models.yolo import Model
from utils.general import non_max_suppression
from utils.torch_utils import select_device

logger = logging.getLogger(__name__)


class FlameSmokeDetector:
    """
    基于YOLOv5的火焰和烟雾检测器。
    这个版本经过了重构，以使用正确的YOLOv5模型加载逻辑。
    """
    
    def __init__(self, assets_path, img_size=640):
        """
        Initializes the YOLOv5 based flame and smoke detector.
        """
        self.img_size = img_size
        self.model_path = os.path.join(assets_path, "models", "torch", "best.pt")
        self.device = select_device('' if torch.cuda.is_available() else 'cpu')
        
        try:
            # 【核心修复】使用YOLOv5的加载方式,并设置 weights_only=False 以兼容新版PyTorch
            self.model = torch.load(self.model_path, map_location=self.device, weights_only=False)['model'].float().fuse().eval()
            self.class_names = self.model.names if hasattr(self.model, 'names') else [f'class_{i}' for i in range(100)]
            
            logger.info(f"成功加载YOLOv5火焰烟雾检测模型 from {self.model_path} on {self.device}")
            logger.info(f"模型类别: {self.class_names}")

        except Exception as e:
            logger.error(f"火焰烟雾检测模型加载失败: {e}", exc_info=True)
            self.model = None
            raise e
    
    def detect(self, img0, confidence_threshold=0.25, iou_threshold=0.45):
        if self.model is None:
            logger.warning("火焰烟雾检测模型未加载，跳过检测。")
            return []

        # Padded resize
        img = self.letterbox(img0, new_shape=self.img_size)[0]
        # Convert
        img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB, to 3x416x416
        img = np.ascontiguousarray(img)

        img = torch.from_numpy(img).to(self.device)
        img = img.float()
        img /= 255.0  # 0 - 255 to 0.0 - 1.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)

        # Inference
        pred = self.model(img)[0]

        # Apply NMS
        pred = non_max_suppression(pred, confidence_threshold, iou_threshold, classes=None, agnostic=False)
        
        detections = []
        for i, det in enumerate(pred):  # detections per image
            # 【修复】添加 det is not None 的检查，防止在没有检测到任何物体时出错
            if det is not None and len(det):
                # Rescale boxes from img_size to im0 size
                det[:, :4] = self.scale_coords(img.shape[2:], det[:, :4], img0.shape).round()

                # Write results
                for *xyxy, conf, cls in reversed(det):
                    class_id = int(cls)
                    class_name = self.class_names[class_id]
                    
                    is_fire = 'fire' in class_name.lower() or 'flame' in class_name.lower()
                    is_smoke = 'smoke' in class_name.lower()
                    
                    if not is_fire and not is_smoke:
                        continue

                    detections.append({
                        "type": "fire_detection",
                        "detection_type": "fire" if is_fire else "smoke",
                        "class_name": class_name,
                        "confidence": float(conf),
                        "coordinates": [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])],
                        "center": [int((xyxy[0] + xyxy[2]) / 2), int((xyxy[1] + xyxy[3]) / 2)],
                        "area": int((xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1]))
                    })
        return detections

    def letterbox(self, img, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleFill=False, scaleup=True):
        shape = img.shape[:2]  # current shape [height, width]
        if isinstance(new_shape, int):
            new_shape = (new_shape, new_shape)

        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
        if not scaleup:
            r = min(r, 1.0)

        ratio = r, r
        new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
        if auto:
            dw, dh = np.mod(dw, 64), np.mod(dh, 64)
        elif scaleFill:
            dw, dh = 0.0, 0.0
            new_unpad = (new_shape[1], new_shape[0])
            ratio = new_shape[1] / shape[1], new_shape[0] / shape[0]

        dw /= 2
        dh /= 2

        if shape[::-1] != new_unpad:
            img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
        return img, ratio, (dw, dh)

    def scale_coords(self, img1_shape, coords, img0_shape, ratio_pad=None):
        if ratio_pad is None:
            gain = min(img1_shape[0] / img0_shape[0], img1_shape[1] / img0_shape[1])
            pad = (img1_shape[1] - img0_shape[1] * gain) / 2, (img1_shape[0] - img0_shape[0] * gain) / 2
        else:
            gain = ratio_pad[0][0]
            pad = ratio_pad[1]

        coords[:, [0, 2]] -= pad[0]
        coords[:, [1, 3]] -= pad[1]
        coords[:, :4] /= gain

        coords[:, 0].clamp_(0, img0_shape[1])
        coords[:, 1].clamp_(0, img0_shape[0])
        coords[:, 2].clamp_(0, img0_shape[1])
        coords[:, 3].clamp_(0, img0_shape[0])
        return coords


# 为了与其他检测器兼容，添加一个别名
FireDetector = FlameSmokeDetector

