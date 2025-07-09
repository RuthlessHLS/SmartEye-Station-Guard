# ai_service/core/behavior_detection.py
import mediapipe as mp
import cv2
import numpy as np

# 初始化MediaPipe Pose解决方案
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils


class BehaviorDetector:
    def __init__(self):
        """
        初始化行为检测器，主要用于跌倒检测。
        """
        # 实例化姿态估计模型
        # min_detection_confidence: 检测置信度阈值
        # min_tracking_confidence: 跟踪置信度阈值
        self.pose_estimator = mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        print("Behavior Detector (Pose Estimation) model loaded successfully.")

    def detect_fall(self, image_np):
        """
        在单帧图像中检测是否有人跌倒。

        Args:
            image_np (np.ndarray): 输入的图像，格式为NumPy数组 (OpenCV BGR格式)。

        Returns:
            tuple: (检测结果列表, 绘制了骨骼的图像)
                   结果列表中的每个元素是一个字典，包含 'status' 和 'location'。
        """
        # MediaPipe需要RGB格式的图像，而OpenCV默认是BGR
        image_rgb = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)

        # 使用姿态估计模型进行处理
        results = self.pose_estimator.process(image_rgb)

        detection_results = []

        # 在图像上绘制骨骼
        annotated_image = image_np.copy()
        if results.pose_landmarks:
            mp_drawing.draw_landmarks(
                annotated_image,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                connection_drawing_spec=mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2)
            )

            # --- 跌倒判断核心逻辑 ---
            landmarks = results.pose_landmarks.landmark

            # 获取臀部关键点 (hip) 的y坐标
            # MediaPipe的坐标是归一化的(0.0到1.0)，所以乘以图像高度得到像素坐标
            h, w, _ = image_np.shape
            hip_y = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y * h

            # 获取脚踝关键点 (ankle) 的y坐标
            left_ankle_y = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y * h
            right_ankle_y = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y * h
            # 取两个脚踝中位置更低的那个
            ankle_y = max(left_ankle_y, right_ankle_y)

            # 简单的跌倒判断规则：
            # 如果臀部的位置非常接近脚踝的位置（垂直距离很小），我们认为可能发生了跌倒
            is_fallen = (ankle_y - hip_y) < 50  # 阈值50像素，可以根据实际情况调整

            status = "fallen" if is_fallen else "normal"

            # 计算人体的边界框
            x_coords = [lm.x * w for lm in landmarks]
            y_coords = [lm.y * h for lm in landmarks]
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)

            detection_results.append({
                "status": status,
                "location": {
                    "x": round(x_min),
                    "y": round(y_min),
                    "w": round(x_max - x_min),
                    "h": round(y_max - y_min)
                }
            })

        return detection_results, annotated_image

    def close(self):
        """
        释放模型资源。
        """
        self.pose_estimator.close()