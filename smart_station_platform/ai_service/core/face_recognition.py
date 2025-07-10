# 文件: ai_service/core/face_recognition.py
# 描述: 人脸识别器，用于检测、编码和识别人脸。

import face_recognition
import numpy as np
import os
import cv2
from typing import List, Dict
from datetime import datetime


class FaceRecognizer:
    def __init__(self, known_faces_dir: str):
        """
        初始化人脸识别器。

        Args:
            known_faces_dir (str): 包含已知人脸图片的目录路径。
                                目录结构应为：known_faces_dir/person_name/image_files
        """
        self.known_faces = {}  # 使用字典存储每个人的人脸编码 {name: [encodings]}
        
        if not os.path.exists(known_faces_dir):
            print(f"警告: 已知人脸目录不存在: {known_faces_dir}")
            return

        # 遍历目录加载已知人脸
        print(f"\n=== 开始加载已知人脸数据库 ===")
        print(f"目录路径: {known_faces_dir}")
        
        for person_name in os.listdir(known_faces_dir):
            person_dir = os.path.join(known_faces_dir, person_name)
            if os.path.isdir(person_dir):
                print(f"\n📁 处理人员目录: {person_name}")
                self.known_faces[person_name] = []
                
                image_files = [f for f in os.listdir(person_dir) 
                             if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                print(f"  找到 {len(image_files)} 个图片文件")
                
                for image_name in image_files:
                    image_path = os.path.join(person_dir, image_name)
                    try:
                        print(f"  - 处理图片: {image_name}")
                        # 加载图片
                        face_image = face_recognition.load_image_file(image_path)
                        # 检测人脸
                        face_locations = face_recognition.face_locations(face_image)
                        if not face_locations:
                            print(f"    ⚠️ 警告: 未检测到人脸")
                            continue
                        # 提取人脸特征
                        face_encodings = face_recognition.face_encodings(face_image, face_locations)
                        if face_encodings:
                            self.known_faces[person_name].extend(face_encodings)
                            print(f"    ✅ 成功提取人脸特征")
                        else:
                            print(f"    ⚠️ 警告: 无法提取人脸特征")
                    except Exception as e:
                        print(f"    ❌ 错误: {str(e)}")
                
                # 显示该人员的统计信息
                encodings_count = len(self.known_faces[person_name])
                if encodings_count > 0:
                    print(f"  ✅ {person_name} 总共提取了 {encodings_count} 个人脸特征")
                else:
                    print(f"  ⚠️ {person_name} 没有提取到任何有效的人脸特征，将被移除")
                    del self.known_faces[person_name]
        
        # 显示最终统计信息
        print("\n=== 人脸数据库加载完成 ===")
        print(f"总共加载了 {len(self.known_faces)} 个人员:")
        for name, encodings in self.known_faces.items():
            print(f"- {name}: {len(encodings)} 个特征")
        print("=========================")

    def detect_and_recognize(self, frame: np.ndarray, tolerance=0.6) -> List[Dict]:
        """
        在单帧图像中检测并识别人脸。

        Args:
            frame (np.ndarray): BGR格式的视频帧。
            tolerance (float): 人脸比对的容忍度，值越小比对越严格。
                             建议范围：0.5-0.7，小于0.5可能过于严格，大于0.7可能过于宽松。

        Returns:
            List[Dict]: 一个包含检测到的所有人脸信息的字典列表。
        """
        results = []

        # 🎯 优化人脸检测：提高检测灵敏度和小人脸检测能力
        # 尝试不同的检测模型和参数组合
        face_locations = []
        
        # 方法1：使用CNN模型 (更准确但较慢) - 提高灵敏度
        try:
            face_locations = face_recognition.face_locations(frame, model="cnn", number_of_times_to_upsample=2)
            if face_locations:
                print(f"🎯 CNN模型检测到 {len(face_locations)} 个人脸")
        except:
            pass
        
        # 方法2：如果CNN没检测到，使用HOG模型 (更快但可能漏检) - 提高灵敏度
        if not face_locations:
            face_locations = face_recognition.face_locations(frame, model="hog", number_of_times_to_upsample=3)
            if face_locations:
                print(f"🎯 HOG模型检测到 {len(face_locations)} 个人脸")
        
        # 方法3：如果还是没有，尝试缩放图像再检测
        if not face_locations and frame.shape[0] > 480:
            # 对于大图像，先缩小再检测可能更有效
            scale_factor = 480 / frame.shape[0]
            small_frame = cv2.resize(frame, None, fx=scale_factor, fy=scale_factor)
            small_face_locations = face_recognition.face_locations(small_frame, model="hog", number_of_times_to_upsample=2)
            
            # 将小图上的坐标转换回原图
            face_locations = []
            for (top, right, bottom, left) in small_face_locations:
                face_locations.append((
                    int(top / scale_factor),
                    int(right / scale_factor), 
                    int(bottom / scale_factor),
                    int(left / scale_factor)
                ))
            if face_locations:
                print(f"🎯 缩放检测到 {len(face_locations)} 个人脸")
        
        # 方法4：新增 - 尝试更小的缩放比例检测微小人脸
        if not face_locations:
            try:
                # 尝试检测更小的人脸
                smaller_frame = cv2.resize(frame, None, fx=0.8, fy=0.8)
                small_face_locations = face_recognition.face_locations(smaller_frame, model="hog", number_of_times_to_upsample=4)
                
                # 将坐标转换回原图
                face_locations = []
                for (top, right, bottom, left) in small_face_locations:
                    face_locations.append((
                        int(top / 0.8),
                        int(right / 0.8), 
                        int(bottom / 0.8),
                        int(left / 0.8)
                    ))
                if face_locations:
                    print(f"🎯 高灵敏度检测到 {len(face_locations)} 个人脸")
            except:
                pass
        
        if not face_locations:
            print("⚠️ 未检测到任何人脸")
            return results
            
        # 提取人脸特征
        face_encodings = face_recognition.face_encodings(frame, face_locations)
        
        # 对每个检测到的人脸进行识别
        for face_idx, (face_location, face_encoding) in enumerate(zip(face_locations, face_encodings)):
            top, right, bottom, left = face_location
            
            # 与所有已知人脸进行比对
            all_distances = {}  # {name: [distances]}
            for known_name, known_encodings in self.known_faces.items():
                all_distances[known_name] = []
                for known_encoding in known_encodings:
                    # 计算人脸特征向量的欧氏距离
                    distance = face_recognition.face_distance([known_encoding], face_encoding)[0]
                    all_distances[known_name].append(distance)
            
            # 输出调试信息
            print(f"\n🔍 人脸 #{face_idx + 1} 识别结果:")
            print(f"  位置: 上={top}, 右={right}, 下={bottom}, 左={left}")
            
            # 计算每个人的最小距离（最佳匹配）和平均距离
            best_matches = []
            for name, distances in all_distances.items():
                if distances:
                    min_distance = min(distances)
                    avg_distance = sum(distances) / len(distances)
                    best_matches.append((name, min_distance, avg_distance))
            
            # 按最小距离排序
            best_matches.sort(key=lambda x: x[1])
            
            if best_matches:
                print("  匹配分数 (越小越相似):")
                for name, min_dist, avg_dist in best_matches:
                    print(f"    - {name}: 最佳={min_dist:.3f}, 平均={avg_dist:.3f}")
                
                # 选择最佳匹配作为识别结果
                best_name, best_distance, avg_distance = best_matches[0]
                
                # 🎯 优化后的识别判断：更灵敏但仍准确
                
                # 1. 基础阈值检查：最佳匹配必须小于基础阈值
                passes_base_threshold = best_distance <= tolerance
                
                # 2. 简化的差异度检查：如果有其他候选人，确保有一定差距
                if len(best_matches) > 1:
                    second_best_distance = best_matches[1][1]
                    distance_gap = (second_best_distance - best_distance) / best_distance
                    passes_distinction = distance_gap > 0.12  # 降低差距要求从15%到12%
                else:
                    passes_distinction = True
                
                # 3. 适中的绝对阈值检查：进一步放宽硬性上限
                passes_absolute = best_distance <= 0.75  # 放宽从0.65到0.75
                
                # 🔥 扩展：高置信度快速通道 - 扩大快速通道范围
                is_high_confidence = best_distance <= 0.45  # 从0.35扩展到0.45
                
                # 🌟 新增：中等置信度通道 - 在高置信度和标准检查之间增加中间层
                is_medium_confidence = (best_distance <= 0.55 and passes_base_threshold)
                
                # 综合判断：多级通道提高识别率
                is_confident = (
                    is_high_confidence or      # 高置信度快速通道
                    is_medium_confidence or    # 中等置信度通道
                    (passes_base_threshold and passes_distinction and passes_absolute)
                )
                
                if is_confident:
                    identity = {"name": best_name, "known": True, "confidence": 1 - best_distance}
                    print(f"  ✅ 识别为: {best_name}")
                    if is_high_confidence:
                        print(f"    🚀 高置信度快速通道: {best_distance:.3f} ≤ 0.45")
                    elif is_medium_confidence:
                        print(f"    🎯 中等置信度通道: {best_distance:.3f} ≤ 0.55")
                    else:
                        print(f"    📊 标准检查通过:")
                        print(f"    - 基础阈值: {'✓' if passes_base_threshold else '✗'} ({best_distance:.3f} vs {tolerance})")
                        print(f"    - 差异程度: {'✓' if passes_distinction else '✗'}")
                        print(f"    - 绝对阈值: {'✓' if passes_absolute else '✗'} ({best_distance:.3f} vs 0.75)")
                else:
                    identity = {"name": "unknown", "known": False, "confidence": 0}
                    print(f"  ❌ 未知人员 (距离: {best_distance:.3f})")
                    print(f"    🔍 检查结果:")
                    print(f"    - 高置信度: {'✗' if not is_high_confidence else '✓'} ({best_distance:.3f} > 0.45)")
                    print(f"    - 中等置信度: {'✗' if not is_medium_confidence else '✓'} ({best_distance:.3f} > 0.55)")
                    print(f"    - 基础阈值: {'✗' if not passes_base_threshold else '✓'} ({best_distance:.3f} vs {tolerance})")
                    print(f"    - 差异程度: {'✗' if not passes_distinction else '✓'}")
                    print(f"    - 绝对阈值: {'✗' if not passes_absolute else '✓'} ({best_distance:.3f} vs 0.75)")
            else:
                identity = {"name": "unknown", "known": False, "confidence": 0}
            
            # 添加到结果列表
            results.append({
                "location": {"top": top, "right": right, "bottom": bottom, "left": left},
                "identity": identity,
                "confidence": 1 - best_matches[0][1] if best_matches else 0,
                "alert_needed": identity["name"] == "unknown",  # 添加是否需要报警的标志
                "best_match": best_matches[0] if best_matches else None,  # 添加最佳匹配信息
                "detection_time": datetime.now().isoformat()  # 添加检测时间
            })
        
        return results