# 文件: ai_service/core/face_recognition.py
# 描述: 人脸识别器，用于检测、编码和识别人脸。

import face_recognition
import numpy as np
import os
import cv2
from typing import List, Dict
import datetime


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

    def detect_and_recognize(self, frame: np.ndarray, tolerance=0.45) -> List[Dict]:
        """
        在单帧图像中检测并识别人脸。

        Args:
            frame (np.ndarray): BGR格式的视频帧。
            tolerance (float): 人脸比对的容忍度，值越小比对越严格。
                             建议范围：0.4-0.5，小于0.4可能过于严格，大于0.5可能过于宽松。

        Returns:
            List[Dict]: 一个包含检测到的所有人脸信息的字典列表。
        """
        results = []
        
        # 检测人脸位置
        face_locations = face_recognition.face_locations(frame)
        if not face_locations:
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
                
                # 使用更严格的多重判断标准来确定是否为已知人员：
                
                # 1. 基础阈值检查：最佳匹配必须小于基础阈值
                passes_base_threshold = best_distance <= tolerance
                
                # 2. 平均距离检查：平均距离不能太高，说明整体相似度要足够
                passes_avg_threshold = avg_distance <= tolerance * 1.15
                
                # 3. 差异度检查：如果有其他候选人，必须与第二候选人有显著差距
                if len(best_matches) > 1:
                    second_best_distance = best_matches[1][1]
                    distance_gap = (second_best_distance - best_distance) / best_distance
                    passes_distinction = distance_gap > 0.2  # 要求至少20%的差距
                else:
                    passes_distinction = True
                
                # 4. 稳定性检查：最佳匹配与平均值不能差太多
                stability_ratio = best_distance / avg_distance
                passes_stability = stability_ratio > 0.7  # 最佳值不能比平均值好太多
                
                # 5. 绝对阈值检查：即使通过了相对比较，也不能超过最大允许阈值
                passes_absolute = best_distance <= 0.5  # 硬性上限
                
                # 综合所有判断条件
                is_confident = (
                    passes_base_threshold and
                    passes_avg_threshold and
                    passes_distinction and
                    passes_stability and
                    passes_absolute
                )
                
                if is_confident:
                    identity = {"name": best_name, "known": True}
                    print(f"  ✅ 识别为: {best_name}")
                    print(f"    置信度检查:")
                    print(f"    - 基础阈值: {'通过' if passes_base_threshold else '未通过'}")
                    print(f"    - 平均距离: {'通过' if passes_avg_threshold else '未通过'}")
                    print(f"    - 差异程度: {'通过' if passes_distinction else '未通过'}")
                    print(f"    - 匹配稳定性: {'通过' if passes_stability else '未通过'}")
                    print(f"    - 绝对阈值: {'通过' if passes_absolute else '未通过'}")
                else:
                    identity = {"name": "unknown", "known": False}
                    print(f"  ❌ 未知人员")
                    print(f"    未通过项:")
                    if not passes_base_threshold:
                        print(f"    - 基础阈值检查未通过 ({best_distance:.3f} > {tolerance})")
                    if not passes_avg_threshold:
                        print(f"    - 平均距离检查未通过 ({avg_distance:.3f} > {tolerance * 1.15:.3f})")
                    if not passes_distinction and len(best_matches) > 1:
                        print(f"    - 与其他候选人差异不够明显 (差距率: {distance_gap:.1%})")
                    if not passes_stability:
                        print(f"    - 匹配稳定性检查未通过 (稳定率: {stability_ratio:.1%})")
                    if not passes_absolute:
                        print(f"    - 超出绝对阈值限制 ({best_distance:.3f} > 0.5)")
            else:
                identity = {"name": "unknown", "known": False}
                print(f"  ❌ 未知人员")
            
            # 添加到结果列表
            results.append({
                "location": {"top": top, "right": right, "bottom": bottom, "left": left},
                "identity": identity,
                "confidence": 1 - best_matches[0][1] if best_matches else 0,
                "alert_needed": identity["name"] == "unknown",  # 添加是否需要报警的标志
                "best_match": best_matches[0] if best_matches else None,  # 添加最佳匹配信息
                "detection_time": datetime.datetime.now().isoformat()  # 添加检测时间
            })
        
        return results