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
        # 尝试找到模型文件
        if model_path is None:
            # 检查环境变量中的资源目录
            asset_base_path = os.getenv("G_DRIVE_ASSET_PATH")
            if asset_base_path and os.path.isdir(asset_base_path):
                # 检查专用火焰检测模型
                fire_model_path = os.path.join(asset_base_path, "models", "torch", "yolov8n-fire.pt")
                if os.path.exists(fire_model_path):
                    model_path = fire_model_path
                    print(f"使用专用火焰检测模型: {model_path}")
                else:
                    # 如果没有找到专用模型，使用通用YOLOv8模型
                    general_model_path = os.path.join(asset_base_path, "models", "torch", "yolov8n.pt")
                    if os.path.exists(general_model_path):
                        model_path = general_model_path
                        print(f"未找到专用火焰检测模型，使用通用YOLO模型: {model_path}")
                    else:
                        print(f"警告: 未找到任何可用的YOLO模型")
                        model_path = "yolov8n.pt"  # 将从Ultralytics下载
        
        # 自动检测设备
        if device is None:
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.device = device
        
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
            self.fire_related_objects = ['oven', 'stove', 'candle', 'lighter', 'match', 'torch', 'campfire']
            self.fire_related_ids = []
            if not self.is_fire_model:
                for k, v in self.class_names.items():
                    if any(obj in v.lower() for obj in self.fire_related_objects):
                        self.fire_related_ids.append(k)
                print(f"火灾相关物体类别ID: {self.fire_related_ids}")
            
        except Exception as e:
            self.model = None
            print(f"火焰烟雾检测模型加载失败: {e}")
    
    def detect(self, image, confidence_threshold=0.25):  # 降低默认置信度阈值
        """
        对图像进行火焰和烟雾检测。

        Args:
            image: 输入图像，可以是图像路径或numpy数组。
            confidence_threshold (float): 置信度阈值。

        Returns:
            list: 包含检测结果字典的列表。
        """
        if self.model is None:
            print("火焰烟雾检测模型未加载，跳过检测。")
            return []

        try:
            # 检查是否需要进行颜色预处理（针对手机屏幕上的火焰图像）
            enhanced_image = self._enhance_fire_colors(image)
            
            # 2. 对原始图像和增强图像都执行推理
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
                    
                    # 如果使用通用模型，仅保留火焰相关目标
                    if not self.is_fire_model:
                        # 如果不是预定义的火灾相关物体，跳过
                        if class_id not in self.fire_related_ids:
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
                    for res in processed_results:
                        # 如果边界框有大量重叠，认为是重复检测
                        existing_box = res["coordinates"]
                        iou = self._calculate_iou(coordinates, existing_box)
                        if iou > 0.5:  # IOU超过50%认为是同一个物体
                            duplicate = True
                            # 保留置信度更高的结果
                            if confidence > res["confidence"]:
                                res.update({
                                    "type": detection_type,
                                    "class_name": class_name,
                                    "confidence": round(confidence, 3),
                                    "coordinates": [round(c, 2) for c in coordinates],
                                    "center": [round(center_x, 2), round(center_y, 2)],
                                    "area": round(box_area, 2)
                                })
                            break
                    
                    if not duplicate:
                        processed_results.append({
                            "type": detection_type,
                            "class_name": class_name,
                            "confidence": round(confidence, 3),
                            "coordinates": [round(c, 2) for c in coordinates],
                            "center": [round(center_x, 2), round(center_y, 2)],
                            "area": round(box_area, 2)
                        })
            
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
                        # 如果不是预定义的火灾相关物体，跳过
                        if class_id not in self.fire_related_ids:
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
                    for res in processed_results:
                        # 如果边界框有大量重叠，认为是重复检测
                        existing_box = res["coordinates"]
                        iou = self._calculate_iou(coordinates, existing_box)
                        if iou > 0.5:  # IOU超过50%认为是同一个物体
                            duplicate = True
                            # 保留置信度更高的结果
                            if confidence > res["confidence"]:
                                res.update({
                                    "type": detection_type,
                                    "class_name": class_name,
                                    "confidence": round(confidence, 3),
                                    "coordinates": [round(c, 2) for c in coordinates],
                                    "center": [round(center_x, 2), round(center_y, 2)],
                                    "area": round(box_area, 2)
                                })
                            break
                    
                    if not duplicate:
                        processed_results.append({
                            "type": detection_type,
                            "class_name": class_name,
                            "confidence": round(confidence, 3),
                            "coordinates": [round(c, 2) for c in coordinates],
                            "center": [round(center_x, 2), round(center_y, 2)],
                            "area": round(box_area, 2)
                        })
            
            # 如果还是没有检测到结果，尝试使用颜色检测法
            if not processed_results and self._has_fire_colors(image):
                # 获取图像尺寸
                h, w = image.shape[:2]
                # 创建覆盖整个图像的边界框
                processed_results.append({
                    "type": "fire",
                    "class_name": "fire_color_detected",
                    "confidence": 0.6,  # 中等置信度
                    "coordinates": [0, 0, w, h],
                    "center": [w/2, h/2],
                    "area": w*h
                })
            
            return processed_results
            
        except Exception as e:
            print(f"火焰检测过程中出错: {e}")
            return []
    
    def _calculate_iou(self, box1, box2):
        """计算两个边界框的IOU（交并比）"""
        # 转换为左上角和右下角坐标
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        # 计算交集区域
        x_left = max(x1_1, x1_2)
        y_top = max(y1_1, y1_2)
        x_right = min(x2_1, x2_2)
        y_bottom = min(y2_1, y2_2)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        
        # 计算两个边界框的面积
        box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
        box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
        
        # 计算并集面积
        union_area = box1_area + box2_area - intersection_area
        
        # 返回IOU
        if union_area == 0:
            return 0.0
        return intersection_area / union_area
    
    def _enhance_fire_colors(self, image):
        """增强图像中的火焰颜色特征"""
        try:
            # 创建图像副本
            enhanced = image.copy()
            
            # 增强图像对比度
            enhanced = cv2.convertScaleAbs(enhanced, alpha=1.5, beta=10)
            
            # 应用伽马校正以增强亮度区域
            gamma = 0.7
            lookup_table = np.array([((i / 255.0) ** gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
            enhanced = cv2.LUT(enhanced, lookup_table)
            
            return enhanced
        except Exception as e:
            print(f"增强图像失败: {e}")
            return image
    
    def _has_fire_colors(self, image):
        """检测图像中是否包含火焰相关的颜色"""
        try:
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
            
            # 如果火焰颜色覆盖比例超过10%，认为是火焰
            return coverage > 0.1
            
        except Exception as e:
            print(f"颜色检测失败: {e}")
            return False
    
    def process_video_frame(self, frame, confidence_threshold=0.25, draw_result=False):  # 降低默认置信度阈值
        """
        处理视频帧，执行火焰和烟雾检测并可选择绘制结果。

        Args:
            frame (np.ndarray): BGR格式的视频帧。
            confidence_threshold (float): 置信度阈值。
            draw_result (bool): 是否在帧上绘制检测结果。

        Returns:
            tuple: (处理后的帧, 检测结果列表)
        """
        # 复制输入帧以避免修改原始数据
        output_frame = frame.copy() if draw_result else frame
        
        # 执行检测
        detections = self.detect(frame, confidence_threshold)
        
        # 如果需要，绘制检测结果
        if draw_result and detections:
            for det in detections:
                # 提取坐标和类型
                x1, y1, x2, y2 = det["coordinates"]
                det_type = det["type"]
                conf = det["confidence"]
                
                # 根据检测类型设置颜色
                if det_type == "fire":
                    color = (0, 0, 255)  # 红色代表火焰
                elif det_type == "smoke":
                    color = (128, 128, 128)  # 灰色代表烟雾
                else:
                    color = (0, 165, 255)  # 橙色代表火灾相关物体
                
                # 绘制边界框
                cv2.rectangle(output_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                
                # 绘制标签背景
                label = f"{det['class_name']} {conf:.2f}"
                text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(output_frame, 
                             (int(x1), int(y1) - text_size[1] - 5),
                             (int(x1) + text_size[0], int(y1)), 
                             color, -1)
                
                # 绘制标签文字
                cv2.putText(output_frame, label, (int(x1), int(y1) - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return output_frame, detections


# 为了与其他检测器兼容，添加一个别名
FireDetector = FlameSmokeDetector

