# ai_service/core/fire_smoke_detection.py

import os
import cv2
import numpy as np
import time
from ultralytics import YOLO
from typing import List, Dict, Union, Optional
import torch


class FlameSmokeDetector:
    """
    火焰与烟雾检测器，使用YOLOv8模型实现实时检测。
    具备以下功能：
    - 检测图像中的火焰和烟雾
    - 支持视频流检测
    - 提供置信度和位置信息
    """
    
    def __init__(self, model_path=None, device=None):
        """
        初始化火焰烟雾检测器。

        Args:
            model_path (str): YOLOv8模型权重文件的路径 (.pt)。
                            如果为None，将尝试使用默认路径。
            device (str): 使用的设备，可以是'cpu'或'cuda:0'等，
                         为None时自动选择可用设备。
        """
        # 设置默认设备
        if device is None:
            self.device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        # 设置默认模型路径
        if model_path is None:
            # 尝试从环境变量获取资源路径
            asset_base_path = os.getenv("G_DRIVE_ASSET_PATH")
            if asset_base_path:
                model_path = os.path.join(asset_base_path, "models", "torch", "yolov8n.pt")
            else:
                # 如果没有设置环境变量，使用默认路径
                model_path = "yolov8n.pt"
                
            # 检查模型文件是否存在
            if not os.path.exists(model_path):
                print(f"警告: 未找到模型文件 {model_path}，尝试使用内置的YOLOv8n模型")
                model_path = "yolov8n"  # 使用ultralytics内置的模型
        
        # 1. 加载YOLOv8模型
        try:
            self.model = YOLO(model_path)
            # 将模型移至指定设备
            self.model.to(self.device)
            
            # 获取模型的类别名称
            self.class_names = self.model.names
            
            # 确定模型类型
            if any(name.lower() in ['fire', 'flame', 'smoke'] for name in self.class_names.values()):
                self.is_fire_model = True
                print("已加载专用火焰/烟雾检测模型")
            else:
                self.is_fire_model = False
                print("已加载通用检测模型，将使用通用目标检测")
                
            print(f"火焰烟雾检测模型加载成功。使用设备: {self.device}")
            print(f"模型类别: {self.class_names}")
            
            # 保存模型中的火焰和烟雾类别ID
            self.fire_class_ids = [k for k, v in self.class_names.items() 
                                 if any(term in v.lower() for term in ['fire', 'flame'])]
            self.smoke_class_ids = [k for k, v in self.class_names.items() 
                                  if 'smoke' in v.lower()]
            
            print(f"火焰类别ID: {self.fire_class_ids}")
            print(f"烟雾类别ID: {self.smoke_class_ids}")
            
            # 添加一些火灾相关物体的类别ID（针对通用模型）
            # 扩大火灾相关物体范围，增加检测率
            self.fire_related_objects = [
                'oven', 'stove', 'candle', 'lighter', 'match', 'torch', 'campfire',
                'hot dog', 'pizza', 'cake', 'wine glass', 'cup', 'bowl', 'bottle',
                'microwave', 'refrigerator', 'toaster', 'sink', 'cell phone', 'laptop',
                'tv', 'remote', 'hair drier', 'toothbrush', 'clock', 'vase', 'scissors',
                'teddy bear', 'tie', 'suitcase', 'frisbee', 'sports ball', 'kite'
            ]
            self.fire_related_ids = []
            if not self.is_fire_model:
                for k, v in self.class_names.items():
                    if any(obj in v.lower() for obj in self.fire_related_objects):
                        self.fire_related_ids.append(k)
                print(f"火灾相关物体类别ID: {self.fire_related_ids}")
            
        except Exception as e:
            self.model = None
            print(f"火焰烟雾检测模型加载失败: {e}")
    
    def detect(self, image, confidence_threshold=0.15):  # 进一步降低默认置信度阈值
        """
        对图像进行火焰和烟雾检测。

        Args:
            image: 输入图像，可以是图像路径或numpy数组。
            confidence_threshold (float): 置信度阈值。

        Returns:
            list: 包含检测结果字典的列表。
        """
        if self.model is None:
            print("火焰烟雾检测模型未加载，尝试使用颜色检测法。")
            if self._has_fire_colors(image):
                # 获取图像尺寸
                h, w = image.shape[:2]
                # 创建覆盖整个图像的边界框
                print("🔥 使用颜色检测成功识别到火焰")
                return [{
                    "type": "fire_detection",  # 修改为前端期望的类型
                    "detection_type": "fire",  # 添加子类型
                    "class_name": "fire_color_detected",
                    "confidence": 0.7,  # 提高颜色检测的置信度
                    "coordinates": [0, 0, w, h],
                    "center": [w/2, h/2],
                    "area": w*h
                }]
            return []

        try:
            # 检查是否需要进行颜色预处理（针对手机屏幕上的火焰图像）
            enhanced_image = self._enhance_fire_colors(image)
            
            # 2. 对原始图像和增强图像都执行推理
            print(f"执行火焰检测，使用置信度阈值: {confidence_threshold}")
            results_original = self.model(image, conf=confidence_threshold, verbose=False)
            results_enhanced = self.model(enhanced_image, conf=confidence_threshold, verbose=False)

            
            # 合并两个结果
            processed_results = []
            
            # 处理原始图像的结果
            for r in results_original:
                boxes = r.boxes

                for box in boxes:
                    # 获取边界框坐标 [x1, y1, x2, y2]
                    coordinates = box.xyxy[0].cpu().numpy().tolist()
                    # 获取类别ID和置信度
                    class_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())
                    
                    # 获取类别名称
                    class_name = self.class_names.get(class_id, "unknown")
                    
                    # 【修复】移除过于频繁的日志打印
                    # print(f"检测到目标 - 类别: {class_name}, 置信度: {confidence:.3f}, 坐标: {coordinates}")
                    
                    # 如果使用通用模型，仅保留火焰相关目标
                    if not self.is_fire_model:
                        # 如果不是预定义的火灾相关物体，跳过
                        is_fire_or_smoke = (class_id in self.fire_class_ids or
                                            class_id in self.smoke_class_ids or
                                            any(term in class_name.lower() for term in ['fire', 'flame', 'smoke']))
                        if not is_fire_or_smoke:
                            # 【修复】静默跳过，不再打印日志
                            # print(f"跳过非火灾/烟雾目标: {class_name}")
                            continue
                    
                    # 确定是火焰还是烟雾
                    is_fire = class_id in self.fire_class_ids or 'fire' in class_name.lower() or 'flame' in class_name.lower()
                    is_smoke = class_id in self.smoke_class_ids or 'smoke' in class_name.lower()
                    
                    # 计算边界框中心点
                    x1, y1, x2, y2 = coordinates
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    
                    # 计算边界框面积
                    box_area = (x2 - x1) * (y2 - y1)
                    
                    detection_type = "fire" if is_fire else "smoke" if is_smoke else "fire_related"
                    print(f"确定检测类型: {detection_type}")
                    
                    # 避免重复添加同一个检测结果
                    duplicate = False
                    for result in processed_results:
                        # 计算IOU
                        iou = self._calculate_iou(coordinates, result["coordinates"])
                        if iou > 0.5:  # 如果IOU大于0.5，认为是同一个目标
                            duplicate = True
                            # 保留置信度更高的
                            if confidence > result["confidence"]:
                                result.update({
                                    "type": "fire_detection",  # 修改为前端期望的类型
                                    "detection_type": detection_type,  # 添加子类型
                                    "class_name": class_name,
                                    "confidence": confidence,
                                    "coordinates": coordinates,
                                    "center": [center_x, center_y],
                                    "area": box_area
                                })
                            break
                    
                    if not duplicate:
                        processed_results.append({
                            "type": "fire_detection",  # 修改为前端期望的类型
                            "detection_type": detection_type,  # 添加子类型
                            "class_name": class_name,
                            "confidence": confidence,
                            "coordinates": coordinates,
                            "center": [center_x, center_y],
                            "area": box_area
                        })
                        print(f"添加新的检测结果: {class_name}, 类型: fire_detection, 子类型: {detection_type}")
            
            # 处理增强图像的结果
            for r in results_enhanced:
                boxes = r.boxes

                for box in boxes:
                    # 获取边界框坐标 [x1, y1, x2, y2]
                    coordinates = box.xyxy[0].cpu().numpy().tolist()
                    # 获取类别ID和置信度
                    class_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())
                    
                    # 获取类别名称
                    class_name = self.class_names.get(class_id, "unknown")
                    
                    # 如果使用通用模型，仅保留火焰相关目标
                    if not self.is_fire_model:
                        is_fire_or_smoke = (class_id in self.fire_class_ids or
                                            class_id in self.smoke_class_ids or
                                            any(term in class_name.lower() for term in ['fire', 'flame', 'smoke']))
                        if not is_fire_or_smoke:
                            continue
                    
                    # 确定是火焰还是烟雾
                    is_fire = class_id in self.fire_class_ids or 'fire' in class_name.lower() or 'flame' in class_name.lower()
                    is_smoke = class_id in self.smoke_class_ids or 'smoke' in class_name.lower()
                    
                    # 计算边界框中心点
                    x1, y1, x2, y2 = coordinates
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    
                    # 计算边界框面积
                    box_area = (x2 - x1) * (y2 - y1)
                    
                    detection_type = "fire" if is_fire else "smoke" if is_smoke else "fire_related"
                    
                    # 避免重复添加同一个检测结果
                    duplicate = False
                    for result in processed_results:
                        # 计算IOU
                        iou = self._calculate_iou(coordinates, result["coordinates"])
                        if iou > 0.5:  # 如果IOU大于0.5，认为是同一个目标
                            duplicate = True
                            # 保留置信度更高的
                            if confidence > result["confidence"]:
                                result.update({
                                    "type": "fire_detection",  # 修改为前端期望的类型
                                    "detection_type": detection_type,  # 添加子类型
                                    "class_name": class_name,
                                    "confidence": confidence,
                                    "coordinates": coordinates,
                                    "center": [center_x, center_y],
                                    "area": box_area
                                })
                            break
                    
                    if not duplicate:
                        processed_results.append({
                            "type": "fire_detection",  # 修改为前端期望的类型
                            "detection_type": detection_type,  # 添加子类型
                            "class_name": class_name,
                            "confidence": confidence,
                            "coordinates": coordinates,
                            "center": [center_x, center_y],
                            "area": box_area
                        })
            
            print(f"🔥 火焰检测完成，返回 {len(processed_results)} 个结果")
            for i, res in enumerate(processed_results):
                print(f"  结果 {i+1}: 类型={res['type']}, 子类型={res['detection_type']}, 置信度={res['confidence']:.3f}")
            
            return processed_results
        except Exception as e:
            print(f"火焰检测过程中出错: {e}")
            return []
    
    def _calculate_iou(self, box1, box2):
        """计算两个边界框的IoU（交并比）"""
        # 计算交集区域
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        # 计算交集面积
        if x2 < x1 or y2 < y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        
        # 计算两个框的面积
        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
        
        # 计算并集面积
        union = box1_area + box2_area - intersection
        
        # 返回IoU
        return intersection / union if union > 0 else 0.0
    
    def _enhance_fire_colors(self, image):
        """增强图像中的火焰颜色，提高检测率"""
        # 复制原始图像
        enhanced = image.copy()
        
        # 转换为HSV颜色空间
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # 提取红色、橙色和黄色区域（火焰颜色）
        # 红色在HSV中有两个范围
        lower_red1 = np.array([0, 70, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 70, 50])
        upper_red2 = np.array([180, 255, 255])
        
        # 橙色和黄色
        lower_orange = np.array([10, 100, 100])
        upper_orange = np.array([25, 255, 255])
        
        # 创建掩码
        mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)
        
        # 合并掩码
        mask = mask_red1 + mask_red2 + mask_orange
        
        # 在掩码区域增强亮度和对比度
        enhanced[mask > 0] = np.clip(enhanced[mask > 0] * 1.3, 0, 255).astype(np.uint8)
        
        return enhanced
    
    def _has_fire_colors(self, image):
        """检查图像中是否有火焰颜色（用于颜色检测法）"""
        # 转换为HSV颜色空间
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # 定义火焰颜色范围（红色、橙色和黄色）
        # 红色在HSV中有两个范围（低端和高端）
        lower_red1 = np.array([0, 70, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 70, 50])
        upper_red2 = np.array([180, 255, 255])
        
        # 橙色范围
        lower_orange = np.array([10, 100, 100])
        upper_orange = np.array([25, 255, 255])
        
        # 黄色范围
        lower_yellow = np.array([25, 100, 100])
        upper_yellow = np.array([35, 255, 255])
        
        # 创建掩码
        mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)
        mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
        
        # 合并掩码
        mask = mask_red1 + mask_red2 + mask_orange + mask_yellow
        
        # 对掩码应用腐蚀和膨胀以消除噪点
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        # 计算掩码覆盖的像素比例
        coverage = cv2.countNonZero(mask) / (image.shape[0] * image.shape[1])
        
        # 如果火焰颜色覆盖率超过5%，则认为存在火焰
        # 降低阈值以提高检测率
        return coverage > 0.05  
    
    def process_video_frame(self, frame, confidence_threshold=0.25, draw_result=True):
        """
        处理视频帧，进行火焰和烟雾检测。

        Args:
            frame: 输入视频帧。
            confidence_threshold (float): 置信度阈值。
            draw_result (bool): 是否在帧上绘制检测结果。

        Returns:
            tuple: (处理后的帧, 检测结果列表)
        """
        # 复制原始帧
        result_frame = frame.copy() if draw_result else None
        
        # 进行检测
        detections = self.detect(frame, confidence_threshold)
        
        # 如果需要绘制结果
        if draw_result and detections:
            for det in detections:
                # 获取坐标
                x1, y1, x2, y2 = det["coordinates"]
                
                # 根据检测类型设置颜色
                if det["detection_type"] == "fire":
                    color = (0, 0, 255)  # 红色表示火焰
                elif det["detection_type"] == "smoke":
                    color = (128, 128, 128)  # 灰色表示烟雾
                else:
                    color = (0, 165, 255)  # 橙色表示火灾相关物体
                
                # 绘制边界框
                cv2.rectangle(result_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                
                # 绘制标签
                label = f"{det['class_name']} {det['confidence']:.2f}"
                cv2.putText(result_frame, label, (int(x1), int(y1) - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return result_frame, detections


# 为了与其他检测器兼容，添加一个别名
FireDetector = FlameSmokeDetector

