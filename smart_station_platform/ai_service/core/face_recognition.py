# 文件: ai_service/core/face_recognition.py
# 描述: 智能人脸识别器，用于检测、编码和识别人脸，支持动态灵敏度配置和新面孔注册。

import os
import time
import logging
from collections import deque
import numpy as np
import cv2
import dlib
import face_recognition
from PIL import Image

logger = logging.getLogger(__name__)

# --- FaceRecognizer 类 ---
class FaceRecognizer:
    """
    智能人脸识别器，负责加载、注册、识别以及提供活体检测所需的面部数据。
    """
    def __init__(self, known_faces_dir, asset_base_path, tolerance=0.6, detection_model='hog'):
        self.known_faces_dir = known_faces_dir
        self.tolerance = tolerance
        self.detection_model = detection_model
        self.known_face_encodings = []
        self.known_face_names = []

        dlib_shape_predictor_path = os.path.join(
            asset_base_path, "models", "dlib", "shape_predictor_68_face_landmarks.dat"
        )

        # 初始化Dlib的面部检测器和关键点预测器
        try:
            self.dlib_detector = dlib.get_frontal_face_detector()
            self.dlib_predictor = dlib.shape_predictor(dlib_shape_predictor_path)
            logger.info(f"成功加载 Dlib shape predictor from {dlib_shape_predictor_path}")
        except Exception as e:
            logger.error(f"无法加载 Dlib shape predictor: {e}. 活体检测功能将受限。")
            self.dlib_detector = None
            self.dlib_predictor = None

        self._load_known_faces()

    def _load_known_faces(self):
        """扫描目录，加载所有已知人脸的特征编码。"""
        self.known_face_encodings = []
        self.known_face_names = []
        logger.info(f"正在从 '{self.known_faces_dir}' 加载已知人脸...")
        if not os.path.isdir(self.known_faces_dir):
            logger.warning(f"已知人脸目录 '{self.known_faces_dir}' 不存在，跳过加载。")
            return

        for name in os.listdir(self.known_faces_dir):
            person_dir = os.path.join(self.known_faces_dir, name)
            if os.path.isdir(person_dir):
                for filename in os.listdir(person_dir):
                    image_path = os.path.join(person_dir, filename)
                    try:
                        image = face_recognition.load_image_file(image_path)
                        encodings = face_recognition.face_encodings(image)
                        if encodings:
                            self.known_face_encodings.append(encodings[0])
                            self.known_face_names.append(name)
                    except Exception as e:
                        logger.warning(f"无法从 {image_path} 加载人脸: {e}")
        logger.info(f"加载完成。共找到 {len(self.known_face_encodings)} 个已注册人脸特征。")

    def reload_known_faces(self):
        """重新加载所有已知人脸数据。"""
        logger.info("正在重新加载所有已知人脸数据...")
        self._load_known_faces()
        logger.info("人脸数据重新加载完成。")

    def register_new_face(self, username, image_bytes):
        """注册一张新的人脸。"""
        person_dir = os.path.join(self.known_faces_dir, username)
        os.makedirs(person_dir, exist_ok=True)

        try:
            image = face_recognition.load_image_file(image_bytes)
            encodings = face_recognition.face_encodings(image)

            if not encodings:
                return {"success": False, "message": "未检测到人脸或图片质量不佳"}

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            image_path = os.path.join(person_dir, f"reg_{timestamp}.jpg")
            
            # 使用Pillow保存图片以确保格式正确
            pil_image = Image.open(image_bytes)
            pil_image.save(image_path, "JPEG")

            self.known_face_encodings.append(encodings[0])
            self.known_face_names.append(username)
            
            logger.info(f"成功注册人脸 '{username}'，特征已添加到内存数据库。")
            return {"success": True, "message": f"成功注册 {username}", "person_id": username}

        except Exception as e:
            logger.error(f"注册人脸 '{username}' 时发生错误: {e}", exc_info=True)
            return {"success": False, "message": f"服务器错误: {e}"}

    def recognize_in_frame(self, frame):
        """在单帧图像中识别人脸。"""
        face_locations = face_recognition.face_locations(frame, model=self.detection_model)
        face_encodings = face_recognition.face_encodings(frame, face_locations)

        results = []
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, self.tolerance)
            name = "Unknown"
            confidence = 0.0

            face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
            if len(face_distances) > 0:
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    name = self.known_face_names[best_match_index]
                    confidence = 1.0 - face_distances[best_match_index]

            results.append({
                "identity": name,
                    "confidence": confidence,
                "bbox": [left, top, right, bottom]
            })
        
        if not results:
            return None
        return max(results, key=lambda x: x['confidence'])

    def get_landmarks_and_pose(self, frame):
        """
        从单帧图像中提取面部关键点和头部姿态，供活体检测使用。
        """
        if not self.dlib_predictor or not self.dlib_detector:
            return None, None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        try:
            rects = self.dlib_detector(gray, 0)
        except Exception as e:
            logger.error(f"Dlib面部检测失败: {e}")
            return None, None

        if len(rects) > 0:
            rect = rects[0]
            try:
                shape = self.dlib_predictor(gray, rect)
                landmarks = np.array([[p.x, p.y] for p in shape.parts()])
                head_pose = self._estimate_head_pose(shape, frame.shape)
                return landmarks, head_pose
            except Exception as e:
                logger.error(f"Dlib关键点或姿态估计失败: {e}")
                return None, None
            
        return None, None

    def _estimate_head_pose(self, shape, frame_shape):
        """根据面部关键点估算头部的旋转角度 (roll, pitch, yaw)。"""
        model_points = np.array([
            (0.0, 0.0, 0.0),             # 鼻尖
            (0.0, -330.0, -65.0),        # 下巴
            (-225.0, 170.0, -135.0),     # 左眼左角
            (225.0, 170.0, -135.0),      # 右眼右角
            (-150.0, -150.0, -125.0),    # 左嘴角
            (150.0, -150.0, -125.0)      # 右嘴角
        ], dtype="double")

        image_points = np.array([
            (shape.part(30).x, shape.part(30).y), (shape.part(8).x, shape.part(8).y),
            (shape.part(36).x, shape.part(36).y), (shape.part(45).x, shape.part(45).y),
            (shape.part(48).x, shape.part(48).y), (shape.part(54).x, shape.part(54).y)
        ], dtype="double")

        focal_length = frame_shape[1]
        center = (frame_shape[1]/2, frame_shape[0]/2)
        camera_matrix = np.array(
            [[focal_length, 0, center[0]], [0, focal_length, center[1]], [0, 0, 1]], dtype="double"
        )
        
        dist_coeffs = np.zeros((4, 1))
        try:
            (success, rotation_vector, translation_vector) = cv2.solvePnP(
                model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
            )
            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
            sy = np.sqrt(rotation_matrix[0, 0]**2 + rotation_matrix[1, 0]**2)
            
            if sy >= 1e-6:
                x = np.arctan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
                y = np.arctan2(-rotation_matrix[2, 0], sy)
                z = np.arctan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
            else:
                x = np.arctan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
                y = np.arctan2(-rotation_matrix[2, 0], sy)
                z = 0
            return (np.degrees(x), np.degrees(y), np.degrees(z)) # (roll, pitch, yaw)
        except Exception as e:
            logger.error(f"头部姿态计算(solvePnP)失败: {e}")
            return None

# --- FaceVerificationSession 类 (旧版，保留以防万一，但不再被新流程使用) ---
class FaceVerificationSession:
    """管理单次人脸验证会话的状态（旧版，已废弃）。"""
    def __init__(self, timeout=7.0):
        self.start_time = time.time()
        self.timeout = timeout
        self.liveness_confirmed = False
        self.recognized_name = None

    def is_timed_out(self):
        return time.time() - self.start_time > self.timeout

    # 其他方法可以保留或删除，因为新流程不使用它们