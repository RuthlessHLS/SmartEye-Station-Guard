# 文件: ai_service/core/face_recognition.py
# 描述: 人脸识别器，用于检测、编码和识别人脸。

import face_recognition
import numpy as np
import os
import cv2
from typing import List, Dict


class FaceRecognizer:
    def __init__(self, known_faces_dir: str):
        """
        初始化人脸识别器。

        Args:
            known_faces_dir (str): 存放已知人员照片的目录路径。
                                   目录下每个子目录代表一个人，子目录名即为人员姓名，
                                   子目录内可以放一张或多张该人员的照片。
        """
        print("正在初始化人脸识别器...")
        self.known_faces_dir = known_faces_dir
        self.known_face_encodings = []
        self.known_face_names = []

        # 在初始化时，从指定目录加载所有已知人脸
        self.load_known_faces()

    def load_known_faces(self):
        """
        从目录加载所有已知人脸并进行编码。
        """
        print(f"正在从 '{self.known_faces_dir}' 目录加载已知人脸...")
        if not os.path.exists(self.known_faces_dir):
            print(f"警告: 已知人脸目录不存在，将创建一个空目录: {self.known_faces_dir}")
            os.makedirs(self.known_faces_dir)
            return

        for person_name in os.listdir(self.known_faces_dir):
            person_dir = os.path.join(self.known_faces_dir, person_name)
            if os.path.isdir(person_dir):
                for filename in os.listdir(person_dir):
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                        image_path = os.path.join(person_dir, filename)
                        try:
                            # 加载图片并获取人脸编码
                            face_image = face_recognition.load_image_file(image_path)
                            # 假设每张照片里只有一张脸，我们取第一个找到的编码
                            face_encodings = face_recognition.face_encodings(face_image)
                            if face_encodings:
                                self.known_face_encodings.append(face_encodings[0])
                                self.known_face_names.append(person_name)
                                print(f"  - 成功加载人脸: {person_name}")
                        except Exception as e:
                            print(f"处理图片 {image_path} 时出错: {e}")

    def detect_and_recognize(self, frame: np.ndarray, tolerance=0.5) -> List[Dict]:
        """
        在单帧图像中检测并识别人脸。

        Args:
            frame (np.ndarray): BGR格式的视频帧。
            tolerance (float): 人脸比对的容忍度，值越小比对越严格。

        Returns:
            List[Dict]: 一个包含检测到的所有人脸信息的字典列表。
        """
        # 为了提高性能，可以将图像缩小
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        # 将图像从BGR转换为RGB（face_recognition库需要）
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # 1. 在当前帧中找到所有人脸的位置和编码
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        recognized_faces = []
        for face_encoding, face_location in zip(face_encodings, face_locations):
            # 2. 将当前找到的人脸与所有已知人脸进行比对
            matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=tolerance)

            name = "Unknown"  # 默认为未知人员
            confidence = 0.0

            # 3. 如果有匹配项，找到最佳匹配
            if True in matches:
                face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    name = self.known_face_names[best_match_index]
                    # 将距离转换为一个模拟的置信度 (1 - 距离)
                    confidence = 1 - face_distances[best_match_index]

            # 将坐标恢复到原始图像尺寸
            top, right, bottom, left = face_location
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            recognized_faces.append({
                "identity": name,
                "confidence": confidence,
                "box": [left, top, right, bottom]
            })

        return recognized_faces