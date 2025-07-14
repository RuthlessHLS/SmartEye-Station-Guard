# 文件: ai_service/core/face_recognition.py
# 描述: 智能人脸识别器，用于检测、编码和识别人脸，支持动态灵敏度配置和新面孔注册。

import face_recognition
import numpy as np
import os
import cv2
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime
import asyncio
# from concurrent.futures import ThreadPoolExecutor  # 【移除】不再需要线程池

# 获取logger实例
logger = logging.getLogger(__name__)

# 【移除】不再需要全局线程池
# _face_loading_thread_pool = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)

def _calculate_eye_aspect_ratio(eye_landmarks: List[Tuple[int, int]]) -> float:
    """
    计算单只眼睛的纵横比 (EAR - Eye Aspect Ratio)。
    这个值在眼睛睁开时较大，闭合时接近于0。
    """
    # 垂直距离
    v_dist1 = np.linalg.norm(np.array(eye_landmarks[1]) - np.array(eye_landmarks[5]))
    v_dist2 = np.linalg.norm(np.array(eye_landmarks[2]) - np.array(eye_landmarks[4]))
    # 水平距离
    h_dist = np.linalg.norm(np.array(eye_landmarks[0]) - np.array(eye_landmarks[3]))
    
    # 避免除以零
    if h_dist == 0:
        return 0.0
        
    ear = (v_dist1 + v_dist2) / (2.0 * h_dist)
    return ear

class FaceRecognizer:
    def __init__(self, known_faces_dir, detection_model="hog", tolerance=0.5, jitter=1):
        """
        初始化人脸识别器。

        Args:
            known_faces_dir (str): 包含已知人脸图片的目录路径。
                                目录结构应为：known_faces_dir/person_name/image_files
        """
        self.known_faces = {}  # 存储每个人的人脸编码 {name: [encodings]}
        self.enabled = True  # 控制检测器是否启用

        # 内部默认检测参数 (可被外部配置覆盖)
        self._default_config = {
            'tolerance': 0.65,  # 默认人脸比对容忍度
            'detection_model': 'auto',  # 默认人脸检测模型: 'hog', 'cnn', 'auto'
            'number_of_times_to_upsample': 2,  # 检测前对图像进行上采样次数
            'min_face_size': 40,  # 最小人脸尺寸 (像素)，小于此尺寸的人脸将被忽略
        }
        self.current_config = self._default_config.copy()  # 当前生效的配置

        self.known_faces_dir = known_faces_dir
        self.known_face_encodings = []
        self.known_face_names = []
        self.tolerance = tolerance
        self.jitter = jitter

        # 活体检测阈值
        self.EAR_THRESHOLD = 0.21  # 眨眼检测的EAR阈值
        self.HEAD_TURN_RATIO_THRESHOLD = 1.5  # 转头检测的鼻子-眼睛距离比率阈值

        self._load_known_faces()

    def _load_known_faces(self):
        """
        核心的加载函数：扫描目录，计算编码。这是一个耗时操作。
        """
        logger.info("=== 开始扫描人脸库并生成编码... ===")
        logger.info(f"目录路径: {self.known_faces_dir}")

        temp_encodings = []
        temp_names = []

        if not os.path.isdir(self.known_faces_dir):
            logger.warning(f"已知人脸目录 '{self.known_faces_dir}' 不存在，跳过加载。")
            return

        for person_name in os.listdir(self.known_faces_dir):
            person_dir = os.path.join(self.known_faces_dir, person_name)
            if not os.path.isdir(person_dir):
                continue
            
            for image_file in os.listdir(person_dir):
                if image_file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    try:
                        image_path = os.path.join(person_dir, image_file)
                        image = face_recognition.load_image_file(image_path)
                        encodings = face_recognition.face_encodings(image)
                        if encodings:
                            temp_encodings.append(encodings[0])
                            temp_names.append(person_name)
                        else:
                            logger.warning(f"在图片 '{image_file}' 中未找到人脸，已跳过。")
                    except Exception as e:
                        logger.error(f"处理图片 '{image_file}' 时出错: {e}", exc_info=True)
        
        # 原子替换，确保服务不会在加载过程中使用不完整的数据
        self.known_face_encodings = temp_encodings
        self.known_face_names = temp_names
        logger.info(f"✅ 人脸库加载完成。共加载 {len(self.known_face_encodings)} 个已知人脸。")

    async def reload_known_faces(self):
        """
        异步接口，在后台线程中安全地执行耗时的加载任务。
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_known_faces)

    def update_config(self, new_config: Dict[str, Any]):
        """
        更新人脸识别器的配置参数。
        Args:
            new_config (Dict[str, Any]): 包含要更新的配置项的字典。
        """
        for key, value in new_config.items():
            if key in self.current_config:
                self.current_config[key] = value
                logger.info(f"更新人脸识别配置: {key} = {value}")
            else:
                logger.warning(f"尝试更新不存在的配置项: {key}")
        logger.info(f"人脸识别器当前配置: {self.current_config}")

    def set_enabled(self, enabled: bool):
        """启用或禁用人脸识别器"""
        self.enabled = enabled
        logger.info(f"人脸识别器已{'启用' if enabled else '禁用'}")

    def add_face(self, image: np.ndarray, person_name: str) -> bool:
        """
        在运行时添加新的人脸到已知人脸数据库。
        Args:
            image (np.ndarray): 包含新人脸的图像 (BGR格式)。
            person_name (str): 新人脸的名称。
        Returns:
            bool: 如果成功添加人脸返回 True，否则返回 False。
        """
        if not self.enabled:
            logger.warning("人脸识别器已禁用，无法添加新面孔。")
            return False

        try:
            # 转换为RGB格式（face_recognition库要求）
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # 使用当前配置检测人脸
            face_locations = face_recognition.face_locations(
                rgb_image,
                model=self.current_config['detection_model'] if self.current_config[
                                                                    'detection_model'] != 'auto' else 'hog',
                number_of_times_to_upsample=self.current_config['number_of_times_to_upsample']
            )

            if not face_locations:
                logger.warning(f"未在提供的图像中检测到人脸，无法注册 '{person_name}'。")
                return False

            # 过滤掉过小的人脸
            filtered_locations = [
                loc for loc in face_locations
                if (loc[2] - loc[0]) >= self.current_config['min_face_size'] and
                   (loc[1] - loc[3]) >= self.current_config['min_face_size']
            ]

            if not filtered_locations:
                logger.warning(
                    f"检测到的人脸尺寸过小，无法注册 '{person_name}' (最小尺寸要求: {self.current_config['min_face_size']}px)。")
                return False

            face_encodings = face_recognition.face_encodings(rgb_image, filtered_locations)

            if not face_encodings:
                logger.warning(f"无法从图像中提取人脸特征，无法注册 '{person_name}'。")
                return False

            # 将新提取的编码动态添加到内存中的已知人脸列表
            self.known_face_encodings.extend(face_encodings)
            self.known_face_names.extend([person_name] * len(face_encodings))

            # 将新注册的人脸图片保存到 known_faces_dir 对应的子目录以实现持久化
            person_dir = os.path.join(self.known_faces_dir, person_name)
            os.makedirs(person_dir, exist_ok=True)
            # 保存一个副本
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_image_path = os.path.join(person_dir, f"reg_{timestamp}.jpg")
            cv2.imwrite(output_image_path, image)

            logger.info(f"✅ 成功注册人脸 '{person_name}'，提取 {len(face_encodings)} 个特征，保存到 {output_image_path} 并已更新内存数据库。")
            return True

        except Exception as e:
            logger.error(f"注册人脸 '{person_name}' 时发生错误: {str(e)}", exc_info=True)
            return False

    def verify_liveness_action(self, image: np.ndarray, action: str) -> bool:
        """
        验证单张图片是否符合指定的活体动作。

        Args:
            image (np.ndarray): 包含人脸的图像 (BGR格式)。
            action (str): 需要验证的动作指令 (例如: '请眨眨眼睛', '请向左转头').

        Returns:
            bool: 如果动作验证成功返回 True，否则返回 False。
        """
        try:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # 首先，获取面部关键点
            face_landmarks_list = face_recognition.face_landmarks(rgb_image)
            if not face_landmarks_list:
                logger.warning(f"活体检测失败：在图像中未找到面部关键点。动作: {action}")
                return False
            
            # 通常我们只处理第一个检测到的人脸
            landmarks = face_landmarks_list[0]

            if '眨眼' in action:
                left_eye_ear = _calculate_eye_aspect_ratio(landmarks['left_eye'])
                right_eye_ear = _calculate_eye_aspect_ratio(landmarks['right_eye'])
                avg_ear = (left_eye_ear + right_eye_ear) / 2.0
                logger.debug(f"眨眼检测: 平均EAR={avg_ear:.3f} (阈值: <{self.EAR_THRESHOLD})")
                return avg_ear < self.EAR_THRESHOLD

            elif '向左转头' in action:
                nose_tip = landmarks['nose_bridge'][-1]
                left_eye_center = np.mean(landmarks['left_eye'], axis=0)
                right_eye_center = np.mean(landmarks['right_eye'], axis=0)
                
                dist_to_left = np.linalg.norm(np.array(nose_tip) - left_eye_center)
                dist_to_right = np.linalg.norm(np.array(nose_tip) - right_eye_center)
                
                if dist_to_left == 0: return False # 避免除零
                ratio = dist_to_right / dist_to_left
                logger.debug(f"向左转头检测: 距离比={ratio:.2f} (阈值: >{self.HEAD_TURN_RATIO_THRESHOLD})")
                return ratio > self.HEAD_TURN_RATIO_THRESHOLD

            elif '向右转头' in action:
                nose_tip = landmarks['nose_bridge'][-1]
                left_eye_center = np.mean(landmarks['left_eye'], axis=0)
                right_eye_center = np.mean(landmarks['right_eye'], axis=0)
                
                dist_to_left = np.linalg.norm(np.array(nose_tip) - left_eye_center)
                dist_to_right = np.linalg.norm(np.array(nose_tip) - right_eye_center)

                if dist_to_right == 0: return False # 避免除零
                ratio = dist_to_left / dist_to_right
                logger.debug(f"向右转头检测: 距离比={ratio:.2f} (阈值: >{self.HEAD_TURN_RATIO_THRESHOLD})")
                return ratio > self.HEAD_TURN_RATIO_THRESHOLD
            
            elif '点头' in action or '正视' in action:
                # 对于点头和正视，我们可以简单地确认检测到了人脸即可
                # 更复杂的可以检查鼻子和下巴的垂直距离，但为了简化，我们暂时认为只要有脸就算通过
                return True

            else:
                logger.warning(f"未知的活体检测动作: {action}")
                return False

        except Exception as e:
            logger.error(f"活体检测动作 '{action}' 验证时发生错误: {e}", exc_info=True)
            return False

    def detect_and_recognize(self, frame: np.ndarray) -> List[Dict]:
        """
        在单帧图像中检测并识别人脸。
        Args:
            frame (np.ndarray): BGR格式的视频帧。
        Returns:
            List[Dict]: 一个包含检测到的所有人脸信息的字典列表。
        """
        if not self.enabled:
            return []

        results = []

        # 获取当前配置
        tolerance = self.current_config['tolerance']
        detection_model = self.current_config['detection_model']
        upsample_times = self.current_config['number_of_times_to_upsample']
        min_face_size = self.current_config['min_face_size']

        # 转换为RGB格式（face_recognition库要求）
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_locations = []

        # 🎯 优化人脸检测：根据配置选择模型和参数
        try:
            if detection_model == "cnn":
                face_locations = face_recognition.face_locations(rgb_frame, model="cnn",
                                                                 number_of_times_to_upsample=upsample_times)
            elif detection_model == "hog":
                face_locations = face_recognition.face_locations(rgb_frame, model="hog",
                                                                 number_of_times_to_upsample=upsample_times)
            else:  # auto 或其他未指定模型时，尝试多模型策略
                # 优先使用hog，因为它通常更快
                face_locations = face_recognition.face_locations(rgb_frame, model="hog",
                                                                 number_of_times_to_upsample=upsample_times)
                if not face_locations and upsample_times < 3:  # 如果hog没检测到且上采样次数不高，尝试更高的上采样
                    face_locations = face_recognition.face_locations(rgb_frame, model="hog",
                                                                     number_of_times_to_upsample=upsample_times + 1)
                if not face_locations:  # 如果hog仍没检测到，尝试cnn
                    face_locations = face_recognition.face_locations(rgb_frame, model="cnn",
                                                                     number_of_times_to_upsample=upsample_times)

            if face_locations:
                logger.debug(f"🎯 检测模型 '{detection_model}' 检测到 {len(face_locations)} 个人脸")
        except Exception as e:
            logger.error(f"人脸检测失败: {str(e)}", exc_info=True)
            return []  # 如果检测失败，直接返回空列表

        # 过滤掉过小的人脸
        filtered_face_locations = []
        for (top, right, bottom, left) in face_locations:
            face_height = bottom - top
            face_width = right - left
            if face_height >= min_face_size and face_width >= min_face_size:
                filtered_face_locations.append((top, right, bottom, left))
            else:
                logger.debug(f"  过滤掉过小人脸: H={face_height}, W={face_width} (Min size: {min_face_size}px)")

        if not filtered_face_locations:
            logger.debug("⚠️ 未检测到满足尺寸要求的人脸")
            return results

        # 提取人脸特征
        face_encodings = face_recognition.face_encodings(rgb_frame, filtered_face_locations)

        # 对每个检测到的人脸进行识别
        for face_idx, (face_location, face_encoding) in enumerate(zip(filtered_face_locations, face_encodings)):
            top, right, bottom, left = face_location

            # 【修复】添加缺失的人脸比对核心逻辑
            matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=tolerance)
            name = "unknown"
            confidence = 0.0
            is_known = False

            face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
            if len(face_distances) > 0:
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    name = self.known_face_names[best_match_index]
                    # 将距离转换为置信度 (0.0 -> 100%, 0.6 -> 0%)
                    confidence = 1.0 - (face_distances[best_match_index] / tolerance)
                    confidence = max(0, min(1, confidence)) # 确保在0-1之间
                    is_known = True

            results.append({
                "type": "face",
                "bbox": [left, top, right, bottom],
                "identity": {
                    "name": name,
                    "is_known": is_known,
                    "confidence": confidence,
                    "face_id": f"face_{face_idx}" # 添加一个唯一的标识符
                }
            })

        return results