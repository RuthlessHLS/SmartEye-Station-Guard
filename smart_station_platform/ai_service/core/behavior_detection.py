# 文件: ai_service/core/behavior_detection.py
# 描述: 行为检测器，用于分析目标的姿态和动作。

import numpy as np
from typing import List, Dict, Tuple, Optional
import cv2
import os
import time


class BehaviorDetector:
    def __init__(self):
        """
        初始化行为检测器。
        加载OpenPose模型用于姿态估计和跌倒检测。
        """
        print("行为检测器初始化中...")
        self.previous_states = {}  # 用于存储每个追踪目标上一帧的状态
        self.initialize_pose_model()
        
    def initialize_pose_model(self):
        """初始化OpenPose模型或替代姿态估计模型"""
        try:
            # 尝试初始化OpenPose模型
            # 路径应与init_detectors中使用的资源路径一致
            ASSET_BASE_PATH = os.getenv("G_DRIVE_ASSET_PATH", ".")
            model_path = os.path.join(ASSET_BASE_PATH, "models", "pose")
            
            # 检查OpenCV DNN模块和模型文件
            if not os.path.exists(os.path.join(model_path, "pose_iter_440000.caffemodel")):
                print("⚠️ 未找到OpenPose模型文件，将使用基于边界框的替代方法进行跌倒检测。")
                self.pose_model = None
                self.use_pose_estimation = False
                return
                
            # 初始化OpenPose模型
            self.pose_proto = os.path.join(model_path, "openpose_pose_coco.prototxt")
            self.pose_model_path = os.path.join(model_path, "pose_iter_440000.caffemodel")
            self.pose_net = cv2.dnn.readNetFromCaffe(self.pose_proto, self.pose_model_path)
            
            # 配置模型参数
            self.n_points = 18  # COCO模型的关键点数量
            self.POSE_PAIRS = [[1, 0], [1, 2], [1, 5], [2, 3], [3, 4], [5, 6], [6, 7],
                              [1, 8], [8, 9], [9, 10], [1, 11], [11, 12], [12, 13],
                              [0, 14], [0, 15], [14, 16], [15, 17]]
            
            self.use_pose_estimation = True
            print("✅ 姿态估计模型加载成功")
            
        except Exception as e:
            print(f"⚠️ 姿态估计模型初始化失败: {e}")
            print("将使用基于边界框的替代方法进行跌倒检测")
            self.pose_model = None
            self.use_pose_estimation = False

    def detect_behavior(self, frame: np.ndarray, person_boxes: List[List[float]], current_time: float = None) -> List[Dict]:
        """
        对检测到的人员进行行为分析。

        Args:
            frame (np.ndarray): 当前的视频帧。
            person_boxes (List[List[float]]): 一个包含多个人边界框的列表，
                                              每个边界框格式为 [x1, y1, x2, y2]。
            current_time (float, optional): 当前时间戳，用于时序分析。

        Returns:
            List[Dict]: 一个包含每个被分析人员行为结果的字典列表。
        """
        if current_time is None:
            current_time = time.time()
            
        detected_behaviors = []

        for i, box in enumerate(person_boxes):
            x1, y1, x2, y2 = map(int, box)
            
            # 跟踪ID (简化方式)
            person_id = f"person_{i}"
            
            # 提取人物区域进行分析
            person_roi = frame[max(0, y1):min(frame.shape[0], y2), 
                              max(0, x1):min(frame.shape[1], x2)]
            
            # 如果ROI太小，跳过
            if person_roi.size == 0 or person_roi.shape[0] < 10 or person_roi.shape[1] < 10:
                continue

            # 使用姿态估计或边界框方法检测跌倒
            if self.use_pose_estimation:
                is_fallen = self.detect_fall_by_pose(person_roi, person_id, current_time)
            else:
                is_fallen = self.detect_fall_by_bbox_ratio(x1, y1, x2, y2)

            if is_fallen:
                detected_behaviors.append({
                    "person_id": person_id,
                    "box": [x1, y1, x2, y2],
                    "behavior": "fall_down",
                    "is_abnormal": True,
                    "need_alert": True,  # 跌倒需要立即告警
                    "confidence": 0.85  # 置信度
                })
            else:
                # 如果没摔倒，就认为在活动
                detected_behaviors.append({
                    "person_id": person_id,
                    "box": [x1, y1, x2, y2],
                    "behavior": "active",  # 正常活动
                    "is_abnormal": False,
                    "need_alert": False,
                    "confidence": 0.7
                })

        return detected_behaviors

    def detect_fall_by_bbox_ratio(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """
        使用边界框高宽比检测跌倒
        
        Args:
            x1, y1, x2, y2: 边界框坐标
            
        Returns:
            bool: 是否检测到跌倒
        """
        # 计算边界框的宽度和高度
        box_w = x2 - x1
        box_h = y2 - y1
        
        # 避免除以零的错误
        if box_h == 0:
            return False
            
        # 计算高宽比
        aspect_ratio = box_w / box_h
        
        # 通常站立的人高宽比小于1 (例如 0.4-0.8)
        # 如果高宽比大于阈值，我们认为他可能摔倒了
        return aspect_ratio > 1.2

    def detect_fall_by_pose(self, person_img: np.ndarray, person_id: str, current_time: float) -> bool:
        """
        使用姿态估计检测跌倒
        
        Args:
            person_img: 人物区域图像
            person_id: 人物ID，用于跟踪
            current_time: 当前时间戳
            
        Returns:
            bool: 是否检测到跌倒
        """
        try:
            # 图像预处理
            img_height, img_width, _ = person_img.shape
            input_blob = cv2.dnn.blobFromImage(person_img, 1.0 / 255, (368, 368), 
                                             (0, 0, 0), swapRB=False, crop=False)
            
            # 推理
            self.pose_net.setInput(input_blob)
            output = self.pose_net.forward()
            
            # 解析关键点
            keypoints = []
            for i in range(self.n_points):
                # 置信度图
                prob_map = output[0, i, :, :]
                prob_map = cv2.resize(prob_map, (img_width, img_height))
                
                # 找到最大置信度点
                _, confidence, _, point = cv2.minMaxLoc(prob_map)
                
                # 如果置信度大于阈值，记录该点
                if confidence > 0.1:
                    keypoints.append((point[0], point[1], confidence))
                else:
                    keypoints.append(None)
            
            # 分析姿态判断是否跌倒
            return self.analyze_pose_for_fall(keypoints, person_id, current_time)
            
        except Exception as e:
            print(f"姿态估计出错: {e}")
            # 出错时使用边界框方法作为后备
            return self.detect_fall_by_bbox_ratio(*self.get_person_bbox(person_img))
    
    def get_person_bbox(self, img: np.ndarray) -> Tuple[int, int, int, int]:
        """
        获取图像中的人物边界框
        """
        return 0, 0, img.shape[1], img.shape[0]
    
    def analyze_pose_for_fall(self, keypoints: List[Optional[Tuple]], person_id: str, current_time: float) -> bool:
        """
        分析人体姿态判断是否跌倒
        
        Args:
            keypoints: 检测到的关键点列表
            person_id: 人物ID
            current_time: 当前时间戳
            
        Returns:
            bool: 是否检测到跌倒
        """
        # 如果关键点不足，无法判断
        valid_points = [p for p in keypoints if p is not None]
        if len(valid_points) < 5:  # 需要足够多的关键点来判断
            return False
        
        # 提取关键身体部位 (COCO模型关键点索引)
        # 0:鼻子 1:颈部 2:右肩 3:右肘 4:右手 5:左肩 6:左肘 7:左手 
        # 8:右臀 9:右膝 10:右脚 11:左臀 12:左膝 13:左脚 14:右眼 15:左眼 16:右耳 17:左耳
        
        # 获取头部和脚部的位置
        head_points = [keypoints[0], keypoints[14], keypoints[15], keypoints[16], keypoints[17]]
        valid_head = [p for p in head_points if p is not None]
        
        foot_points = [keypoints[10], keypoints[13]]
        valid_foot = [p for p in foot_points if p is not None]
        
        # 如果头部或脚部关键点不可见，使用其他方法判断
        if not valid_head or not valid_foot:
            # 使用边界框方法作为后备
            if person_id in self.previous_states:
                prev_state = self.previous_states[person_id]
                # 如果前一帧是跌倒状态，保持该状态以避免闪烁
                if "is_fallen" in prev_state and prev_state["is_fallen"]:
                    return True
            return False
        
        # 计算头部中心点
        head_center = (sum(p[0] for p in valid_head) / len(valid_head), 
                      sum(p[1] for p in valid_head) / len(valid_head))
        
        # 计算脚部中心点
        foot_center = (sum(p[0] for p in valid_foot) / len(valid_foot),
                      sum(p[1] for p in valid_foot) / len(valid_foot))
        
        # 计算头部与脚部的高度差和水平差
        height_diff = abs(foot_center[1] - head_center[1])
        horizontal_diff = abs(foot_center[0] - head_center[0])
        
        # 如果水平差大于高度差，可能是跌倒状态
        is_fallen = horizontal_diff > height_diff * 0.8
        
        # 记录当前状态，用于下一帧的判断
        self.previous_states[person_id] = {
            "timestamp": current_time,
            "is_fallen": is_fallen,
            "head_pos": head_center,
            "foot_pos": foot_center
        }
        
        return is_fallen