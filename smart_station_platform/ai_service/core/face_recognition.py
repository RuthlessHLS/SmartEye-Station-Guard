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


class FaceRecognizer:
    def __init__(self, known_faces_dir: str):
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
        self.tolerance = self.current_config['tolerance']
        self.jitter = 1 # 默认jitter值

        self._load_known_faces()

    def _load_known_faces(self):
        """
        从指定目录加载已知人脸并生成编码。
        """
        logger.info("=== 开始加载已知人脸数据库 ===")
        logger.info(f"目录路径: {self.known_faces_dir}")

        self.known_face_encodings = []
        self.known_face_names = []

        if not os.path.isdir(self.known_faces_dir):
            logger.warning(f"已知人脸目录 '{self.known_faces_dir}' 不存在，跳过加载。")
            return

        for person_name in os.listdir(self.known_faces_dir):
            person_dir = os.path.join(self.known_faces_dir, person_name)
            if not os.path.isdir(person_dir):
                continue
            
            image_files = [f for f in os.listdir(person_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            logger.info(f"📁 处理人员目录: {person_name}，找到 {len(image_files)} 个图片文件")

            for image_file in image_files:
                try:
                    image_path = os.path.join(person_dir, image_file)
                    image = face_recognition.load_image_file(image_path)
                    face_locations = face_recognition.face_locations(image, model=self.current_config['detection_model'])
                    
                    if face_locations:
                        face_encoding = face_recognition.face_encodings(image, known_face_locations=face_locations, num_jitters=self.jitter)[0]
                        self.known_face_encodings.append(face_encoding)
                        self.known_face_names.append(person_name)
                    else:
                        logger.warning(f"在图片 '{image_file}' 中未找到人脸，已跳过。")
                except Exception as e:
                    logger.error(f"处理图片 '{image_file}' 时出错: {e}", exc_info=True)
        
        logger.info(f"✅ 人脸数据库加载完成。共加载 {len(self.known_face_encodings)} 个已知人脸。")

    async def reload_known_faces(self):
        """
        异步接口，在后台线程中安全地重新加载人脸数据。
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

            # 将新提取的编码添加到内存中的已知人脸字典
            if person_name not in self.known_faces:
                self.known_faces[person_name] = []
            self.known_faces[person_name].extend(face_encodings)

            # 可选：将新注册的人脸图片保存到 known_faces_dir 对应的子目录
            person_dir = os.path.join(self.known_faces_dir, person_name)
            os.makedirs(person_dir, exist_ok=True)
            # 保存一个副本，用于持久化
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_image_path = os.path.join(person_dir, f"{person_name}_{timestamp}.jpg")
            cv2.imwrite(output_image_path, image)

            logger.info(f"成功注册人脸 '{person_name}'，提取 {len(face_encodings)} 个特征，保存到 {output_image_path}")
            return True

        except Exception as e:
            logger.error(f"注册人脸 '{person_name}' 时发生错误: {str(e)}", exc_info=True)
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

            # 与所有已知人脸进行比对
            all_distances = {}  # {name: [distances]}
            for known_name, known_encodings in self.known_faces.items():
                if known_encodings:  # 确保有已知编码
                    # 计算人脸特征向量的欧氏距离
                    # 【修复 3.1】将 face_recognition.face_distances 更正为 face_recognition.face_distance
                    distances = face_recognition.face_distance(known_encodings, face_encoding)
                    all_distances[known_name] = distances.tolist()  # 转换为列表

            best_matches = []
            for name, distances in all_distances.items():
                if distances:
                    min_distance = min(distances)
                    avg_distance = sum(distances) / len(distances)
                    best_matches.append((name, min_distance, avg_distance))

            best_matches.sort(key=lambda x: x[1])  # 按最小距离排序

            identity = {"name": "unknown", "known": False, "confidence": 0.0}
            confidence_score = 0.0

            if best_matches:
                best_name, best_distance, avg_distance = best_matches[0]

                # 🎯 优化后的识别判断：更灵敏但仍准确
                # 1. 基础阈值检查：最佳匹配必须小于基础阈值
                passes_base_threshold = best_distance <= tolerance

                # 2. 简化的差异度检查：如果有其他候选人，确保有一定差距
                # 避免被第二相似的人脸干扰
                passes_distinction = True
                if len(best_matches) > 1:
                    second_best_distance = best_matches[1][1]
                    # 确保最佳匹配与次佳匹配之间有足够的距离差异
                    if best_distance > 0:  # 避免除以零
                        distance_gap_ratio = (second_best_distance - best_distance) / best_distance
                        if distance_gap_ratio < 0.12:  # 降低差距要求从15%到12%
                            passes_distinction = False

                # 3. 适中的绝对阈值检查：进一步放宽硬性上限
                passes_absolute = best_distance <= 0.75  # 放宽从0.65到0.75

                # 🔥 扩展：高置信度快速通道 - 扩大快速通道范围
                is_high_confidence = best_distance <= 0.45  # 从0.35扩展到0.45

                # 🌟 新增：中等置信度通道 - 在高置信度和标准检查之间增加中间层
                is_medium_confidence = (best_distance <= 0.55 and passes_base_threshold)

                # 综合判断：多级通道提高识别率
                is_confident = (
                        is_high_confidence or  # 高置信度快速通道
                        is_medium_confidence or  # 中等置信度通道
                        (passes_base_threshold and passes_distinction and passes_absolute)
                )

                if is_confident:
                    confidence_score = max(0.0, 1.0 - best_distance)  # 距离越小，置信度越高
                    identity = {"name": best_name, "known": True, "confidence": confidence_score}
                    logger.debug(f"  ✅ 识别为: {best_name} (距离: {best_distance:.3f}, 置信度: {confidence_score:.3f})")
                    if is_high_confidence:
                        logger.debug(f"    🚀 高置信度快速通道: {best_distance:.3f} <= 0.45")
                    elif is_medium_confidence:
                        logger.debug(f"    🎯 中等置信度通道: {best_distance:.3f} <= 0.55")
                    else:
                        logger.debug(
                            f"    📊 标准检查通过: 基础阈值={passes_base_threshold}, 差异={passes_distinction}, 绝对={passes_absolute}")
                else:
                    identity = {"name": "unknown", "known": False, "confidence": 0.0}
                    logger.debug(f"  ❌ 未知人员 (最佳距离: {best_distance:.3f})")
                    logger.debug(
                        f"    🔍 检查未通过: 高置信度={is_high_confidence}, 中等置信度={is_medium_confidence}, 基础阈值={passes_base_threshold}, 差异={passes_distinction}, 绝对={passes_absolute}")
            else:
                logger.debug("  没有已知人脸匹配。")

            results.append({
                "location": {"top": top, "right": right, "bottom": bottom, "left": left},
                "identity": identity,
                "confidence": confidence_score,
                "alert_needed": identity["name"] == "unknown",
                "best_match": best_matches[0] if best_matches else None,
                "detection_time": datetime.now().isoformat()
            })

        return results