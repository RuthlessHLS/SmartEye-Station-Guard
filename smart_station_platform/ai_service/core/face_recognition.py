# 文件: ai_service/core/face_recognition.py
# 描述: 智能人脸识别器，用于检测、编码和识别人脸，支持动态灵敏度配置和新面孔注册。

import os
import time
import logging
from collections import deque, defaultdict
import numpy as np
import cv2
import dlib
import face_recognition
from PIL import Image
import tempfile
# --- 新增导入 ---
from skimage.feature import local_binary_pattern
from .anti_spoofing_predictor import AntiSpoofingPredictor

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

        # --- 初始化深度学习反欺骗检测器 ---
        try:
            anti_spoof_model_path = os.path.join(
                asset_base_path, "models", "anti_spoof", "4_0_0_80x80_MiniFASNetV1.pth"
            )
            if os.path.exists(anti_spoof_model_path):
                self.spoof_detector = AntiSpoofingPredictor(anti_spoof_model_path)
                logger.info("成功加载深度学习反欺骗模型。")
            else:
                self.spoof_detector = None
                logger.warning(f"未找到反欺骗模型 at '{anti_spoof_model_path}'，深度学习活体检测功能已禁用。")
        except Exception as e:
            self.spoof_detector = None
            logger.error(f"加载深度学习反欺骗模型失败: {e}", exc_info=True)


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
        """
        扫描目录，加载所有已知人脸的特征编码。
        通过聚合每个人的多个样本来创建一个更鲁棒的“平均脸”特征。
        """
        self.known_face_encodings = []
        self.known_face_names = []
        encodings_by_person = defaultdict(list)

        logger.info(f"开始从 '{self.known_faces_dir}' 加载并聚合人脸特征...")
        if not os.path.isdir(self.known_faces_dir):
            logger.warning(f"已知人脸目录 '{self.known_faces_dir}' 不存在，跳过加载。")
            return

        # 步骤 1: 收集每个人的所有特征编码
        # 现在，目录名直接就是用户名
        for username in os.listdir(self.known_faces_dir):
            person_dir = os.path.join(self.known_faces_dir, username)
            if os.path.isdir(person_dir):
                for filename in os.listdir(person_dir):
                    if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                        continue

                    image_path = os.path.join(person_dir, filename)
                    cache_path = os.path.splitext(image_path)[0] + ".npy"

                    try:
                        encoding = None
                        if os.path.exists(cache_path) and os.path.getmtime(cache_path) >= os.path.getmtime(image_path):
                            encoding = np.load(cache_path)
                        else:
                            logger.info(f"为 '{username}' 的图片 '{filename}' 计算新特征...")
                            image = face_recognition.load_image_file(image_path)
                            face_encodings_list = face_recognition.face_encodings(image)
                            if face_encodings_list:
                                encoding = face_encodings_list[0]
                                np.save(cache_path, encoding)
                                logger.info(f"为 '{username}' 创建了新的特征缓存: {os.path.basename(cache_path)}")
                            else:
                                logger.warning(f"在图片 {image_path} 中未找到人脸，跳过。")
                                continue
                        
                        if encoding is not None:
                            encodings_by_person[username].append(encoding)

                    except Exception as e:
                        logger.error(f"处理图片 {image_path} 时发生错误: {e}")
        
        # 步骤 2: 为每个人计算平均特征向量
        if not encodings_by_person:
            logger.warning("未找到任何可加载的人脸特征。")
            return
            
        for name, encodings in encodings_by_person.items():
            if not encodings:
                continue
            
            # 计算平均值
            average_encoding = np.mean(encodings, axis=0)
            self.known_face_encodings.append(average_encoding)
            self.known_face_names.append(name)
            logger.info(f"为用户 '{name}' 聚合了 {len(encodings)} 个样本，生成了一个平均特征。")

        logger.info(f"加载并聚合完成。共找到 {len(self.known_face_names)} 个注册用户。")

    def reload_known_faces(self):
        """重新加载所有已知人脸数据。"""
        logger.info("正在重新加载所有已知人脸数据...")
        self._load_known_faces()
        logger.info("人脸数据重新加载完成。")

    def register_new_face(self, username, image_bytes):
        """注册一张新的人脸，并为其创建特征缓存。"""
        person_dir = os.path.join(self.known_faces_dir, username)
        os.makedirs(person_dir, exist_ok=True)

        try:
            image = face_recognition.load_image_file(image_bytes)
            encodings = face_recognition.face_encodings(image)

            if not encodings:
                return {"success": False, "message": "未检测到人脸或图片质量不佳"}

            encoding = encodings[0]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            # 使用Pillow保存图片以确保格式正确
            image_path = os.path.join(person_dir, f"reg_{timestamp}.jpg")
            pil_image = Image.open(image_bytes)
            pil_image.save(image_path, "JPEG")

            # 保存特征缓存
            cache_path = os.path.splitext(image_path)[0] + ".npy"
            np.save(cache_path, encoding)

            self.known_face_encodings.append(encoding)
            self.known_face_names.append(username)
            
            logger.info(f"成功注册人脸 '{username}'，特征已缓存至 {os.path.basename(cache_path)}。")
            return {"success": True, "message": f"成功注册 {username}", "person_id": username}

        except Exception as e:
            logger.error(f"注册人脸 '{username}' 时发生错误: {e}", exc_info=True)
            return {"success": False, "message": f"服务器错误: {e}"}

    def add_face(self, image: np.ndarray, person_name: str) -> bool:
        """
        添加一张新的人脸图像到数据库中，并更新模型。
        这是对 register_new_face 的一个更底层的封装。

        Args:
            image (np.ndarray): 从cv2读取的图像.
            person_name (str): 与人脸关联的姓名或ID.

        Returns:
            bool: 如果成功添加，返回 True，否则 False.
        """
        person_dir = os.path.join(self.known_faces_dir, person_name)
        os.makedirs(person_dir, exist_ok=True)

        try:
            # 检查图像中是否能找到人脸
            face_locations = face_recognition.face_locations(image, model=self.detection_model)
            if not face_locations:
                logger.warning(f"为 '{person_name}' 添加人脸失败：图像中未检测到人脸。")
                return False

            # 使用找到的第一个人脸进行编码
            face_encodings = face_recognition.face_encodings(image, known_face_locations=face_locations)
            if not face_encodings:
                logger.warning(f"为 '{person_name}' 添加人脸失败：无法对检测到的人脸进行编码。")
                return False
            
            encoding = face_encodings[0]

            # 保存图像文件和特征文件
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            image_filename = f"reg_{timestamp}.jpg"
            image_path = os.path.join(person_dir, image_filename)
            
            # 将 numpy 数组转为 PIL Image 以便保存
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            pil_image.save(image_path, "JPEG")

            cache_path = os.path.splitext(image_path)[0] + ".npy"
            np.save(cache_path, encoding)

            # 动态更新内存中的模型
            self._load_known_faces()
            
            logger.info(f"成功为 '{person_name}' 添加新的人脸图像并更新模型。")
            return True

        except Exception as e:
            logger.error(f"为 '{person_name}' 添加人脸时发生错误: {e}", exc_info=True)
            return False

    def _assess_face_quality(self, frame):
        """
        评估单帧图像中的人脸质量。
        返回一个质量分数和检测到的人脸数据。分数越高，质量越好。
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 1. 检测人脸
        face_locations = face_recognition.face_locations(frame, model=self.detection_model)
        if len(face_locations) != 1:
            return 0, None, "图中必须有且仅有一张人脸"

        (top, right, bottom, left) = face_locations[0]
        face_image = frame[top:bottom, left:right]

        # 2. 清晰度评估 (拉普拉斯方差)
        laplacian_var = cv2.Laplacian(cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        
        # 3. 姿态评估
        landmarks, head_pose = self.get_landmarks_and_pose(frame)
        if head_pose is None:
            return 0, None, "无法检测到头部姿态"
        
        roll, pitch, yaw = head_pose
        
        # 姿态分数：越接近正面，分数越高
        # 过滤掉角度过大的图像
        if abs(pitch) > 25 or abs(yaw) > 25 or abs(roll) > 25:
             return 0, None, f"头部姿态不佳 (pitch: {pitch:.2f}, yaw: {yaw:.2f}, roll: {roll:.2f})"
        
        pose_score = (1 - abs(pitch) / 90.0) + (1 - abs(yaw) / 90.0) + (1 - abs(roll) / 90.0)

        # 综合分数
        quality_score = laplacian_var * pose_score
        
        # 检查是否满足最低要求
        if laplacian_var < 40:  # 阈值可调，过滤掉非常模糊的图像
            return 0, None, f"图像过于模糊 (清晰度: {laplacian_var:.2f})"

        return quality_score, frame, "质量合格"

    def register_from_video(self, username, video_bytes, num_faces_to_select=5, frame_interval=5):
        """
        从视频流中提取所有人脸特征并聚合，生成一个鲁棒的平均特征用于注册。
        """
        logger.info(f"开始从视频为用户 '{username}' 进行聚合注册...")
        
        person_dir = os.path.join(self.known_faces_dir, username)
        os.makedirs(person_dir, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(video_bytes)
            video_path = tmp.name

        collected_encodings = []
        last_good_frame = None
        try:
            cap = cv2.VideoCapture(video_path)
            frame_count = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_count % frame_interval == 0:
                    # 使用CNN模型检测帧中的所有人脸
                    face_locations = face_recognition.face_locations(frame, model='cnn')
                    if face_locations:
                        # 提取该帧中所有人脸的特征
                        face_encodings = face_recognition.face_encodings(frame, face_locations)
                        if face_encodings:
                            collected_encodings.extend(face_encodings)
                            last_good_frame = frame  # 保存最后一帧有效图像用于存档
                            logger.debug(f"在帧 {frame_count} 找到 {len(face_encodings)} 个有效人脸特征。")
                
                frame_count += 1
        finally:
            if 'cap' in locals() and cap.isOpened():
                cap.release()
            os.unlink(video_path)

        if not collected_encodings:
            logger.warning(f"视频处理完成，但未能从任何帧中提取到有效的人脸特征。")
            return {"success": False, "message": "视频中未能检测到任何人脸，请检查光线和摄像头角度。"}

        # --- 核心逻辑：计算所有特征的平均值 ---
        average_encoding = np.mean(collected_encodings, axis=0)
        logger.info(f"成功为 '{username}' 聚合了 {len(collected_encodings)} 个特征，生成了平均脸。正在保存...")

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            image_filename = f"agg_reg_{timestamp}.jpg"
            image_path = os.path.join(person_dir, image_filename)
            
            # 保存最后一张检测到人脸的帧作为代表图像
            if last_good_frame is not None:
                cv2.imwrite(image_path, last_good_frame)
            
            # 保存聚合后的平均特征
            cache_path = os.path.splitext(image_path)[0] + ".npy"
            np.save(cache_path, average_encoding)
            
            logger.info(f"已保存 '{username}' 的聚合人脸特征到 {os.path.basename(cache_path)}")
        except Exception as e:
            logger.error(f"保存用户 '{username}' 的聚合特征时出错: {e}", exc_info=True)
            return {"success": False, "message": "保存人脸数据时发生服务器错误。"}

        # 重新加载模型以包含新注册的用户
        self.reload_known_faces()

        return {
            "success": True, 
            "message": f"成功通过聚合 {len(collected_encodings)} 个特征点注册了 {username}。", 
            "person_id": username
        }

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

    def _calculate_ear(self, eye):
        """计算单只眼睛的纵横比(EAR)"""
        # 计算两组垂直眼标志（x，y）坐标之间的欧氏距离
        A = np.linalg.norm(eye[1] - eye[5])
        B = np.linalg.norm(eye[2] - eye[4])
        # 计算水平眼标志（x，y）坐标之间的欧氏距离
        C = np.linalg.norm(eye[0] - eye[3])
        # 计算眼睛的纵横比
        ear = (A + B) / (2.0 * C)
        return ear

    def get_eye_aspect_ratios(self, landmarks):
        """
        从面部关键点中计算双眼的EAR值。
        :param landmarks: 68个面部关键点的Numpy数组。
        :return: (left_ear, right_ear) 元组，失败则返回 (None, None)。
        """
        if landmarks is None or landmarks.shape[0] != 68:
            return None, None
        
        try:
            # 提取左右眼的关键点索引
            (lStart, lEnd) = (36, 42)
            (rStart, rEnd) = (42, 48)
            
            leftEye = landmarks[lStart:lEnd]
            rightEye = landmarks[rStart:rEnd]
            
            left_ear = self._calculate_ear(leftEye)
            right_ear = self._calculate_ear(rightEye)
            
            return left_ear, right_ear
        except Exception as e:
            logger.error(f"计算EAR时出错: {e}")
            return None, None

    def get_mouth_aspect_ratio(self, landmarks):
        """
        从面部关键点中计算嘴巴的纵横比(MAR)。
        :param landmarks: 68个面部关键点的Numpy数组。
        :return: MAR值，失败则返回 None。
        """
        if landmarks is None or landmarks.shape[0] != 68:
            return None
        
        try:
            # 提取嘴巴的关键点
            mouth = landmarks[60:68]
            
            # 计算嘴巴垂直方向的距离
            A = np.linalg.norm(mouth[2] - mouth[6]) # 上下唇中心
            B = np.linalg.norm(mouth[3] - mouth[5])
            
            # 计算嘴巴水平方向的距离
            C = np.linalg.norm(mouth[0] - mouth[4]) # 嘴角
            
            mar = (A + B) / (2.0 * C)
            return mar
        except Exception as e:
            logger.error(f"计算MAR时出错: {e}")
            return None

    def verify_head_shake(self, yaw_sequence, threshold=15, min_shakes=2):
        """
        验证头部是否完成摇头动作。
        :param yaw_sequence: 一系列的头部偏航角(yaw)值。
        :param threshold: 判定位移的宽松角度阈值。
        :param min_shakes: 至少需要完成的摇头次数。
        """
        if len(yaw_sequence) < 5: return False
        
        directions = [] # 1 for right, -1 for left
        for i in range(1, len(yaw_sequence)):
            if yaw_sequence[i] - yaw_sequence[i-1] > threshold / 2:
                if not directions or directions[-1] != 1: directions.append(1)
            elif yaw_sequence[i] - yaw_sequence[i-1] < -threshold / 2:
                if not directions or directions[-1] != -1: directions.append(-1)
        
        # 宽松判定：只要有来回摆动即可
        return len(directions) >= min_shakes

    def verify_head_nod(self, pitch_sequence, threshold=10, min_nods=2):
        """
        验证头部是否完成点头动作。
        :param pitch_sequence: 一系列的头部俯仰角(pitch)值。
        :param threshold: 判定位移的宽松角度阈值。
        :param min_nods: 至少需要完成的点头次数。
        """
        if len(pitch_sequence) < 5: return False
        
        directions = [] # 1 for down, -1 for up
        for i in range(1, len(pitch_sequence)):
            if pitch_sequence[i] - pitch_sequence[i-1] > threshold / 2:
                if not directions or directions[-1] != 1: directions.append(1)
            elif pitch_sequence[i] - pitch_sequence[i-1] < -threshold / 2:
                if not directions or directions[-1] != -1: directions.append(-1)
        
        # 宽松判定：只要有上下摆动即可
        return len(directions) >= min_nods

    def detect_screen_replay(self, frame, face_location=None):
        """
        通过检测摩尔纹来分析图像是否为屏幕重放攻击。
        :param frame: 完整的视频帧.
        :param face_location: (可选) 已知的人脸位置 (top, right, bottom, left).
        :return: True 如果检测到可疑的屏幕纹理, 否则 False.
        """
        if face_location:
            (top, right, bottom, left) = face_location
        else:
            locations = face_recognition.face_locations(frame, model='hog')
            if len(locations) != 1:
                return False 
            (top, right, bottom, left) = locations[0]
            
        face_image = frame[top:bottom, left:right]

        if face_image.size == 0:
            return False

        gray_face = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        
        # 执行快速傅里叶变换
        f = np.fft.fft2(gray_face)
        fshift = np.fft.fftshift(f)
        magnitude_spectrum = np.log(1 + np.abs(fshift))

        # 遮罩中心区域的低频成分
        rows, cols = gray_face.shape
        crow, ccol = rows // 2 , cols // 2
        mask_radius = int(min(rows, cols) * 0.1)
        cv2.circle(magnitude_spectrum, (ccol, crow), mask_radius, 0, -1)

        # 通过计算频谱峰值与均值的比率来判断是否存在异常高频信号（摩尔纹）
        mean_spectrum_val = np.mean(magnitude_spectrum[magnitude_spectrum > 0])
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(magnitude_spectrum)
        
        peak_to_mean_ratio = max_val / mean_spectrum_val if mean_spectrum_val > 0 else 0
        
        # 设定一个宽松的比率阈值，高于此值则可能为屏幕翻拍
        ratio_threshold = 2.5 
        
        if peak_to_mean_ratio > ratio_threshold:
            logger.warning(
                f"检测到潜在的屏幕重放攻击（摩尔纹）。"
                f"频谱峰值与均值比: {peak_to_mean_ratio:.2f} (阈值: {ratio_threshold})"
            )
            return True
            
        return False

    def _is_print_attack(self, face_image: np.ndarray, min_std_dev=18.0) -> bool:
        """
        通过分析人脸区域的纹理来检测打印攻击（照片攻击）。
        真实人脸的纹理比打印照片更复杂。

        Args:
            face_image (np.ndarray): 裁剪出的人脸区域图像 (BGR格式)。
            min_std_dev (float): LBP直方图的标准差阈值，低于此值可能为攻击。

        Returns:
            bool: 如果怀疑是打印攻击，返回 True，否则 False。
        """
        if face_image is None or face_image.size == 0:
            return False

        # 1. 转换为灰度图
        gray_face = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        
        # 2. 计算LBP特征
        # 'uniform' 方法对于旋转和灰度变化具有不变性
        radius = 1
        n_points = 8 * radius
        lbp = local_binary_pattern(gray_face, n_points, radius, method='uniform')
        
        # 3. 计算LBP直方图
        (hist, _) = np.histogram(lbp.ravel(),
                                 bins=np.arange(0, n_points + 3),
                                 range=(0, n_points + 2))
        
        # 4. 归一化直方图
        hist = hist.astype("float")
        hist /= (hist.sum() + 1e-6)
        
        # 5. 分析直方图的标准差
        # 打印照片的纹理通常更均匀，导致LBP直方图的标准差较低
        std_dev = np.std(hist)
        
        logger.debug(f"[打印攻击检测] LBP直方图标准差: {std_dev:.4f} (阈值: > {min_std_dev})")

        # 如果标准差低于阈值，则有可能是打印攻击
        return std_dev < min_std_dev

    def detect_and_recognize(self, frame, detection_model='hog', tolerance=0.55, enable_liveness: bool = True):
        """
        在单帧图像中检测、识别所有人脸，并进行活体检测判断。
        这是一个增强版本，整合了照片攻击检测。
        """
        # 使用self.detection_model作为默认值，但允许API覆盖
        model_to_use = self.detection_model if detection_model is None else detection_model

        face_locations = face_recognition.face_locations(frame, model=model_to_use)
        face_encodings = face_recognition.face_encodings(frame, face_locations)

        recognized_faces = []

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            face_image_crop = frame[top:bottom, left:right]
            
            # --- 核心安全增强：打印攻击检测 ---
            if self._is_print_attack(face_image_crop):
                logger.warning(f"检测到潜在的打印照片攻击 at [{top},{left},{bottom},{right}]。拒绝识别。")
                recognized_faces.append({
                    "location": {"top": top, "right": right, "bottom": bottom, "left": left},
                    "bbox": [left, top, right, bottom],
                    "identity": {"name": "Spoof Attack", "is_known": False, "should_alert": True, "attack_type": "print"},
                    "confidence": 1.0 # 对于攻击检测，我们可以非常有信心
                })
                continue # 检测到攻击，跳过后续识别步骤

            # --- 核心安全增强：深度学习活体检测 ---
            if self.spoof_detector and enable_liveness:
                is_real, real_confidence = self.spoof_detector.predict(face_image_crop)
                logger.debug(f"深度学习活体检测结果: is_real={is_real}, confidence={real_confidence:.4f}")
                if not is_real:
                    logger.warning(f"检测到潜在的AI换脸/视频攻击 at [{top},{left},{bottom},{right}]。拒绝识别。")
                    recognized_faces.append({
                        "location": {"top": top, "right": right, "bottom": bottom, "left": left},
                        "bbox": [left, top, right, bottom],
                        "identity": {"name": "Spoof Attack", "is_known": False, "should_alert": True, "attack_type": "deepfake_or_video"},
                        "confidence": 1.0 - real_confidence
                    })
                    continue # 检测到攻击，跳过后续识别步骤

            # --- 标准人脸识别流程 ---
            matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=tolerance)
            face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
            
            best_match_index = -1
            if True in matches:
                best_match_index = np.argmin(face_distances)

            identity_info = {"name": "unknown", "is_known": False, "should_alert": False, "confidence": 0.0}

            if best_match_index != -1:
                name = self.known_face_names[best_match_index]
                confidence = 1 - face_distances[best_match_index]
                identity_info = {"name": name, "is_known": True, "should_alert": False, "confidence": confidence}
            else:
                # 即使是未知人脸，也估算一个“置信度”
                if len(face_distances) > 0:
                    min_dist = np.min(face_distances)
                    # 将距离转换为一个0-1之间的“不像”程度，再反转
                    confidence = max(0, 1 - (min_dist - tolerance) / (1.0 - tolerance))
                    # 低于一定置信度的陌生人需要告警
                    if 0.1 < confidence < 0.4:
                         identity_info["should_alert"] = True
                else: # 如果数据库为空
                    confidence = 0.0
                
                identity_info["confidence"] = confidence

            recognized_faces.append({
                "location": {"top": top, "right": right, "bottom": bottom, "left": left},
                "bbox": [left, top, right, bottom],
                "identity": identity_info
            })

        return recognized_faces

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