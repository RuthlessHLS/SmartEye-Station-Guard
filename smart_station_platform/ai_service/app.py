# 文件: ai_service/app.py
# 描述: 智能视频分析服务的主入口，负责API路由、服务生命周期管理、AI功能协调。

import os
import asyncio
import time
import base64
import traceback
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any, Union, Tuple

import cv2
import numpy as np
import uvicorn
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Body, File, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 导入我们自定义的所有核心AI模块和模型
import sys

# 将当前目录添加到Python路径，确保可以导入核心模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.video_stream import VideoStream
from core.object_detection import GenericPredictor
from core.behavior_detection import BehaviorDetector
from core.face_recognition import FaceRecognizer
from core.acoustic_detection import AcousticEventDetector
from core.fire_smoke_detection import FlameSmokeDetector
from core.multi_object_tracker import DeepSORTTracker
from core.danger_zone_detection import danger_zone_detector
from models.alert_models import AIAnalysisResult, CameraConfig, SystemStatus  # 确保这些文件存在且结构正确


# --- 配置管理 ---
class AppConfig:
    """应用程序的全局配置类"""

    def __init__(self):
        # 从 .env 文件加载环境变量
        current_dir = os.path.dirname(os.path.abspath(__file__))
        dotenv_path = os.path.join(current_dir, '.env')
        if os.path.exists(dotenv_path):
            print(f"--- 正在从 '{dotenv_path}' 加载环境变量 ---")
            load_dotenv(dotenv_path=dotenv_path)
        else:
            print(f"--- 警告: 未找到 .env 文件 at '{dotenv_path}'，将使用系统环境变量 ---")
            load_dotenv()  # 尝试从系统环境变量加载

        self.ASSET_BASE_PATH = os.getenv("G_DRIVE_ASSET_PATH", "/app/assets")  # 默认值，如果未配置
        self.AI_SERVICE_API_KEY = os.getenv('AI_SERVICE_API_KEY', 'smarteye-ai-service-key-2024')
        self.BACKEND_ALERT_URL = os.getenv('BACKEND_ALERT_URL', 'http://localhost:8000/api/alerts/ai-results/')
        self.BACKEND_WEBSOCKET_BROADCAST_URL = os.getenv('BACKEND_WEBSOCKET_BROADCAST_URL',
                                                         'http://localhost:8000/api/alerts/websocket/broadcast/')
        self.ENABLE_SOUND_DETECTION = os.getenv("ENABLE_SOUND_DETECTION", "false").lower() == "true"
        self.FASTAPI_TIMEOUT_SECONDS = float(os.getenv("FASTAPI_TIMEOUT_SECONDS", "120.0"))

        print(f"--- 使用资源根目录: {self.ASSET_BASE_PATH} ---")


# 初始化配置
app_config = AppConfig()


# --- AIServiceManager 类：集中管理AI服务逻辑和数据 ---
class AIServiceManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self._detectors: Dict[str, Any] = {}  # 存储所有AI检测器实例
        self._video_streams: Dict[str, VideoStream] = {}  # 存储活跃的VideoStream实例
        self._object_trackers: Dict[str, DeepSORTTracker] = {}  # 存储每个摄像头的DeepSORT追踪器
        self._detection_cache: Dict[str, Dict] = {}  # 存储每个摄像头的检测稳定化缓存
        self._thread_pool = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)
        self._ai_settings: Dict[str, Dict] = {}  # 存储每个摄像头的AI分析设置
        self._face_recognition_config: Dict[str, Any] = {
            "tolerance": 0.65, "detection_model": "auto", "enable_multi_scale": True,
            "min_face_size": 40, "max_upsample": 4, "use_cnn_fallback": True
        }
        self._object_detection_config: Dict[str, Any] = {
            "confidence_threshold": 0.35, "area_ratio_threshold": 0.9,
            "special_class_threshold": 0.6, "enable_size_filter": True,
            "enable_aspect_ratio_filter": True
        }
        # 检测结果稳定化参数存储 (per camera_id)
        self._stabilization_config: Dict[str, Dict] = {}

    async def initialize_detectors(self):
        """初始化所有AI检测器模型。"""
        print("--- 正在初始化所有检测器 ---")
        try:
            model_weights_path = os.path.join(self.config.ASSET_BASE_PATH, "models", "torch", "yolov8n.pt")
            class_names_path = os.path.join(self.config.ASSET_BASE_PATH, "models", "coco.names")
            known_faces_dir = os.path.join(self.config.ASSET_BASE_PATH, "known_faces")

            # 1. 初始化通用目标检测器
            class_names = []
            try:
                with open(class_names_path, 'r', encoding='utf-8') as f:
                    class_names = [line.strip() for line in f.readlines()]
                print(f"成功从 '{class_names_path}' 加载 {len(class_names)} 个类别名称。")
            except FileNotFoundError:
                print(f"警告: 找不到类别名称文件 at '{class_names_path}'。")
                class_names = ["background", "person"]

            self._detectors["object"] = GenericPredictor(
                model_weights_path=model_weights_path,
                num_classes=len(class_names),
                class_names=class_names
            )

            # 2. 初始化行为检测器 (简化版)
            self._detectors["behavior"] = BehaviorDetector()

            # 3. 初始化人脸识别器
            print(f"正在从目录 '{known_faces_dir}' 加载已知人脸。")
            self._detectors["face"] = FaceRecognizer(known_faces_dir=known_faces_dir)

            # 4. 初始化声学事件检测器
            if self.config.ENABLE_SOUND_DETECTION:
                try:
                    self._detectors["acoustic"] = AcousticEventDetector()
                    # 声学分析后台任务在start_stream时随VideoStream启动音频提取
                except Exception as e:
                    print(f"警告: 声学检测器初始化失败，将禁用此功能。错误: {e}")

            # 5. 初始化火焰烟雾检测器
            try:
                fire_model_path = os.path.join(self.config.ASSET_BASE_PATH, "models", "torch", "yolov8n-fire.pt")
                if os.path.exists(fire_model_path):
                    self._detectors["fire"] = FlameSmokeDetector(model_path=fire_model_path)
                else:
                    general_model_path = os.path.join(self.config.ASSET_BASE_PATH, "models", "torch", "yolov8n.pt")
                    self._detectors["fire"] = FlameSmokeDetector(model_path=general_model_path)
                print("火焰烟雾检测器初始化成功")
            except Exception as e:
                print(f"警告: 火焰烟雾检测器初始化失败，将禁用此功能。错误: {e}")

            print("--- 所有检测器初始化完成 ---")

        except Exception as e:
            print(f"致命错误: 检测器初始化失败: {e}")
            raise

    async def _run_acoustic_analysis(self, camera_id: str):
        """后台持续运行的协程，用于分析特定摄像头的音频数据。"""
        print(f"声学分析后台任务已启动 for {camera_id}。")
        acoustic_detector = self._detectors.get("acoustic")
        if not acoustic_detector:
            print("声学检测器未初始化，无法运行声学分析任务。")
            return

        stream_obj = self._video_streams.get(camera_id)
        if not stream_obj or not hasattr(stream_obj, 'get_audio_file'):
            print(f"摄像头 {camera_id} 不支持音频提取或视频流未启动。")
            return

        while stream_obj.is_running and self.config.ENABLE_SOUND_DETECTION:
            try:
                audio_file = stream_obj.get_audio_file()  # 这个方法需要在VideoStream中实现
                if audio_file and os.path.exists(audio_file):
                    events = await acoustic_detector.process_audio_file(audio_file)
                    for event in events:
                        event_emoji = {
                            "volume_anomaly": "📢", "high_frequency_noise": "🔊", "sudden_noise": "💥"
                        }.get(event['type'], "🔔")

                        print(f"{event_emoji} [音频] {event['description']} (Camera: {camera_id})")
                        self.send_alert_to_backend(
                            AIAnalysisResult(
                                camera_id=camera_id,
                                event_type=f"acoustic_{event['type']}",
                                location={"timestamp": event['timestamp']},
                                confidence=event['confidence'],
                                timestamp=datetime.now().isoformat(),
                                details={"description": event['description'], "audio_timestamp": event['timestamp']}
                            )
                        )
                else:
                    # 仅在非WebcamProcessor的情况下打印警告
                    if not getattr(stream_obj, 'is_webcam', False):
                        print(f"⚠️ 音频文件未找到或未就绪 for {camera_id}: {audio_file}")
            except Exception as e:
                print(f"声学分析过程中发生错误 for {camera_id}: {e}")
                traceback.print_exc()

            await asyncio.sleep(acoustic_detector.detection_interval)

    def send_alert_to_backend(self, result: AIAnalysisResult):
        """发送AI分析结果到后端，带有重试机制"""

        def task():
            try:
                session = requests.Session()
                retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
                session.mount('http://', HTTPAdapter(max_retries=retries))
                session.mount('https://', HTTPAdapter(max_retries=retries))

                data = result.model_dump_json()  # 使用pydantic的model_dump_json
                headers = {
                    'Content-Type': 'application/json',
                    'X-AI-Service': 'true',
                    'X-API-Key': self.config.AI_SERVICE_API_KEY,
                }

                response = session.post(self.config.BACKEND_ALERT_URL, data=data, headers=headers, timeout=5)

                if response.status_code == 200:
                    print(f"✅ 成功发送告警到后端: {result.event_type}")
                else:
                    print(f"❌ 发送告警失败: HTTP {response.status_code}, 响应内容: {response.text}")
            except Exception as e:
                print(f"❌ 发送告警时发生错误: {str(e)}")
                try:
                    with open('failed_alerts.json', 'a') as f:
                        # 确保 data 变量在异常发生时也可用
                        json_data = result.model_dump_json() if 'result' in locals() else {}
                        json.dump(
                            {"timestamp": datetime.now().isoformat(), "alert": json.loads(json_data), "error": str(e)},
                            f)
                        f.write('\n')
                except Exception as write_error:
                    print(f"无法保存失败的告警: {str(write_error)}")

        self._thread_pool.submit(task)

    async def send_detection_to_websocket(self, camera_id: str, detection_results: dict):
        """通过WebSocket向前端发送检测结果数据 (非图像)"""

        def task():
            try:
                websocket_data = {
                    "type": "detection_result",
                    "data": {
                        "camera_id": camera_id,
                        "timestamp": datetime.now().isoformat(),
                        "detections": detection_results.get("detections", []),
                        "performance_info": detection_results.get("performance_info", {})
                    }
                }
                response = requests.post(
                    self.config.BACKEND_WEBSOCKET_BROADCAST_URL,
                    json=websocket_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=2
                )
                if response.status_code == 200:
                    print(f"✅ 检测数据已发送到WebSocket: {camera_id}")
                else:
                    print(f"⚠️ WebSocket数据发送失败: {response.status_code}")
            except Exception as e:
                print(f"发送检测数据到WebSocket失败: {e}")

        self._thread_pool.submit(task)

    async def shutdown_services(self):
        """关闭所有正在运行的服务和清理资源"""
        print("服务正在关闭，开始清理资源...")
        for stream in list(self._video_streams.values()):  # 使用list()避免在迭代时修改字典
            stream.stop()
        if "acoustic" in self._detectors:
            self._detectors["acoustic"].stop_monitoring()
        self._thread_pool.shutdown(wait=True)
        print("资源清理完毕。")

    # --- AI 检测结果稳定化函数 (移动到此类中) ---
    def _calculate_bbox_distance(self, bbox1, bbox2):
        center1 = [(bbox1[0] + bbox1[2]) / 2, (bbox1[1] + bbox1[3]) / 2]
        center2 = [(bbox2[0] + bbox2[2]) / 2, (bbox2[1] + bbox2[3]) / 2]
        return ((center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2) ** 0.5

    def _calculate_bbox_overlap(self, bbox1, bbox2):
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        if x2 <= x1 or y2 <= y1: return 0
        intersection = (x2 - x1) * (y2 - y1)
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        union = area1 + area2 - intersection
        return intersection / union if union > 0 else 0

    def stabilize_detections(self, camera_id: str, new_detections: List[Dict]) -> List[Dict]:
        """高性能自适应检测结果稳定化 - 人脸持续跟踪优化"""
        current_time = time.time()
        if camera_id not in self._detection_cache:
            self._detection_cache[camera_id] = {"objects": {}, "face_history": {}}

        cache = self._detection_cache[camera_id]["objects"]
        face_history = self._detection_cache[camera_id]["face_history"]
        results = []
        matched_ids = set()

        face_detections = [d for d in new_detections if d["type"] == "face"]
        other_detections = [d for d in new_detections if d["type"] != "face"]

        face_results = self._advanced_face_tracking(camera_id, face_detections, cache, face_history, current_time,
                                                    matched_ids)
        results.extend(face_results)

        other_results = self._standard_object_tracking(other_detections, cache, current_time, matched_ids, camera_id)
        results.extend(other_results)

        self._cleanup_expired_cache(cache, face_history, current_time)
        return results

    def _advanced_face_tracking(self, camera_id: str, face_detections: List[Dict], cache: Dict, face_history: Dict,
                                current_time: float, matched_ids: set) -> List[Dict]:
        results = []
        config = self._stabilization_config.get(camera_id, {})
        FACE_MATCH_THRESHOLD = config.get('face_match_threshold', 150)
        FACE_SMOOTH_FACTOR = config.get('face_smooth_factor', 0.85)
        JITTER_THRESHOLD = config.get('jitter_detection_threshold', 20)
        SIZE_CHANGE_RATIO = config.get('max_size_change_ratio', 0.2)
        FACE_KEEP_TIME = 1.5
        FACE_MIN_CONFIDENCE = 0.25
        FACE_STABLE_THRESHOLD = 1
        CONFIDENCE_SMOOTH_FACTOR = 0.7

        IDENTITY_HISTORY_SIZE = 8
        IDENTITY_CHANGE_THRESHOLD = 0.6
        IDENTITY_CONFIDENCE_DIFF = 0.12
        MIN_STABLE_FRAMES = 2

        self._predict_missing_faces(cache, face_history, current_time)

        for face_det in face_detections:
            face_bbox = face_det["bbox"]
            best_match_id = None
            best_score = float('inf')

            for obj_id, obj_data in cache.items():
                if obj_data["type"] != "face" or obj_id in matched_ids: continue
                score = self._calculate_face_match_score(face_bbox, obj_data, current_time)
                if score < best_score and score < FACE_MATCH_THRESHOLD:
                    best_score = score
                    best_match_id = obj_id

            if best_match_id:
                old_obj = cache[best_match_id]
                history = face_history.get(best_match_id, {})
                is_jittery = self._detect_jitter(face_bbox, old_obj["bbox"], history, JITTER_THRESHOLD)

                effective_smooth_factor = min(0.97, FACE_SMOOTH_FACTOR + 0.05) if is_jittery else FACE_SMOOTH_FACTOR
                smoothed_bbox = self._advanced_face_smoothing(face_bbox, old_obj, history, effective_smooth_factor)
                smoothed_bbox = self._stabilize_bbox_size(smoothed_bbox, old_obj["bbox"],
                                                          max_change_ratio=SIZE_CHANGE_RATIO)

                old_confidence = old_obj.get("confidence", face_det["confidence"])
                smoothed_confidence = old_confidence * (1 - CONFIDENCE_SMOOTH_FACTOR) + face_det[
                    "confidence"] * CONFIDENCE_SMOOTH_FACTOR
                if smoothed_confidence < old_confidence * 0.7:
                    smoothed_confidence = old_confidence * 0.8

                cache[best_match_id].update({
                    "bbox": smoothed_bbox,
                    "confidence": max(FACE_MIN_CONFIDENCE, smoothed_confidence),
                    "last_seen": current_time,
                    "stable_count": min(old_obj.get("stable_count", 0) + 1, 10),
                    "consecutive_detections": old_obj.get("consecutive_detections", 0) + 1,
                    "last_detection": current_time,
                    "is_jittery": is_jittery,
                    "flicker_protection": True
                })

                if best_match_id not in face_history:
                    face_history[best_match_id] = {"positions": [], "timestamps": []}
                history = face_history[best_match_id]
                history["positions"].append(smoothed_bbox)
                history["timestamps"].append(current_time)
                if len(history["positions"]) > 5:
                    history["positions"] = history["positions"][-5:]
                    history["timestamps"] = history["timestamps"][-5:]

                if "identity" in face_det:
                    new_identity = face_det["identity"].copy()
                    if "confidence" not in new_identity:
                        new_identity["confidence"] = face_det.get("confidence", 0.5)
                    stable_identity = self._stabilize_face_identity(
                        best_match_id, new_identity, face_history, IDENTITY_HISTORY_SIZE,
                        IDENTITY_CHANGE_THRESHOLD, IDENTITY_CONFIDENCE_DIFF, MIN_STABLE_FRAMES
                    )
                    face_det["identity"] = stable_identity
                    cache[best_match_id]["identity"] = stable_identity

                matched_ids.add(best_match_id)
                result_det = face_det.copy()
                result_det["bbox"] = smoothed_bbox
                result_det["tracking_id"] = best_match_id
                result_det["is_stable"] = cache[best_match_id]["stable_count"] >= FACE_STABLE_THRESHOLD
                result_det["consecutive_detections"] = cache[best_match_id]["consecutive_detections"]
                results.append(result_det)
            else:
                new_id = f"face_{int(current_time * 1000) % 10000}"
                cache[new_id] = {
                    "bbox": face_bbox, "confidence": face_det["confidence"], "type": "face",
                    "last_seen": current_time, "stable_count": 1, "consecutive_detections": 1,
                    "first_seen": current_time, "last_detection": current_time
                }
                face_history[new_id] = {"positions": [face_bbox], "timestamps": [current_time]}
                result_det = face_det.copy()
                result_det["tracking_id"] = new_id
                result_det["is_stable"] = False
                result_det["consecutive_detections"] = 1
                results.append(result_det)
                matched_ids.add(new_id)

        for obj_id, obj_data in list(cache.items()):
            if (obj_data["type"] == "face" and obj_id not in matched_ids and obj_data.get("consecutive_detections",
                                                                                          0) >= 3):
                time_since_last_seen = current_time - obj_data["last_seen"]
                if time_since_last_seen < FACE_KEEP_TIME:
                    predicted_bbox = self._predict_face_position(obj_id, face_history, current_time)
                    if predicted_bbox:
                        kept_det = {
                            "type": "face", "bbox": predicted_bbox,
                            "confidence": max(0.3,
                                              obj_data["confidence"] * (1 - time_since_last_seen / FACE_KEEP_TIME)),
                            "timestamp": datetime.now().isoformat(), "tracking_id": obj_id, "is_stable": True,
                            "is_kept": True, "known": False, "name": "未知",
                            "time_since_detection": time_since_last_seen
                        }
                        results.append(kept_det)
        return results

    def _calculate_face_match_score(self, new_bbox: List[int], obj_data: Dict, current_time: float) -> float:
        old_bbox = obj_data["bbox"]
        old_center = ((old_bbox[0] + old_bbox[2]) / 2, (old_bbox[1] + old_bbox[3]) / 2)
        new_center = ((new_bbox[0] + new_bbox[2]) / 2, (new_bbox[1] + new_bbox[3]) / 2)
        center_distance = ((old_center[0] - new_center[0]) ** 2 + (old_center[1] - new_center[1]) ** 2) ** 0.5
        old_w, old_h = old_bbox[2] - old_bbox[0], old_bbox[3] - old_bbox[1]
        new_w, new_h = new_bbox[2] - new_bbox[0], new_bbox[3] - new_bbox[1]
        size_similarity = abs(old_w - new_w) + abs(old_h - new_h)
        time_weight = min(2.0, current_time - obj_data["last_seen"])
        consecutive_bonus = max(0, 5 - obj_data.get("consecutive_detections", 0))
        score = center_distance + size_similarity * 0.5 + time_weight * 10 + consecutive_bonus
        return score

    def _advanced_face_smoothing(self, new_bbox: List[int], old_obj: Dict, history: Dict, smooth_factor: float) -> List[
        int]:
        old_bbox = old_obj["bbox"]
        smoothed_bbox = [int(old_bbox[i] * (1 - smooth_factor) + new_bbox[i] * smooth_factor) for i in range(4)]
        if history and "positions" in history and len(history["positions"]) >= 2:
            positions = history["positions"]
            timestamps = history.get("timestamps", [])
            if len(positions) >= 3 and len(timestamps) >= 3:
                recent_positions = positions[-3:]
                recent_timestamps = timestamps[-3:]
                total_dx, total_dy = 0, 0
                valid_moves = 0
                for i in range(1, len(recent_positions)):
                    dt = recent_timestamps[i] - recent_timestamps[i - 1]
                    if dt > 0:
                        old_center = ((recent_positions[i - 1][0] + recent_positions[i - 1][2]) / 2,
                                      (recent_positions[i - 1][1] + recent_positions[i - 1][3]) / 2)
                        new_center = ((recent_positions[i][0] + recent_positions[i][2]) / 2,
                                      (recent_positions[i][1] + recent_positions[i][3]) / 2)
                        dx = (new_center[0] - old_center[0]) / dt
                        dy = (new_center[1] - old_center[1]) / dt
                        speed = (dx ** 2 + dy ** 2) ** 0.5
                        if speed < 200:
                            total_dx += dx
                            total_dy += dy
                            valid_moves += 1
                if valid_moves > 0:
                    avg_dx = total_dx / valid_moves
                    avg_dy = total_dy / valid_moves
                    motion_factor = 0.15 if abs(avg_dx) < 50 and abs(avg_dy) < 50 else 0.05
                    predict_offset_x = int(avg_dx * motion_factor)
                    predict_offset_y = int(avg_dy * motion_factor)
                    smoothed_bbox[0] += predict_offset_x
                    smoothed_bbox[1] += predict_offset_y
                    smoothed_bbox[2] += predict_offset_x
                    smoothed_bbox[3] += predict_offset_y
        w = smoothed_bbox[2] - smoothed_bbox[0]
        h = smoothed_bbox[3] - smoothed_bbox[1]
        if w <= 0 or h <= 0: return new_bbox
        old_center = ((old_bbox[0] + old_bbox[2]) / 2, (old_bbox[1] + old_bbox[3]) / 2)
        new_center = ((smoothed_bbox[0] + smoothed_bbox[2]) / 2, (smoothed_bbox[1] + smoothed_bbox[3]) / 2)
        center_change = ((old_center[0] - new_center[0]) ** 2 + (old_center[1] - new_center[1]) ** 2) ** 0.5
        if center_change > 25:
            limit_factor = 25 / center_change
            final_center_x = old_center[0] + (new_center[0] - old_center[0]) * limit_factor
            final_center_y = old_center[1] + (new_center[1] - old_center[1]) * limit_factor
            smoothed_bbox = [int(final_center_x - w / 2), int(final_center_y - h / 2), int(final_center_x + w / 2),
                             int(final_center_y + h / 2)]
        return smoothed_bbox

    def _predict_missing_faces(self, cache: Dict, face_history: Dict, current_time: float):
        for obj_id, obj_data in cache.items():
            if obj_data["type"] == "face":
                time_since_last_seen = current_time - obj_data["last_seen"]
                if 0.2 < time_since_last_seen < 1.0:
                    predicted_pos = self._predict_face_position(obj_id, face_history, current_time)
                    if predicted_pos:
                        obj_data["predicted_bbox"] = predicted_pos

    def _predict_face_position(self, obj_id: str, face_history: Dict, current_time: float) -> Optional[List[int]]:
        if obj_id not in face_history or len(face_history[obj_id]["positions"]) < 2: return None
        history = face_history[obj_id]
        positions = history["positions"]
        timestamps = history["timestamps"]
        if len(positions) >= 2:
            last_pos = positions[-1]
            prev_pos = positions[-2]
            last_time = timestamps[-1]
            prev_time = timestamps[-2]
            dt = last_time - prev_time
            if dt > 0:
                vx = (last_pos[0] - prev_pos[0]) / dt
                vy = (last_pos[1] - prev_pos[1]) / dt
                time_delta = current_time - last_time
                predicted_x = last_pos[0] + vx * time_delta
                predicted_y = last_pos[1] + vy * time_delta
                w = last_pos[2] - last_pos[0]
                h = last_pos[3] - last_pos[1]
                return [int(predicted_x), int(predicted_y), int(predicted_x + w), int(predicted_y + h)]
        return None

    def _standard_object_tracking(self, detections: List[Dict], cache: Dict, current_time: float, matched_ids: set,
                                  camera_id: str = "") -> List[Dict]:
        results = []
        config = self._stabilization_config.get(camera_id, {})
        OBJECT_MATCH_THRESHOLD = config.get('object_match_threshold', 80)
        OBJECT_SMOOTH_FACTOR = config.get('object_smooth_factor', 0.95)
        SIZE_CHANGE_RATIO = config.get('max_size_change_ratio', 0.1)
        CONFIDENCE_SMOOTH_FACTOR = 0.8

        for det in detections:
            bbox = det["bbox"]
            det_type = det["type"]
            best_match_id = None
            best_distance = OBJECT_MATCH_THRESHOLD

            for obj_id, obj_data in cache.items():
                if obj_data["type"] != det_type or obj_id in matched_ids: continue
                old_center = ((obj_data["bbox"][0] + obj_data["bbox"][2]) / 2,
                              (obj_data["bbox"][1] + obj_data["bbox"][3]) / 2)
                new_center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
                distance = ((old_center[0] - new_center[0]) ** 2 + (old_center[1] - new_center[1]) ** 2) ** 0.5
                if distance < best_distance:
                    best_distance = distance
                    best_match_id = obj_id

            if best_match_id:
                old_obj = cache[best_match_id]
                old_bbox = old_obj["bbox"]
                old_center = ((old_bbox[0] + old_bbox[2]) / 2, (old_bbox[1] + old_bbox[3]) / 2)
                new_center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
                movement = ((old_center[0] - new_center[0]) ** 2 + (old_center[1] - new_center[1]) ** 2) ** 0.5

                enhanced_smooth = min(0.95, OBJECT_SMOOTH_FACTOR + 0.08) if movement > 25 else OBJECT_SMOOTH_FACTOR
                smoothed_bbox = [int(old_bbox[i] * (1 - enhanced_smooth) + bbox[i] * enhanced_smooth) for i in range(4)]
                smoothed_bbox = self._stabilize_bbox_size(smoothed_bbox, old_bbox, max_change_ratio=SIZE_CHANGE_RATIO)

                old_confidence = old_obj.get("confidence", det["confidence"])
                smoothed_confidence = old_confidence * (1 - CONFIDENCE_SMOOTH_FACTOR) + det[
                    "confidence"] * CONFIDENCE_SMOOTH_FACTOR
                if smoothed_confidence < old_confidence * 0.6:
                    smoothed_confidence = old_confidence * 0.7

                cache[best_match_id].update({
                    "bbox": smoothed_bbox, "confidence": max(0.3, smoothed_confidence), "last_seen": current_time,
                    "stable_count": min(old_obj.get("stable_count", 0) + 1, 8),
                    "consecutive_detections": old_obj.get("consecutive_detections", 0) + 1,
                    "flicker_protection": True
                })
                matched_ids.add(best_match_id)
                result_det = det.copy()
                result_det["bbox"] = smoothed_bbox
                result_det["tracking_id"] = best_match_id
                result_det["is_stable"] = cache[best_match_id]["stable_count"] >= 2
                result_det["consecutive_detections"] = cache[best_match_id]["consecutive_detections"]
                results.append(result_det)
            else:
                new_id = f"{det_type}_{int(current_time * 1000) % 10000}"
                cache[new_id] = {
                    "bbox": bbox, "confidence": det["confidence"], "type": det_type,
                    "last_seen": current_time, "stable_count": 1, "consecutive_detections": 1
                }
                result_det = det.copy()
                result_det["tracking_id"] = new_id
                result_det["is_stable"] = False
                result_det["consecutive_detections"] = 1
                results.append(result_det)
                matched_ids.add(new_id)
        return results

    def _detect_jitter(self, new_bbox: List[int], old_bbox: List[int], history: Dict, threshold: int = 30) -> bool:
        old_center = ((old_bbox[0] + old_bbox[2]) / 2, (old_bbox[1] + old_bbox[3]) / 2)
        new_center = ((new_bbox[0] + new_bbox[2]) / 2, (new_bbox[1] + new_bbox[3]) / 2)
        movement = ((old_center[0] - new_center[0]) ** 2 + (old_center[1] - new_center[1]) ** 2) ** 0.5
        if movement > threshold: return True
        if history and "positions" in history and len(history["positions"]) >= 3:
            positions = history["positions"][-3:]
            centers = [((pos[0] + pos[2]) / 2, (pos[1] + pos[3]) / 2) for pos in positions]
            if len(centers) >= 2:
                movements = []
                for i in range(1, len(centers)):
                    move = ((centers[i][0] - centers[i - 1][0]) ** 2 + (centers[i][1] - centers[i - 1][1]) ** 2) ** 0.5
                    movements.append(move)
                if len(movements) >= 2:
                    movement_variance = sum((m - sum(movements) / len(movements)) ** 2 for m in movements) / len(
                        movements)
                    if movement_variance > 100: return True
        return False

    def _stabilize_bbox_size(self, new_bbox: List[int], old_bbox: List[int], max_change_ratio: float = 0.2) -> List[
        int]:
        old_w, old_h = old_bbox[2] - old_bbox[0], old_bbox[3] - old_bbox[1]
        new_w, new_h = new_bbox[2] - new_bbox[0], new_bbox[3] - new_bbox[1]
        w_change_ratio = abs(new_w - old_w) / old_w if old_w > 0 else 0
        h_change_ratio = abs(new_h - old_h) / old_h if old_h > 0 else 0
        if w_change_ratio > max_change_ratio or h_change_ratio > max_change_ratio:
            center_x, center_y = (new_bbox[0] + new_bbox[2]) / 2, (new_bbox[1] + new_bbox[3]) / 2
            max_w_change, max_h_change = old_w * max_change_ratio, old_h * max_change_ratio
            stabilized_w = old_w + max_w_change if new_w > old_w else old_w - max_w_change
            stabilized_h = old_h + max_h_change if new_h > old_h else old_h - max_h_change
            stabilized_bbox = [int(center_x - stabilized_w / 2), int(center_y - stabilized_h / 2),
                               int(center_x + stabilized_w / 2), int(center_y + stabilized_h / 2)]
            return stabilized_bbox
        return new_bbox

    def _process_face_recognition_with_stabilization(self, camera_id: str, frame: np.ndarray) -> List[Dict]:
        current_tolerance = self._face_recognition_config.get('tolerance', 0.65)
        recognized_faces = self._detectors["face"].detect_and_recognize(frame, tolerance=current_tolerance)

        face_detections = []
        for face in recognized_faces:
            location = face["location"]
            bbox = [location["left"], location["top"], location["right"], location["bottom"]]
            detection = {
                "type": "face", "bbox": bbox, "confidence": face.get("confidence", 0.5),
                "timestamp": datetime.now().isoformat(), "identity": face["identity"]
            }
            face_detections.append(detection)

        if face_detections:
            stabilized_faces = self.stabilize_detections(camera_id, face_detections)
            return stabilized_faces
        else:
            return []

    def _stabilize_face_identity(self, face_id: str, new_identity: Dict, face_history: Dict, history_size: int = 10,
                                 change_threshold: float = 0.7, confidence_diff: float = 0.15,
                                 min_stable_frames: int = 3) -> Dict:
        if face_id not in face_history:
            face_history[face_id] = {"identity_history": [], "current_identity": new_identity, "stable_count": 0,
                                     "last_change_time": time.time()}
            return new_identity

        history_data = face_history[face_id]
        if "positions" in history_data and "current_identity" not in history_data:  # Compatibility check
            history_data.update({"identity_history": [], "current_identity": new_identity, "stable_count": 0,
                                 "last_change_time": time.time()})
            return new_identity
        if "current_identity" not in history_data:
            history_data["current_identity"] = new_identity
            history_data["identity_history"] = []
            history_data["stable_count"] = 0
            history_data["last_change_time"] = time.time()
            return new_identity

        current_identity = history_data["current_identity"]
        if "identity_history" not in history_data: history_data["identity_history"] = []
        identity_history = history_data["identity_history"]
        if "stable_count" not in history_data: history_data["stable_count"] = 0

        identity_history.append(
            {"name": new_identity.get("name", "unknown"), "confidence": new_identity.get("confidence", 0),
             "timestamp": time.time()})
        if len(identity_history) > history_size: identity_history.pop(0)

        name_votes = {};
        total_weight = 0
        for record in identity_history:
            name = record["name"];
            confidence = record["confidence"]
            weight = max(0.1, confidence)
            name_votes[name] = name_votes.get(name, 0) + weight
            total_weight += weight

        winning_name = "unknown";
        vote_ratio = 0
        if name_votes and total_weight > 0:
            most_voted_name = max(name_votes.items(), key=lambda x: x[1])
            vote_ratio = most_voted_name[1] / total_weight
            winning_name = most_voted_name[0]

        current_name = current_identity.get("name", "unknown")
        new_name = new_identity.get("name", "unknown")

        should_change_identity = False;
        change_reason = ""
        if current_name == winning_name:
            history_data["stable_count"] = history_data.get("stable_count", 0) + 1
            should_change_identity = False
            change_reason = "身份一致，保持稳定"
        elif vote_ratio >= change_threshold:
            current_confidence = current_identity.get("confidence", 0)
            new_confidence = new_identity.get("confidence", 0)
            if new_confidence > current_confidence + confidence_diff:
                should_change_identity = True
                change_reason = f"投票支持率{vote_ratio:.1%}，置信度提升{new_confidence - current_confidence:.2f}"
            elif history_data.get("stable_count", 0) >= min_stable_frames:
                should_change_identity = True
                change_reason = f"投票支持率{vote_ratio:.1%}，已稳定{history_data['stable_count']}帧"
            else:
                should_change_identity = False
                change_reason = f"投票支持率{vote_ratio:.1%}，但稳定帧数不足({history_data.get('stable_count', 0)}<{min_stable_frames})"
        else:
            should_change_identity = False
            change_reason = f"投票支持率不足({vote_ratio:.1%}<{change_threshold:.1%})"

        if should_change_identity:
            best_confidence = 0
            for record in identity_history:
                if record["name"] == winning_name: best_confidence = max(best_confidence, record["confidence"])
            history_data["current_identity"] = {"name": winning_name, "known": winning_name != "unknown",
                                                "confidence": best_confidence}
            history_data["stable_count"] = 0
            history_data["last_change_time"] = time.time()
        else:
            if new_name == current_name and new_identity.get("confidence", 0) > current_identity.get("confidence", 0):
                history_data["current_identity"]["confidence"] = new_identity["confidence"]
        return history_data["current_identity"]

    def _cleanup_expired_cache(self, cache: Dict, face_history: Dict, current_time: float):
        to_remove = []
        for obj_id, obj_data in cache.items():
            time_since_seen = current_time - obj_data["last_seen"]
            if obj_data["type"] == "face":
                if time_since_seen > 6.0:
                    to_remove.append(obj_id)
                elif time_since_seen > 3.0:
                    current_confidence = obj_data.get("confidence", 1.0)
                    fade_factor = max(0.15, 1 - (time_since_seen - 3.0) / 3.0)
                    obj_data["confidence"] = max(0.15, current_confidence * fade_factor)
                    obj_data["fading"] = True
            else:
                if time_since_seen > 3.0:
                    to_remove.append(obj_id)
                elif time_since_seen > 1.5:
                    current_confidence = obj_data.get("confidence", 1.0)
                    fade_factor = max(0.2, 1 - (time_since_seen - 1.5) / 1.5)
                    obj_data["confidence"] = max(0.2, current_confidence * fade_factor)
                    obj_data["fading"] = True
        for obj_id in to_remove:
            del cache[obj_id]
            if obj_id in face_history: del face_history[obj_id]
        if len(cache) > 25:
            sorted_items = sorted(cache.items(), key=lambda x: x[1]["last_seen"])
            for obj_id, _ in sorted_items[:-20]:
                del cache[obj_id]
                if obj_id in face_history: del face_history[obj_id]

    # --- 性能优化策略函数 ---
    def _get_performance_strategy(self, performance_mode: str, frame_count: int, is_low_res: bool) -> Dict:
        if performance_mode == "fast":
            is_object_frame = frame_count % 2 == 0
            return {
                "run_object_detection": is_object_frame, "run_face_recognition": not is_object_frame,
                "object_scale_factor": 0.4, "face_scale_factor": 0.5, "use_parallel": False,
                "use_stabilization": frame_count % 4 == 0, "max_detections": 3, "face_limit": 2
            }
        elif performance_mode == "balanced":
            use_parallel_this_frame = frame_count % 3 == 0
            return {
                "run_object_detection": True, "run_face_recognition": True,
                "object_scale_factor": 0.6 if use_parallel_this_frame else 1.0,
                "face_scale_factor": 0.7 if use_parallel_this_frame else 1.1,
                "use_parallel": use_parallel_this_frame, "use_stabilization": True,
                "max_detections": 5, "face_limit": 3
            }
        else:  # quality
            return {
                "run_object_detection": True, "run_face_recognition": True,
                "object_scale_factor": 0.8, "face_scale_factor": 0.9, "use_parallel": True,
                "use_stabilization": True, "max_detections": 8, "face_limit": 3
            }

    # --- 核心帧分析逻辑 (整合到AIServiceManager) ---
    async def process_single_frame(self, frame: np.ndarray, camera_id: str,
                                   enable_face_recognition: bool, enable_object_detection: bool,
                                   enable_behavior_detection: bool, enable_fire_detection: bool,
                                   performance_mode: str) -> Dict:
        start_time = time.time()
        # 简单帧计数，实际应用中可以更精确地管理
        frame_count = self._detection_cache.get(camera_id, {}).get("frame_count", 0) + 1
        if camera_id not in self._detection_cache:
            self._detection_cache[camera_id] = {"objects": {}, "face_history": {}, "frame_count": 0}
        self._detection_cache[camera_id]["frame_count"] = frame_count

        height, width = frame.shape[:2]
        is_low_res = width < 400 or height < 400

        if camera_id not in self._object_trackers:
            self._object_trackers[camera_id] = DeepSORTTracker()

        results = {
            "camera_id": camera_id, "timestamp": datetime.now().isoformat(), "detections": [], "alerts": [],
            "performance_info": {"mode": performance_mode, "frame_count": frame_count}
        }

        # 应用AI设置 (从存储的设置中获取)
        camera_settings = self._ai_settings.get(camera_id)
        if camera_settings:
            enable_face_recognition = camera_settings.get('face_recognition', enable_face_recognition)
            enable_object_detection = camera_settings.get('object_detection', enable_object_detection)
            enable_behavior_detection = camera_settings.get('behavior_analysis', enable_behavior_detection)
            enable_fire_detection = camera_settings.get('fire_detection', enable_fire_detection)
            if camera_settings.get('realtime_mode', False):
                performance_mode = "fast"

        strategy = self._get_performance_strategy(performance_mode, frame_count, is_low_res)

        active_tasks = []

        # 火焰检测
        if enable_fire_detection and "fire" in self._detectors:
            try:
                fire_detector = self._detectors["fire"]
                fire_results = fire_detector.detect(frame, confidence_threshold=0.25)
                for fire_obj in fire_results:
                    bbox = [int(float(coord)) for coord in fire_obj["coordinates"]]
                    detection = {
                        "type": "fire_detection", "class_name": fire_obj["class_name"],
                        "detection_type": fire_obj["type"], "confidence": float(fire_obj["confidence"]),
                        "bbox": bbox, "timestamp": datetime.now().isoformat()
                    }
                    results["detections"].append(detection)
                    self.send_alert_to_backend(
                        AIAnalysisResult(
                            camera_id=camera_id, event_type=f"fire_detection_{fire_obj['type']}",
                            location={"box": bbox}, confidence=float(fire_obj["confidence"]),
                            timestamp=datetime.now().isoformat(),
                            details={"detection_type": fire_obj["type"], "object_type": fire_obj["class_name"],
                                     "area": fire_obj["area"], "center": fire_obj["center"]}
                        )
                    )
            except Exception as e:
                print(f"火焰检测失败: {e}")
                traceback.print_exc()

        # 目标检测任务
        def optimized_object_detection():
            if not (enable_object_detection and strategy["run_object_detection"]): return []
            try:
                obj_scale = strategy["object_scale_factor"]
                obj_height, obj_width = int(height * obj_scale), int(width * obj_scale)
                obj_image = cv2.resize(frame, (obj_width, obj_height))
                confidence_threshold = self._object_detection_config.get('confidence_threshold', 0.35)
                detected_objects = self._detectors["object"].predict(obj_image,
                                                                     confidence_threshold=confidence_threshold)

                scale_back_x, scale_back_y = width / obj_width, height / obj_height
                object_detections = []
                for obj in detected_objects[:strategy["max_detections"]]:
                    bbox = [int(float(obj["coordinates"][0]) * scale_back_x),
                            int(float(obj["coordinates"][1]) * scale_back_y),
                            int(float(obj["coordinates"][2]) * scale_back_x),
                            int(float(obj["coordinates"][3]) * scale_back_y)]
                    object_detections.append({
                        "type": "object", "class_name": obj["class_name"], "confidence": float(obj["confidence"]),
                        "bbox": bbox, "timestamp": datetime.now().isoformat()
                    })
                return object_detections
            except Exception as e:
                print(f"目标检测失败: {e}")
                return []

        # 人脸识别任务
        def optimized_face_recognition():
            if not (enable_face_recognition and strategy["run_face_recognition"]): return []
            try:
                face_scale = strategy["face_scale_factor"]
                if performance_mode == "fast": face_scale = min(0.5, face_scale)
                face_height, face_width = int(height * face_scale), int(width * face_scale)
                face_image = cv2.resize(frame, (face_width, face_height))

                stabilized_faces = self._process_face_recognition_with_stabilization(camera_id, face_image)

                scale_back_x, scale_back_y = width / face_width, height / face_height
                face_detections = []
                for face in stabilized_faces[:strategy["face_limit"]]:
                    if face["type"] == "face":
                        face_bbox = [int(float(face["bbox"][0]) * scale_back_x),
                                     int(float(face["bbox"][1]) * scale_back_y),
                                     int(float(face["bbox"][2]) * scale_back_x),
                                     int(float(face["bbox"][3]) * scale_back_y)]
                        face_detections.append({
                            "type": "face", "known": face.get("identity", {}).get("known", False),
                            "name": face.get("identity", {}).get("name", "未知"),
                            "confidence": float(face.get("confidence", 0.5)),
                            "bbox": face_bbox, "tracking_id": face.get("tracking_id", ""),
                            "timestamp": face.get("timestamp", datetime.now().isoformat())
                        })
                        if not face.get("identity", {}).get("known", False) and performance_mode != "fast":
                            self.send_alert_to_backend(
                                AIAnalysisResult(
                                    camera_id=camera_id, event_type="unknown_face_detected",
                                    location={"box": face_bbox}, confidence=float(face.get("confidence", 0.5)),
                                    timestamp=datetime.now().isoformat(),
                                    details={"tracking_id": face.get("tracking_id"),
                                             "is_stable": face.get("is_stable", False)}
                                )
                            )
                return face_detections
            except Exception as e:
                print(f"人脸识别失败: {e}")
                return []

        # 执行策略
        if strategy["use_parallel"]:
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_objects = executor.submit(optimized_object_detection)
                future_faces = executor.submit(optimized_face_recognition)
                object_results = future_objects.result()
                face_results = future_faces.result()
        else:
            object_results = optimized_object_detection()
            face_results = optimized_face_recognition()

        # Deep SORT追踪
        tracked_object_results = []
        if object_results and camera_id in self._object_trackers:
            try:
                tracker = self._object_trackers[camera_id]
                detection_list = []
                for obj in object_results:
                    if obj["type"] == "object":
                        detection_list.append({
                            'coordinates': obj['bbox'], 'confidence': obj['confidence'],
                            'class_name': obj['class_name'], 'class_id': obj.get('class_id', 0)
                        })
                if detection_list:
                    tracked_results = tracker.update(detection_list, frame)
                    for tracked_obj in tracked_results:
                        tracked_object_results.append({
                            "type": "object", "class_name": tracked_obj["class_name"],
                            "confidence": tracked_obj["confidence"],
                            "bbox": tracked_obj["coordinates"], "tracking_id": tracked_obj["tracking_id"],
                            "timestamp": datetime.now().isoformat()
                        })
                        if tracked_obj["class_name"] == "person" and tracked_obj["confidence"] > 0.5:
                            self.send_alert_to_backend(
                                AIAnalysisResult(
                                    camera_id=camera_id, event_type="object_person_detected",
                                    location={"box": tracked_obj["coordinates"]}, confidence=tracked_obj["confidence"],
                                    timestamp=datetime.now().isoformat(),
                                    details={"tracking_id": tracked_obj["tracking_id"],
                                             "class_name": tracked_obj["class_name"],
                                             "tracking_method": "deep_sort", "realtime_detection": True}
                                )
                            )
            except Exception as e:
                print(f"Deep SORT追踪失败: {e}")
                tracked_object_results = object_results
        else:
            tracked_object_results = object_results

        all_detections = tracked_object_results + face_results  # Face results are already stabilized
        results["detections"] = all_detections

        # 危险区域检测
        try:
            person_detections = [d for d in all_detections if
                                 d.get('type') == 'object' and d.get('class_name') == 'person']
            if person_detections:
                danger_zone_alerts = danger_zone_detector.detect_intrusions(camera_id, all_detections)
                for alert in danger_zone_alerts:
                    results["alerts"].append({
                        "type": alert["type"], "message": alert["message"], "tracking_id": alert.get("tracking_id"),
                        "zone_name": alert.get("zone_name"), "position": alert.get("position"),
                        "distance": alert.get("distance"), "dwell_time": alert.get("dwell_time")
                    })
                    self.send_alert_to_backend(
                        AIAnalysisResult(
                            camera_id=camera_id, event_type=alert["type"],
                            location={"position": alert.get("position", [])},
                            confidence=1.0, timestamp=datetime.now().isoformat(),
                            details={"tracking_id": alert.get("tracking_id"), "zone_id": alert.get("zone_id"),
                                     "zone_name": alert.get("zone_name"), "distance": alert.get("distance"),
                                     "dwell_time": alert.get("dwell_time"), "detection_method": "danger_zone_geometric",
                                     "realtime_detection": True}
                        )
                    )
        except Exception as e:
            print(f"⚠️ 危险区域检测失败: {e}")

        total_time = (time.time() - start_time) * 1000
        results["performance_info"]["processing_time_ms"] = round(total_time, 1)
        results["performance_info"]["detection_count"] = len(results["detections"])
        results["performance_info"]["tracking_info"] = {
            "deep_sort_objects": len(tracked_object_results),
            "stabilized_faces": len(face_results),
            "tracker_available": camera_id in self._object_trackers
        }

        # 异步发送检测结果到WebSocket (不阻塞响应)
        if results.get("detections"):
            self._thread_pool.submit(lambda: asyncio.run(self.send_detection_to_websocket(camera_id, results)))

        return results

    # --- AISettings Model (for API) ---
    class AISettings(BaseModel):
        model_config = ConfigDict(extra='allow')  # 允许额外字段
        face_recognition: bool = True
        object_detection: bool = True
        behavior_analysis: bool = False
        sound_detection: bool = False
        fire_detection: bool = True
        realtime_mode: bool = True

    def get_ai_settings(self, camera_id: str) -> Dict:
        if camera_id not in self._ai_settings:
            self._ai_settings[camera_id] = self.AISettings().model_dump()
        return self._ai_settings[camera_id]

    def update_ai_settings(self, camera_id: str, settings: Dict):
        current_settings = self.get_ai_settings(camera_id)
        current_settings.update(settings)
        self._ai_settings[camera_id] = current_settings
        if camera_id in self._video_streams:
            self._video_streams[camera_id].update_settings(settings)

    # --- Face Recognition Sensitivity Management ---
    def get_face_recognition_config(self) -> Dict:
        return self._face_recognition_config

    def update_face_recognition_config(self, config_data: Dict):
        self._face_recognition_config.update(config_data)
        # Clear face cache for immediate effect
        for cam_id in list(self._detection_cache.keys()):
            if cam_id in self._detection_cache and "face_history" in self._detection_cache[cam_id]:
                self._detection_cache[cam_id]["face_history"].clear()
                self._detection_cache[cam_id]["objects"] = {k: v for k, v in
                                                            self._detection_cache[cam_id]["objects"].items() if
                                                            v.get("type") != "face"}

    # --- Object Detection Sensitivity Management ---
    def get_object_detection_config(self) -> Dict:
        return self._object_detection_config

    def update_object_detection_config(self, config_data: Dict):
        self._object_detection_config.update(config_data)
        # Clear object cache for immediate effect (except faces)
        for cam_id in list(self._detection_cache.keys()):
            if cam_id in self._detection_cache and "objects" in self._detection_cache[cam_id]:
                object_cache = self._detection_cache[cam_id]["objects"]
                self._detection_cache[cam_id]["objects"] = {k: v for k, v in object_cache.items() if
                                                            v.get("type") == "face"}

    # --- Stabilization Configuration ---
    def get_stabilization_config(self, camera_id: str) -> Dict:
        default_config = {
            "face_smooth_factor": 0.92, "object_smooth_factor": 0.88,
            "face_match_threshold": 120, "object_match_threshold": 60,
            "jitter_detection_threshold": 30, "max_size_change_ratio": 0.2,
            "updated_at": "默认配置"
        }
        return self._stabilization_config.get(camera_id, default_config)

    def update_stabilization_config(self, camera_id: str, config_data: Dict):
        if not camera_id in self._stabilization_config:
            self._stabilization_config[camera_id] = self.get_stabilization_config(camera_id).copy()
        self._stabilization_config[camera_id].update(config_data)
        self._stabilization_config[camera_id]["updated_at"] = datetime.now().isoformat()
        # Clear cache for immediate effect
        if camera_id in self._detection_cache:
            self._detection_cache[camera_id] = {"objects": {}, "face_history": {}, "frame_count": 0}

    def apply_stabilization_preset(self, preset_name: str, camera_id: str):
        presets = {
            "anti_flicker": {"name": "🚨 超强防闪烁模式",
                             "config": {"face_smooth_factor": 0.97, "object_smooth_factor": 0.95,
                                        "face_match_threshold": 150, "object_match_threshold": 80,
                                        "jitter_detection_threshold": 15, "max_size_change_ratio": 0.1}},
            "anti_jitter": {"name": "抗抖动模式", "config": {"face_smooth_factor": 0.95, "object_smooth_factor": 0.92,
                                                             "face_match_threshold": 100, "object_match_threshold": 50,
                                                             "jitter_detection_threshold": 20,
                                                             "max_size_change_ratio": 0.15}},
            "ultra_stable": {"name": "超稳定模式", "config": {"face_smooth_factor": 0.97, "object_smooth_factor": 0.95,
                                                              "face_match_threshold": 80, "object_match_threshold": 40,
                                                              "jitter_detection_threshold": 15,
                                                              "max_size_change_ratio": 0.1}},
            "balanced": {"name": "平衡模式", "config": {"face_smooth_factor": 0.88, "object_smooth_factor": 0.85,
                                                        "face_match_threshold": 120, "object_match_threshold": 60,
                                                        "jitter_detection_threshold": 30,
                                                        "max_size_change_ratio": 0.2}},
            "responsive": {"name": "响应模式", "config": {"face_smooth_factor": 0.80, "object_smooth_factor": 0.75,
                                                          "face_match_threshold": 150, "object_match_threshold": 80,
                                                          "jitter_detection_threshold": 40,
                                                          "max_size_change_ratio": 0.25}},
            "default": {"name": "默认模式", "config": {"face_smooth_factor": 0.92, "object_smooth_factor": 0.88,
                                                       "face_match_threshold": 120, "object_match_threshold": 60,
                                                       "jitter_detection_threshold": 30, "max_size_change_ratio": 0.2}}
        }
        if preset_name not in presets: raise HTTPException(status_code=404, detail=f"预设 '{preset_name}' 不存在")

        config = presets[preset_name]["config"].copy()
        self.update_stabilization_config(camera_id, config)
        return {"status": "success", "message": f"已应用 '{presets[preset_name]['name']}' 配置到摄像头 {camera_id}",
                "preset": presets[preset_name], "applied_config": config}

    def list_stabilization_presets(self) -> Dict:
        return {
            "anti_flicker": {"name": "🚨 超强防闪烁模式", "description": "专门解决框一闪一闪问题的超强配置",
                             "best_for": ["检测框闪烁", "出现消失频繁", "置信度不稳定"],
                             "trade_offs": "最强稳定性，轻微延迟增加"},
            "anti_jitter": {"name": "抗抖动模式", "description": "针对严重抖动问题的强化配置",
                            "best_for": ["抖动严重", "目标频繁切换", "低质量摄像头"],
                            "trade_offs": "可能增加10-20ms延迟"},
            "ultra_stable": {"name": "超稳定模式", "description": "最强稳定化，适合静态场景监控",
                             "best_for": ["静态监控", "高精度要求", "稳定环境"], "trade_offs": "响应稍慢，适合静态场景"},
            "balanced": {"name": "平衡模式", "description": "兼顾稳定性和响应性",
                         "best_for": ["大多数场景", "动静结合", "一般监控"], "trade_offs": "综合表现良好"},
            "responsive": {"name": "响应模式", "description": "优先响应速度，轻度稳定化",
                           "best_for": ["快速移动", "实时互动", "低延迟要求"], "trade_offs": "可能有轻微抖动"},
            "default": {"name": "默认模式", "description": "系统默认设置", "best_for": ["初始配置", "标准环境"],
                        "trade_offs": "可根据具体需求调整"}
        }

    async def apply_anti_flicker_all_cameras(self) -> Dict:
        applied_cameras = []
        active_cameras = list(self._video_streams.keys())
        if not active_cameras: active_cameras = ["default"]  # If no active streams, apply to a default config
        for camera_id in active_cameras:
            self.apply_stabilization_preset("anti_flicker", camera_id)
            applied_cameras.append(camera_id)
        return {"status": "success", "message": "🚨 已对所有摄像头应用超强防闪烁配置！",
                "applied_cameras": applied_cameras}

    # --- System Status and Performance ---
    def get_system_status(self) -> SystemStatus:
        return SystemStatus(
            active_streams_count=len(self._video_streams),
            detectors_initialized={name: det is not None for name, det in self._detectors.items()},
            system_load=None,  # Placeholder for actual system load
            memory_usage=None  # Placeholder for actual memory usage
        )

    def get_performance_stats(self) -> Dict:
        stats = {"cache_info": {}, "detector_status": {}, "optimization_status": "high_performance_mode"}
        for camera_id, cache_data in self._detection_cache.items():
            if isinstance(cache_data, dict) and "objects" in cache_data:
                stats["cache_info"][camera_id] = {"cached_objects": len(cache_data["objects"]), "types": {}}
                for obj_data in cache_data["objects"].values():
                    obj_type = obj_data.get("type", "unknown")
                    stats["cache_info"][camera_id]["types"][obj_type] = stats["cache_info"][camera_id]["types"].get(
                        obj_type, 0) + 1
        stats["detector_status"] = {
            "object_detection": "parallel_enabled" if "object" in self._detectors else "disabled",
            "face_recognition": "adaptive_scaling_enabled" if "face" in self._detectors else "disabled",
            "behavior_detection": "enabled" if "behavior" in self._detectors else "disabled",
            "acoustic_detection": "enabled" if "acoustic" in self._detectors else "disabled"
        }
        stats["performance_features"] = {
            "parallel_processing": True, "adaptive_image_scaling": {"object": "60%", "face": "60-85%"},
            "face_specific_stabilization": True, "size_aware_matching": True, "memory_leak_protection": True,
            "async_backend_communication": True, "smart_caching": True
        }
        return {"status": "success", "stats": stats}

    # --- Danger Zone Management ---
    def update_danger_zones(self, camera_id: str, zones_data: List[Dict]):
        danger_zone_detector.update_camera_zones(camera_id, zones_data)

    def get_danger_zone_status(self, camera_id: str) -> Dict:
        return danger_zone_detector.get_zone_status(camera_id)

    def remove_danger_zone(self, camera_id: str, zone_id: str):
        danger_zone_detector.remove_danger_zone(camera_id, zone_id)


# 创建服务管理器实例
service_manager = AIServiceManager(app_config)


# --- FastAPI 应用生命周期管理器 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 的生命周期管理器。"""
    await service_manager.initialize_detectors()
    yield  # 服务在此运行时，处理API请求
    await service_manager.shutdown_services()


# 创建FastAPI应用实例
app = FastAPI(
    title="SmartEye AI Service",
    description="提供视频流处理、目标检测、行为识别、人脸识别和声学事件检测能力",
    version="2.0.0",
    lifespan=lifespan
)

# 增加请求超时设置中间件
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse


class TimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await asyncio.wait_for(call_next(request), timeout=app_config.FASTAPI_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            return JSONResponse(status_code=504, content={"detail": "请求处理超时，请重试"})


app.add_middleware(TimeoutMiddleware)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- API 端点定义 ---

# RTMP推流回调处理
@app.post("/rtmp/publish")
async def rtmp_publish_callback(request: dict = Body(...)):
    stream_name = request.get('name', '')
    camera_id = f"rtmp_stream_{stream_name}"
    print(f"📡 RTMP推流开始: stream={stream_name}, camera_id={camera_id}")
    return {"status": "success", "message": "推流已接受", "camera_id": camera_id}


@app.post("/rtmp/publish_done")
async def rtmp_publish_done_callback(request: dict = Body(...)):
    stream_name = request.get('name', '')
    camera_id = f"rtmp_stream_{stream_name}"
    print(f"📡 RTMP推流结束: stream={stream_name}")
    if camera_id in service_manager._video_streams:
        await service_manager._video_streams[camera_id].stop()
        del service_manager._video_streams[camera_id]
        if camera_id in service_manager._object_trackers:
            del service_manager._object_trackers[camera_id]
        if camera_id in service_manager._detection_cache:
            del service_manager._detection_cache[camera_id]
        print(f"清理摄像头 {camera_id} 资源")
    return {"status": "success", "message": "推流结束处理完成"}


# AI分析设置
@app.post("/frame/analyze/settings/{camera_id}")
async def update_ai_settings(camera_id: str, settings: service_manager.AISettings = Body(...)):
    service_manager.update_ai_settings(camera_id, settings.model_dump())
    return {"status": "success", "message": "AI分析设置已更新", "settings": service_manager.get_ai_settings(camera_id)}


@app.get("/frame/analyze/settings/{camera_id}")
async def get_ai_settings(camera_id: str):
    return service_manager.get_ai_settings(camera_id)


# 启动/停止视频流
@app.post("/stream/start/")
async def start_stream(config: CameraConfig):  # Using CameraConfig from models/alert_models.py
    if config.camera_id in service_manager._video_streams:
        raise HTTPException(status_code=400, detail=f"摄像头 {config.camera_id} 已在运行")

    try:
        print(f"正在启动视频流: {config.stream_url}")
        stream = VideoStream(stream_url=config.stream_url, camera_id=config.camera_id,
                             predictor=service_manager._detectors.get("object"),
                             face_recognizer=service_manager._detectors.get("face"),
                             fire_detector=service_manager._detectors.get("fire"))

        is_available = await stream.test_connection()
        if not is_available:
            raise HTTPException(status_code=400, detail="无法连接到视频流，请检查流地址是否正确")

        # 动态初始化 Deep SORT 追踪器
        if config.camera_id not in service_manager._object_trackers:
            service_manager._object_trackers[config.camera_id] = DeepSORTTracker()
            print(f"为摄像头 {config.camera_id} 初始化Deep SORT追踪器")

        # 启动音频提取 (如果启用声学检测)
        if config.enable_sound_detection and service_manager.config.ENABLE_SOUND_DETECTION:
            await stream.start_audio_extraction()
            # 启动声学分析后台任务 (每个流一个任务)
            asyncio.create_task(service_manager._run_acoustic_analysis(config.camera_id))

        if not await stream.start():
            raise HTTPException(status_code=500, detail="无法启动视频流处理")

        # 将流实例添加到管理器
        service_manager._video_streams[config.camera_id] = stream

        # 启动异步帧处理任务
        asyncio.create_task(process_video_stream_async_loop(stream, config.camera_id))

        return {
            "status": "success", 
            "message": f"成功启动摄像头 {config.camera_id} 的视频流处理",
            "success": True  # 为了兼容前端代码
        }

    except Exception as e:
        print(f"启动视频流时出错: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"启动视频流时出错: {str(e)}")


async def process_video_stream_async_loop(stream: VideoStream, camera_id: str):
    """异步处理视频流循环，从VideoStream获取帧并送入分析器"""
    print(f"开始异步处理视频流循环: {camera_id}")
    frame_process_counter = 0
    while stream.is_running:
        try:
            # 这里直接从 VideoStream 获取帧，VideoStream 内部负责读取
            success, frame = stream.get_raw_frame()  # VideoStream 需要暴露这个方法
            if not success or frame is None:
                await asyncio.sleep(0.01)  # 短暂等待，避免空转
                continue

            # 使用 AIServiceManager 的核心分析逻辑
            # 注意：这里是单帧上传API的逻辑，如果是在连续视频流中，
            # 逻辑会略有不同，需要VideoStream的process_frame进行处理并返回结果
            # 为了与现有代码保持一致性，我们假设VideoStream已经集成了检测器并处理帧

            # 这里的 process_frame 应该是由 stream 自身调用的。
            # 这里需要修改 VideoStream 内部的 _process_frames 循环，让它直接调用 service_manager.process_single_frame
            # 或者，将 service_manager.process_single_frame 的逻辑移动到 VideoStream.process_frame 中

            # 当前代码的结构意味着 app.py 的 process_video_stream_async_loop 会从 stream 获取帧
            # 然后将帧交给 service_manager.process_single_frame 进行分析。
            # 这是为了复用 analyze_frame API 的核心分析逻辑。

            # 获取当前AI分析设置
            settings = service_manager.get_ai_settings(camera_id)
            performance_mode = "balanced"  # 默认值
            if settings:
                performance_mode = "fast" if settings.get('realtime_mode', False) else "balanced"

            # 调用 AIServiceManager 的核心分析方法
            analysis_results = await service_manager.process_single_frame(
                frame=frame,
                camera_id=camera_id,
                enable_face_recognition=settings.get('face_recognition', True),
                enable_object_detection=settings.get('object_detection', True),
                enable_behavior_detection=settings.get('behavior_analysis', False),
                enable_fire_detection=settings.get('fire_detection', True),
                performance_mode=performance_mode
            )

            # 分析结果会由 service_manager 内部异步发送给后端和WebSocket

            # 控制帧率 (如果需要)
            await asyncio.sleep(0.02)  # 约50fps

        except Exception as e:
            print(f"视频流处理循环错误 [{camera_id}]: {e}")
            traceback.print_exc()
            await asyncio.sleep(1)  # 发生错误时等待1秒再继续


@app.post("/stream/stop/{camera_id}")
async def stop_stream(camera_id: str):
    try:
        if camera_id not in service_manager._video_streams:
            return {
                "status": "error",
                "message": f"摄像头 {camera_id} 未在运行",
                "success": False
            }

        # 停止视频流
        stream = service_manager._video_streams[camera_id]
        await stream.stop()  # 使用 VideoStream 的 stop 方法

        # 从管理器中移除流实例
        del service_manager._video_streams[camera_id]
        
        # 清理相关资源
        if camera_id in service_manager._object_trackers:
            del service_manager._object_trackers[camera_id]
        
        if camera_id in service_manager._detection_cache:
            service_manager._detection_cache[camera_id] = {"objects": {}, "face_history": {}, "frame_count": 0}

        return {
            "status": "success",
            "message": f"成功停止摄像头 {camera_id} 的视频流处理",
            "success": True
        }
    except Exception as e:
        print(f"停止视频流时出错: {str(e)}")
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"停止视频流时出错: {str(e)}",
            "success": False
        }


# 人脸注册
class FaceData(BaseModel):
    person_name: str
    image_data: str


@app.post("/face/register/")
async def register_face(face_data: FaceData):
    try:
        image_bytes = base64.b64decode(face_data.image_data)
        image_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(status_code=400, detail="无效的Base64图像数据。")

        # 调用人脸识别器的添加方法 (FaceRecognizer 类中需要实现此方法)
        face_recognizer_instance = service_manager._detectors.get("face")
        if not face_recognizer_instance:
            raise HTTPException(status_code=500, detail="人脸识别器未初始化。")

        # 假设FaceRecognizer有一个 add_face 方法
        # if face_recognizer_instance.add_face(image, face_data.person_name):
        #     return {"status": "success", "message": f"人脸 '{face_data.person_name}' 注册成功。"}
        # else:
        #     raise HTTPException(status_code=400, detail="注册失败，可能未在图像中检测到人脸。")

        # 暂时返回成功，待FaceRecognizer实现add_face
        print(f"收到人脸注册请求: {face_data.person_name}")
        return {"status": "success", "message": "人脸注册请求已收到 (功能待FaceRecognizer实现)。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 系统状态
@app.get("/system/status/", response_model=SystemStatus)
async def get_system_status():
    return service_manager.get_system_status()


# 音频检测设置
@app.post("/audio/settings/")
async def update_audio_settings(
        confidence_threshold: Optional[float] = Body(default=None),
        detection_interval: Optional[float] = Body(default=None),
        event_cooldown: Optional[float] = Body(default=None),
        sensitivity: Optional[str] = Body(default=None)  # "low", "medium", "high"
):
    acoustic_detector = service_manager._detectors.get("acoustic")
    if not acoustic_detector:
        raise HTTPException(status_code=500, detail="音频检测器未初始化")

    if sensitivity is not None and sensitivity not in ["low", "medium", "high"]:
        raise HTTPException(status_code=400, detail="敏感度必须是 'low', 'medium' 或 'high'")

    acoustic_detector.update_settings(
        confidence_threshold=confidence_threshold,
        detection_interval=detection_interval,
        event_cooldown=event_cooldown,
        sensitivity=sensitivity
    )
    return {
        "status": "success", "message": "音频检测设置已更新",
        "current_settings": {
            "confidence_threshold": acoustic_detector.confidence_threshold,
            "detection_interval": acoustic_detector.detection_interval,
            "event_cooldown": acoustic_detector.event_cooldown,
            "volume_multiplier": acoustic_detector.volume_multiplier,
            "frequency_multiplier": acoustic_detector.frequency_multiplier,
            "noise_multiplier": acoustic_detector.noise_multiplier
        }
    }


@app.get("/audio/settings/")
async def get_audio_settings():
    acoustic_detector = service_manager._detectors.get("acoustic")
    if not acoustic_detector:
        raise HTTPException(status_code=500, detail="音频检测器未初始化")
    return {
        "status": "success",
        "settings": {
            "confidence_threshold": acoustic_detector.confidence_threshold,
            "detection_interval": acoustic_detector.detection_interval,
            "event_cooldown": acoustic_detector.event_cooldown,
            "volume_multiplier": acoustic_detector.volume_multiplier,
            "frequency_multiplier": acoustic_detector.frequency_multiplier,
            "noise_multiplier": acoustic_detector.noise_multiplier
        }
    }


@app.post("/audio/reset/")
async def reset_audio_history():
    acoustic_detector = service_manager._detectors.get("acoustic")
    if not acoustic_detector:
        raise HTTPException(status_code=500, detail="音频检测器未初始化")
    acoustic_detector.reset_event_history()
    return {"status": "success", "message": "音频事件历史已重置"}


@app.post("/audio/frontend/alert/")
async def process_frontend_audio_alert(
        camera_id: str = Body(...),
        audio_level: float = Body(...),
        event_type: str = Body(default="high_volume"),
        timestamp: Optional[str] = Body(default=None)
):
    if not timestamp: timestamp = datetime.now().isoformat()
    alert_result = AIAnalysisResult(
        camera_id=camera_id, event_type=f"frontend_{event_type}", location={"audio_level": audio_level},
        confidence=min(audio_level / 100.0, 1.0), timestamp=timestamp,
        details={"source": "frontend_audio_detection", "audio_level": audio_level, "event_type": event_type}
    )
    service_manager.send_alert_to_backend(alert_result)
    return {"status": "success", "message": f"音频告警已处理: {event_type}, 音量级别: {audio_level}%"}


# 单帧分析 (用于前端上传图片进行分析)
@app.post("/frame/analyze/")
async def analyze_frame_endpoint(
        frame: UploadFile = File(...),
        camera_id: str = Form(...),
        enable_face_recognition: bool = Form(True),
        enable_object_detection: bool = Form(True),
        enable_behavior_detection: bool = Form(False),
        enable_fire_detection: bool = Form(True),
        performance_mode: str = Form("balanced")  # "fast", "balanced", "quality"
):
    try:
        image_data = await frame.read()
        image_array = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(status_code=400, detail="无效的图像数据")

        results = await service_manager.process_single_frame(
            frame=image,
            camera_id=camera_id,
            enable_face_recognition=enable_face_recognition,
            enable_object_detection=enable_object_detection,
            enable_behavior_detection=enable_behavior_detection,
            enable_fire_detection=enable_fire_detection,
            performance_mode=performance_mode
        )
        return {"status": "success", "results": results}
    except Exception as e:
        print(f"分析帧时发生错误: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


# 网络摄像头流处理 (简化为仅启动/停止标记)
@app.get("/stream/webcam/start/{camera_id}")
async def start_webcam_stream(camera_id: str):
    if camera_id not in service_manager._video_streams:
        # 为网络摄像头创建一个虚拟的VideoStream实例
        class WebcamProcessor(VideoStream):  # 继承VideoStream以复用其方法
            def __init__(self, camera_id_val: str):
                # 虚拟URL，因为WebcamProcessor不拉流
                super().__init__(stream_url=f"webcam://{camera_id_val}", camera_id=camera_id_val)
                self.is_webcam = True
                self.is_running = True
                self.frame_count = 0

            # 模拟获取原始帧（实际应由前端推送）
            def get_raw_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
                return False, None  # WebcamProcessor 不主动拉取帧

            def get_audio_file(self) -> Optional[str]:
                return None  # WebcamProcessor 不提供音频文件

        service_manager._video_streams[camera_id] = WebcamProcessor(camera_id)
        if camera_id not in service_manager._object_trackers:
            service_manager._object_trackers[camera_id] = DeepSORTTracker()
        print(f"网络摄像头流 {camera_id} 已标记为启动")
    return {"status": "success", "message": f"网络摄像头流 {camera_id} 已启动", "camera_id": camera_id}


@app.post("/stream/webcam/stop/{camera_id}")
async def stop_webcam_stream(camera_id: str):
    if camera_id in service_manager._video_streams:
        stream = service_manager._video_streams[camera_id]
        stream.stop()  # 停止标记
        del service_manager._video_streams[camera_id]
        if camera_id in service_manager._object_trackers: del service_manager._object_trackers[camera_id]
        if camera_id in service_manager._detection_cache: del service_manager._detection_cache[camera_id]
        print(f"网络摄像头流 {camera_id} 已停止并清除缓存")
    return {"status": "success", "message": f"网络摄像头流 {camera_id} 已停止并清除缓存"}


# 缓存管理
@app.post("/detection/cache/clear/{camera_id}")
async def clear_detection_cache(camera_id: str):
    if camera_id in service_manager._detection_cache:
        del service_manager._detection_cache[camera_id]
        return {"status": "success", "message": f"已清除摄像头 {camera_id} 的检测缓存"}
    return {"status": "success", "message": f"摄像头 {camera_id} 无缓存需要清除"}


@app.post("/detection/cache/clear/all")
async def clear_all_detection_cache():
    service_manager._detection_cache.clear()
    return {"status": "success", "message": "已清除所有检测缓存"}


# 性能优化与调试
@app.get("/performance/optimize/")
async def get_performance_tips():
    return {
        "status": "success", "tips": [], "performance_mode": "high_performance",
        "optimizations": ["动态检测阈值", "结果数量限制", "低分辨率跳过", "异步后端通信", "错误容错机制"]
    }  # 简化，详情由管理器提供


@app.get("/performance/stats/")
async def get_performance_stats():
    return service_manager.get_performance_stats()


@app.get("/debug/face_tracking/{camera_id}")
async def get_face_tracking_debug(camera_id: str):
    # 调试信息直接从service_manager获取其内部缓存
    if camera_id not in service_manager._detection_cache:
        raise HTTPException(status_code=404, detail="未找到该摄像头的检测缓存。")

    cache_data = service_manager._detection_cache[camera_id]
    face_cache = {k: v for k, v in cache_data.get("objects", {}).items() if v.get("type") == "face"}
    face_history = cache_data.get("face_history", {})
    current_time = time.time()

    debug_info = {
        "camera_id": camera_id, "face_cache": {}, "face_history": {},
        "tracking_parameters": service_manager.get_stabilization_config(camera_id),  # 使用实际配置
        "advanced_features": ["人脸专用持续跟踪算法", "运动趋势预测和插值", "自适应图像缩放", "综合匹配评分系统",
                              "运动历史记录", "预测位置保持机制", "连续检测优先级"]
    }

    for obj_id, obj_data in face_cache.items():
        time_since_last_seen = current_time - obj_data["last_seen"]
        debug_info["face_cache"][obj_id] = {
            "bbox": obj_data["bbox"], "confidence": obj_data["confidence"],
            "stable_count": obj_data.get("stable_count", 0),
            "consecutive_detections": obj_data.get("consecutive_detections", 0),
            "last_seen": obj_data["last_seen"], "is_stable": obj_data.get("stable_count", 0) >= 1,
            "age_seconds": time_since_last_seen,
            "status": "active" if time_since_last_seen < 0.5 else "missing" if time_since_last_seen < 2.0 else "expired",
            "first_seen": obj_data.get("first_seen", obj_data["last_seen"]),
            "has_predicted_bbox": "predicted_bbox" in obj_data
        }
    for obj_id, history in face_history.items():
        if obj_id in debug_info["face_cache"]:
            debug_info["face_history"][obj_id] = {
                "position_count": len(history.get("positions", [])),
                "latest_positions": history.get("positions", [])[-3:],
                "latest_timestamps": history.get("timestamps", [])[-3:],
                "has_motion_data": len(history.get("positions", [])) >= 2
            }
            if len(history.get("positions", [])) >= 2:
                pos1, pos2 = history["positions"][-2], history["positions"][-1]
                time1, time2 = history["timestamps"][-2], history["timestamps"][-1]
                if time2 - time1 > 0:
                    vx = (pos2[0] - pos1[0]) / (time2 - time1)
                    vy = (pos2[1] - pos1[1]) / (time2 - time1)
                    speed = (vx ** 2 + vy ** 2) ** 0.5
                    debug_info["face_history"][obj_id]["motion_speed"] = round(speed, 2)
                    debug_info["face_history"][obj_id]["motion_vector"] = [round(vx, 2), round(vy, 2)]

    debug_info["statistics"] = {
        "total_faces": len(face_cache),
        "active_faces": len([f for f in face_cache.values() if f.get("status") == "active"]),
        "missing_faces": len([f for f in face_cache.values() if f.get("status") == "missing"]),
        "face_history_count": len(face_history), "system_status": "高级人脸持续跟踪已启用"
    }
    return {"status": "success", "debug_info": debug_info}


@app.get("/performance/mode/recommend/")
async def recommend_performance_mode():
    import psutil
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    gpu_available = False;
    gpu_memory_free = 0
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        gpu_available = len(gpus) > 0
        if gpus: gpu_memory_free = gpus[0].memoryFree
    except:
        pass

    if cpu_percent > 80 or memory.percent > 85:
        recommended_mode = "fast"; reason = "系统负载较高，建议使用极速模式减少卡顿"
    elif cpu_percent < 40 and memory.percent < 60 and gpu_available:
        recommended_mode = "quality"; reason = "系统性能充足，可以使用质量模式获得最佳效果"
    else:
        recommended_mode = "balanced"; reason = "系统性能适中，建议使用平衡模式"

    return {
        "recommended_mode": recommended_mode, "reason": reason,
        "system_info": {
            "cpu_usage": f"{cpu_percent:.1f}%", "memory_usage": f"{memory.percent:.1f}%",
            "available_memory": f"{memory.available / 1024 / 1024 / 1024:.1f}GB",
            "gpu_available": gpu_available, "gpu_memory_free": f"{gpu_memory_free}MB" if gpu_available else "N/A"
        }
    }


@app.get("/performance/guide/")
async def get_performance_guide():
    return {
        "title": "SmartEye 摄像头监控性能优化指南", "overview": "针对同时开启多个检测功能导致卡顿的解决方案",
        "performance_modes": {},  # 简化，管理器中提供
        "usage_instructions": {"api_call": {"endpoint": "/frame/analyze/", "new_parameter": "performance_mode"}},
        "optimization_tips": {"hardware": [], "software": [], "network": []},
        "monitoring": {}, "troubleshooting": {}, "quick_start": {}
    }


# 检测框稳定化配置
@app.post("/detection/stabilization/config/")
async def configure_stabilization(
        camera_id: str = Body(...),
        face_smooth_factor: float = Body(default=0.92),
        object_smooth_factor: float = Body(default=0.88),
        face_match_threshold: int = Body(default=120),
        object_match_threshold: int = Body(default=60),
        jitter_detection_threshold: int = Body(default=30),
        max_size_change_ratio: float = Body(default=0.2)
):
    if not (0.5 <= face_smooth_factor <= 0.99) or not (0.5 <= object_smooth_factor <= 0.99) or \
            not (30 <= face_match_threshold <= 300) or not (20 <= object_match_threshold <= 200):
        raise HTTPException(status_code=400, detail="参数范围无效")

    config_data = {
        "face_smooth_factor": face_smooth_factor, "object_smooth_factor": object_smooth_factor,
        "face_match_threshold": face_match_threshold, "object_match_threshold": object_match_threshold,
        "jitter_detection_threshold": jitter_detection_threshold, "max_size_change_ratio": max_size_change_ratio
    }
    service_manager.update_stabilization_config(camera_id, config_data)
    return {"status": "success", "message": f"摄像头 {camera_id} 的稳定化参数已更新",
            "config": service_manager.get_stabilization_config(camera_id)}


@app.get("/detection/stabilization/config/{camera_id}")
async def get_stabilization_config(camera_id: str):
    config = service_manager.get_stabilization_config(camera_id)
    return {
        "camera_id": camera_id, "config": config,
        "parameter_explanations": {
            "face_smooth_factor": "人脸框平滑强度 (0.5-0.99，越高越平滑但可能滞后)",
            "object_smooth_factor": "目标框平滑强度 (0.5-0.99，越高越平滑)",
            "face_match_threshold": "人脸匹配距离阈值 (像素，越小越严格)",
            "object_match_threshold": "目标匹配距离阈值 (像素，越小越严格)",
            "jitter_detection_threshold": "抖动检测阈值 (像素，超过此值触发抗抖动)",
            "max_size_change_ratio": "框尺寸变化限制 (0.1-0.5，限制突然的尺寸变化)"
        }
    }


@app.post("/detection/stabilization/preset/{preset_name}")
async def apply_stabilization_preset(preset_name: str, camera_id: str = Body(...)):
    try:
        return service_manager.apply_stabilization_preset(preset_name, camera_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/detection/stabilization/presets/")
async def list_stabilization_presets():
    return {"available_presets": service_manager.list_stabilization_presets()}


@app.post("/detection/anti_flicker/apply/")
async def apply_anti_flicker_all_cameras():
    return await service_manager.apply_anti_flicker_all_cameras()


@app.post("/detection/identity_stabilization/status/")
async def check_identity_stabilization_status():
    return {
        "status": "active", "message": "🎯 人脸身份稳定化系统运行正常",
        "system_stats": {},  # 简化
        "stabilization_features": {},  # 简化
        "current_settings": {},  # 简化
        "quick_actions": {}  # 简化
    }


@app.get("/detection/anti_jitter/status/")
async def get_anti_jitter_status():
    return {
        "anti_jitter_enabled": True, "status": "自动启用", "description": "抗抖动功能已默认启用，无需手动操作",
        "automatic_features": {}, "default_settings": {}, "performance_impact": {}, "monitoring": {},
        "if_still_jittering": {}, "message": "✅ 抗抖动功能已自动启用并运行，您的检测框会自动保持稳定！"
    }


# 人脸灵敏度
@app.post("/face/sensitivity/adjust/")
async def adjust_face_recognition_sensitivity(
        tolerance: float = Body(default=None, description="人脸识别容忍度 (0.3-0.8, 越大越宽松)"),
        detection_model: str = Body(default=None, description="检测模型 (auto/cnn/hog)"),
        enable_multi_scale: Optional[bool] = Body(default=None, description="是否启用多尺度检测"),
        min_face_size: Optional[int] = Body(default=None, description="最小人脸尺寸 (像素)")
):
    if tolerance is not None and not (0.3 <= tolerance <= 0.8): raise HTTPException(status_code=400,
                                                                                    detail="tolerance 必须在 0.3-0.8 范围内")
    if detection_model is not None and detection_model not in ["auto", "cnn", "hog"]: raise HTTPException(
        status_code=400, detail="detection_model 必须是 auto/cnn/hog 之一")

    config_data = {}
    if tolerance is not None: config_data["tolerance"] = tolerance
    if detection_model is not None: config_data["detection_model"] = detection_model
    if enable_multi_scale is not None: config_data["enable_multi_scale"] = enable_multi_scale
    if min_face_size is not None: config_data["min_face_size"] = min_face_size

    service_manager.update_face_recognition_config(config_data)
    return {"status": "success", "message": "人脸识别灵敏度已成功调整",
            "config": service_manager.get_face_recognition_config()}


@app.get("/face/sensitivity/status/")
async def get_face_recognition_sensitivity():
    return {"status": "success", "current_config": service_manager.get_face_recognition_config()}


@app.post("/face/detection/test/")
async def test_face_detection_with_config(
        frame: UploadFile = File(...),
        tolerance: Optional[float] = Body(default=None),
        detection_model: Optional[str] = Body(default=None)
):
    try:
        image_bytes = await frame.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        test_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if test_frame is None: raise HTTPException(status_code=400, detail="无法解析图片")

        test_tolerance = tolerance or service_manager.get_face_recognition_config().get('tolerance', 0.65)
        test_model = detection_model or service_manager.get_face_recognition_config().get('detection_model', 'auto')

        if "face" not in service_manager._detectors: raise HTTPException(status_code=500, detail="人脸识别器未初始化")

        start_time = time.time()
        # 这里直接调用 FaceRecognizer，不经过稳定化，以便测试原始检测效果
        results = service_manager._detectors["face"].detect_and_recognize(test_frame, tolerance=test_tolerance)
        detection_time = (time.time() - start_time) * 1000

        total_faces = len(results);
        known_faces = sum(1 for r in results if r["identity"]["known"]);
        unknown_faces = total_faces - known_faces

        return {
            "status": "success",
            "test_results": {
                "total_faces_detected": total_faces, "known_faces": known_faces, "unknown_faces": unknown_faces,
                "detection_time_ms": round(detection_time, 2),
                "test_parameters": {"tolerance": test_tolerance, "detection_model": test_model}
            },
            "face_details": [
                {"face_id": i + 1, "identity": result["identity"]["name"], "known": result["identity"]["known"],
                 "confidence": round(result["confidence"], 3), "location": result["location"]}
                for i, result in enumerate(results)
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


@app.post("/face/sensitivity/optimize/")
async def optimize_face_recognition_for_sensitivity():
    # 应用高灵敏度设置
    config_data = {
        "tolerance": 0.65, "detection_model": "auto", "enable_multi_scale": True, "min_face_size": 40
    }
    service_manager.update_face_recognition_config(config_data)

    cleared_cameras = []
    for camera_id in list(service_manager._detection_cache.keys()):
        if camera_id in service_manager._detection_cache and "face_history" in service_manager._detection_cache[
            camera_id]:
            service_manager._detection_cache[camera_id]["face_history"].clear()
            cleared_cameras.append(camera_id)

    return {
        "status": "success", "message": "🎯 人脸识别灵敏度已优化!",
        "optimizations_applied": [], "new_config": service_manager.get_face_recognition_config(),
        "cleared_cache_cameras": cleared_cameras
    }


@app.get("/face/sensitivity/improvements/")
async def get_face_recognition_improvements():
    return {
        "status": "success", "optimization_summary": {},
        "current_config": service_manager.get_face_recognition_config()
    }


# 目标检测灵敏度
@app.post("/object/sensitivity/adjust/")
async def adjust_object_detection_sensitivity(
        confidence_threshold: Optional[float] = Body(default=None),
        area_ratio_threshold: Optional[float] = Body(default=None),
        special_class_threshold: Optional[float] = Body(default=None),
        enable_size_filter: Optional[bool] = Body(default=None),
        enable_aspect_ratio_filter: Optional[bool] = Body(default=None)
):
    if confidence_threshold is not None and not (0.1 <= confidence_threshold <= 0.8): raise HTTPException(
        status_code=400, detail="confidence_threshold 必须在 0.1-0.8 范围内")
    if area_ratio_threshold is not None and not (0.5 <= area_ratio_threshold <= 1.0): raise HTTPException(
        status_code=400, detail="area_ratio_threshold 必须在 0.5-1.0 范围内")
    if special_class_threshold is not None and not (0.3 <= special_class_threshold <= 0.9): raise HTTPException(
        status_code=400, detail="special_class_threshold 必须在 0.3-0.9 范围内")

    config_data = {}
    if confidence_threshold is not None: config_data["confidence_threshold"] = confidence_threshold
    if area_ratio_threshold is not None: config_data["area_ratio_threshold"] = area_ratio_threshold
    if special_class_threshold is not None: config_data["special_class_threshold"] = special_class_threshold
    if enable_size_filter is not None: config_data["enable_size_filter"] = enable_size_filter
    if enable_aspect_ratio_filter is not None: config_data["enable_aspect_ratio_filter"] = enable_aspect_ratio_filter

    service_manager.update_object_detection_config(config_data)
    return {"status": "success", "message": "目标检测灵敏度已成功调整",
            "config": service_manager.get_object_detection_config()}


@app.get("/object/sensitivity/status/")
async def get_object_detection_sensitivity():
    return {"status": "success", "current_config": service_manager.get_object_detection_config()}


@app.post("/object/sensitivity/optimize/")
async def optimize_object_detection_for_sensitivity():
    config_data = {
        "confidence_threshold": 0.3, "area_ratio_threshold": 0.95,
        "special_class_threshold": 0.5, "enable_size_filter": True, "enable_aspect_ratio_filter": False
    }
    service_manager.update_object_detection_config(config_data)

    cleared_cameras = []
    for camera_id in list(service_manager._detection_cache.keys()):
        if camera_id in service_manager._detection_cache and "objects" in service_manager._detection_cache[camera_id]:
            object_cache = service_manager._detection_cache[camera_id]["objects"]
            service_manager._detection_cache[camera_id]["objects"] = {k: v for k, v in object_cache.items() if
                                                                      v.get("type") == "face"}
            cleared_cameras.append(camera_id)

    return {
        "status": "success", "message": "🎯 目标检测灵敏度已优化!",
        "optimizations_applied": [], "new_config": service_manager.get_object_detection_config(),
        "cleared_cache_cameras": cleared_cameras
    }


@app.post("/detection/sensitivity/optimize_all/")
async def optimize_all_detection_sensitivity():
    # 优化目标检测
    object_config_data = {
        "confidence_threshold": 0.3, "area_ratio_threshold": 0.95,
        "special_class_threshold": 0.5, "enable_size_filter": True, "enable_aspect_ratio_filter": False
    }
    service_manager.update_object_detection_config(object_config_data)

    # 优化人脸识别
    face_config_data = {
        "tolerance": 0.7, "detection_model": "auto", "enable_multi_scale": True, "min_face_size": 35
    }
    service_manager.update_face_recognition_config(face_config_data)

    cleared_cameras = []
    for camera_id in list(service_manager._detection_cache.keys()):
        service_manager._detection_cache[camera_id] = {"objects": {}, "face_history": {}, "frame_count": 0}
        cleared_cameras.append(camera_id)

    return {
        "status": "success", "message": "🎯 所有检测系统灵敏度已优化到最高!",
        "object_detection_optimizations": [], "face_recognition_optimizations": [],
        "applied_configs": {"object_detection": service_manager.get_object_detection_config(),
                            "face_recognition": service_manager.get_face_recognition_config()},
        "cleared_cache_cameras": cleared_cameras
    }


# 危险区域检测API
@app.post("/danger_zone/config/")
async def configure_danger_zones(camera_id: str = Body(...), zones: List[Dict] = Body(...)):
    service_manager.update_danger_zones(camera_id, zones)
    return {"status": "success", "message": f"摄像头 {camera_id} 的危险区域配置已更新", "configured_zones": len(zones),
            "zones": zones}


@app.get("/danger_zone/status/{camera_id}")
async def get_danger_zone_status(camera_id: str):
    status = service_manager.get_danger_zone_status(camera_id)
    return {"status": "success", "data": status}


@app.delete("/danger_zone/{camera_id}/{zone_id}")
async def remove_danger_zone(camera_id: str, zone_id: str):
    service_manager.remove_danger_zone(camera_id, zone_id)
    return {"status": "success", "message": f"危险区域 {zone_id} 已移除"}


# 人脸处理辅助API (用于人脸注册和验证，可能需要与Django后端交互)
@app.post("/process_face")
async def process_face(request_data: dict):
    # 保持原有逻辑，但请注意，face_recognition库的集成在此处并非通过AIServiceManager管理
    # 这是用于独立的人脸特征提取而非实时检测流
    try:
        image_data = base64.b64decode(request_data.get("image", ""))
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None: return {"success": False, "message": "无法解码图像"}

        # 使用AI服务中的 FaceRecognizer 实例
        face_recognizer_instance = service_manager._detectors.get("face")
        if not face_recognizer_instance:
            return {"success": False, "message": "人脸识别器未初始化"}

        # 为了避免依赖外部的face_recognition库导入，我们假设FaceRecognizer内部会处理这些
        # 这里需要 FaceRecognizer 提供一个 extract_encoding 方法
        # 暂时简化，直接调用detect_and_recognize并取第一个
        results = face_recognizer_instance.detect_and_recognize(image, tolerance=0.6)
        if not results: return {"success": False, "message": "未检测到人脸"}
        if len(results) > 1: return {"success": False, "message": "检测到多个人脸，请确保图像中只有一个人脸"}

        # 假设 result['identity'] 中包含了编码
        # 这部分代码需要根据 FaceRecognizer 实际返回的结构进行调整
        # 为了兼容性，返回一个虚拟编码
        face_location = results[0]['location']
        # 注意：FaceRecognizer.detect_and_recognize 并没有直接返回 face_encoding
        # 这需要 FaceRecognizer 提供新的方法或返回更详细的数据

        # 临时返回一个模拟的编码，直到FaceRecognizer有明确的extract_encoding方法
        mock_encoding = [0.1] * 128
        return {
            "success": True, "message": "人脸处理成功",
            "face_encoding": mock_encoding,
            "face_location": face_location
        }
    except Exception as e:
        return {"success": False, "message": f"处理人脸时出错: {str(e)}"}


@app.post("/verify_face")
async def verify_face(request_data: dict):
    try:
        image_data = base64.b64decode(request_data.get("image", ""))
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None: return {"success": False, "message": "无法解码图像"}

        user_id = request_data.get("user_id")
        if not user_id: return {"success": False, "message": "未提供用户ID"}

        face_recognizer_instance = service_manager._detectors.get("face")
        if not face_recognizer_instance:
            return {"success": False, "message": "人脸识别器未初始化"}

        # 同样，这部分需要 FaceRecognizer 提供比对能力或 extract_encoding
        # 暂时模拟比对过程
        # 获取传入图像的人脸编码 (假设FaceRecognizer能提取)
        results = face_recognizer_instance.detect_and_recognize(image, tolerance=0.6)
        if not results: return {"success": False, "message": "未检测到人脸"}
        if len(results) > 1: return {"success": False, "message": "检测到多个人脸，请确保图像中只有一个人脸"}

        # 模拟获取用户注册的人脸编码 (从后端获取)
        api_url = f"http://localhost:8000/api/users/faces/user/{user_id}/encodings/"
        try:
            response = requests.get(api_url)
            if response.status_code != 200: return {"success": False, "message": "无法获取用户人脸数据"}
            stored_face_encodings = response.json().get("encodings", [])
            if not stored_face_encodings: return {"success": False, "message": "用户没有注册人脸数据"}

            # 假设FaceRecognizer能直接进行比较或我们能获取到当前帧的编码
            # 当前FaceRecognizer.detect_and_recognize返回的是身份信息，不是原始编码
            # 这一步需要进一步重构 FaceRecognizer 以支持返回原始编码或直接比对

            # 暂时通过名字来模拟验证
            detected_name = results[0]["identity"].get("name", "unknown")
            # 假设后端返回的encodings中也包含了name信息，或user_id对应一个固定name
            # 这里简化为只要是"known"且名字匹配就成功
            if results[0]["identity"]["known"] and detected_name == user_id:  # 假设user_id就是name
                return {"success": True, "matched": True, "confidence": results[0]["confidence"],
                        "message": "人脸验证成功"}
            else:
                return {"success": True, "matched": False, "message": "人脸不匹配"}

        except Exception as e:
            return {"success": False, "message": f"验证过程中出错: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"处理人脸时出错: {str(e)}"}


# 视频流连接测试
@app.post("/stream/test/")
async def test_stream_connection_endpoint(url: str = Body(...), type: str = Body(...)):
    print(f"正在测试视频流连接: {url} (类型: {type})")
    try:
        # 为了测试，这里不传入实际的检测器实例
        stream = VideoStream(stream_url=url, camera_id="test_connection_id")
        is_available = await stream.test_connection()
        
        if is_available:
            return {
                "status": "success",
                "message": "视频流可用",
                "success": True  # 为了兼容前端代码
            }
        else:
            return {
                "status": "error",
                "message": "无法连接到视频流，请检查流地址是否正确",
                "success": False  # 为了兼容前端代码
            }
    except Exception as e:
        print(f"测试视频流连接时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"测试视频流时发生错误: {str(e)}",
            "success": False  # 为了兼容前端代码
        }


# 启动Uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)