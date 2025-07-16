# 文件: ai_service/app.py
# 描述: 智能视频分析服务的主入口，负责API路由、服务生命周期管理、AI功能协调。

import os
import asyncio
import time
import base64
import traceback
import json
import tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any, Union, Tuple
from threading import Lock

import cv2
import numpy as np
import uvicorn
import requests
import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Body, File, UploadFile, Form, Query, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from requests.adapters import HTTPAdapter
from starlette.responses import JSONResponse
from urllib3.util.retry import Retry
from starlette.websockets import WebSocketState
import httpx
from urllib.parse import urlparse, parse_qs
from loguru import logger

# 添加自定义JSON编码器处理datetime对象
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# 导入我们自定义的所有核心AI模块和模型
import sys
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
# 将当前目录添加到Python路径，确保可以导入核心模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from smart_station_platform.ai_service.core.video_stream import VideoStream
from smart_station_platform.ai_service.core.object_detection import ObjectDetector
from smart_station_platform.ai_service.core.behavior_detection import BehaviorDetector
from smart_station_platform.ai_service.core.face_recognition import FaceRecognizer
from smart_station_platform.ai_service.core.fire_smoke_detection import FlameSmokeDetector
from smart_station_platform.ai_service.core.multi_object_tracker import DeepSORTTracker
from smart_station_platform.ai_service.core.danger_zone_detection import DangerZoneDetector
from smart_station_platform.ai_service.core.liveness_detector import LivenessSession
from smart_station_platform.ai_service.models.alert_models import AIAnalysisResult, CameraConfig, SystemStatus
from smart_station_platform.ai_service.core.draw_utils import draw_detections
from smart_station_platform.ai_service.core.webrtc_pusher import webrtc_pusher, start_cleanup_task

# --- 全局变量和模型初始化 ---
face_recognizer: Optional[FaceRecognizer] = None
fire_detector: Optional[FlameSmokeDetector] = None
object_detector: Optional[ObjectDetector] = None
tracker: Optional[DeepSORTTracker] = None
danger_zone_detector: Optional[DangerZoneDetector] = None
app_config = None
service_manager = None
known_faces_path = "smart_station_platform/ai_service/assets/known_faces"
DETECTION_FRAME_SKIP = 2  # 每 X 帧进行一次AI分析，以平衡性能和实时性


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
            load_dotenv()

        # 【核心修复】不再使用环境变量，而是计算相对路径
        # self.ASSET_BASE_PATH = os.getenv("G_DRIVE_ASSET_PATH", "/app/assets")
        self.ASSET_BASE_PATH = os.path.normpath(os.path.join(current_dir, 'assets'))
        self.AI_SERVICE_API_KEY = os.getenv('AI_SERVICE_API_KEY', 'smarteye-ai-service-key-2024')
        self.BACKEND_ALERT_URL = os.getenv('BACKEND_ALERT_URL', 'http://localhost:8000/api/alerts/ai-results/')
        self.BACKEND_WEBSOCKET_BROADCAST_URL = os.getenv('BACKEND_WEBSOCKET_BROADCAST_URL', 'http://localhost:8000/api/alerts/websocket/broadcast/')
        self.BACKEND_INTERNAL_LOGIN_URL = os.getenv('BACKEND_INTERNAL_LOGIN_URL', 'http://localhost:8000/api/users/login/internal/')
        self.INTERNAL_SERVICE_API_KEY = os.getenv('INTERNAL_SERVICE_API_KEY', 'a-secure-default-key-for-dev')
        self.ENABLE_SOUND_DETECTION = os.getenv("ENABLE_SOUND_DETECTION", "false").lower() == "true"
        self.FASTAPI_TIMEOUT_SECONDS = float(os.getenv("FASTAPI_TIMEOUT_SECONDS", "120.0"))

        print(f"--- 使用资源根目录: {self.ASSET_BASE_PATH} ---")

# --- AISettings 类 ---
class AISettings(BaseModel):
    face_recognition: Optional[bool] = None
    object_detection: Optional[bool] = None
    behavior_analysis: Optional[bool] = None
    fire_detection: Optional[bool] = None
    sound_detection: Optional[bool] = None
    liveness_detection: Optional[bool] = None
    realtime_mode: Optional[bool] = None
    face_confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    object_confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    fall_detection_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    stabilization_level: Optional[str] = Field(None, pattern="^(default|responsive|balanced|stable|ultra_stable)$")

    class Config:
        extra = 'ignore'

# --- AIServiceManager 类 ---
class AIServiceManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self._detectors: Dict[str, Any] = {
            "object": None, "fire": None, "face": None, "behavior": None,
        }
        self._video_streams: Dict[str, VideoStream] = {}
        self._video_streams_lock = Lock()
        self._object_trackers: Dict[str, DeepSORTTracker] = {}
        self._detection_cache: Dict[str, Dict] = {}
        self._thread_pool = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)
        self._ai_settings: Dict[str, Dict] = {}
        self._face_recognition_config: Dict[str, Any] = {"tolerance": 0.65, "detection_model": "auto"}
        self._object_detection_config: Dict[str, Any] = {"confidence_threshold": 0.35}
        self._stabilization_config: Dict[str, Dict] = {}
        self._video_webrtc: Dict[str, str] = {}

    def get_ai_settings(self, camera_id: str) -> Dict[str, Any]:
        """获取指定摄像头的AI分析配置，如果不存在则返回默认配置。"""
        default_settings = {
            "face_recognition": True, "object_detection": True, "behavior_analysis": False,
            "fire_detection": True, "sound_detection": False, "liveness_detection": True,
            "realtime_mode": True, "face_confidence_threshold": 0.6, "object_confidence_threshold": 0.4,
        }
        return self._ai_settings.get(camera_id, default_settings.copy())

    def update_ai_settings(self, camera_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """更新指定摄像头的AI配置。"""
        if camera_id not in self._ai_settings:
            self._ai_settings[camera_id] = self.get_ai_settings(camera_id)
        self._ai_settings[camera_id].update(settings)
        logger.info(f"AI settings for camera '{camera_id}' updated: {self._ai_settings[camera_id]}")
        return self._ai_settings[camera_id]

    def update_stream_settings(self, camera_id: str, settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新正在运行的视频流的AI配置。"""
        if camera_id in self._video_streams:
            return self.update_ai_settings(camera_id, settings)
        return None

    async def reload_face_recognizer(self):
        """重新加载人脸识别器中的已知人脸数据。"""
        global face_recognizer
        if face_recognizer:
            face_recognizer.reload_known_faces()
            self._detectors["face"] = face_recognizer
            logger.info("Face recognizer data reloaded successfully.")

    async def send_alert_to_backend(self, alert_data: AIAnalysisResult):
        """将AI分析结果作为告警发送到主后端服务。"""
        alert_dict = alert_data.model_dump()
        logger.info(f"准备发送告警到后端: {alert_dict}")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.config.BACKEND_ALERT_URL,
                    json=alert_dict,
                    headers={'X-Internal-API-Key': self.config.INTERNAL_SERVICE_API_KEY},
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info(f"告警已成功发送到后端，响应: {response.json()}")
                return True
            except httpx.RequestError as e:
                logger.error(f"发送告警到后端时发生网络错误: {e}")
                return False
            except Exception as e:
                logger.error(f"发送告警到后端时发生未知错误: {e}", exc_info=True)
                return False

    async def broadcast_via_backend(self, camera_id: str, payload: Dict[str, Any]):
        """通过主后端将数据广播到WebSocket客户端。"""
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    self.config.BACKEND_WEBSOCKET_BROADCAST_URL,
                    json={"camera_id": camera_id, "payload": payload},
                    headers={'X-Internal-API-Key': self.config.INTERNAL_SERVICE_API_KEY}, timeout=5.0)
            except httpx.RequestError as e:
                logger.error(f"Error broadcasting message via backend for camera {camera_id}: {e}")

    async def send_to_websocket(self, camera_id: str, message: Dict[str, Any]):
        await self.broadcast_via_backend(camera_id, message)

    async def send_detection_to_websocket(self, camera_id: str, results: Dict[str, Any]):
        await self.broadcast_via_backend(camera_id, {"type": "ai_detection", "data": results})
        
    async def get_user_token(self, username: str) -> Optional[Dict[str, Any]]:
        """从主后端获取用户的登录令牌。"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.BACKEND_INTERNAL_LOGIN_URL, json={'username': username},
                    headers={'X-Internal-API-Key': self.config.INTERNAL_SERVICE_API_KEY}, timeout=5)
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            logger.error(f"请求用户 '{username}' 的token失败: {e}", exc_info=True)
            return None

    def get_stream_key_from_url(self, url: str, source_type: str) -> Optional[str]:
        """从播放URL中提取流密钥。"""
        try:
            path = urlparse(url).path
            if source_type in ['flv', 'hls'] and (path.endswith('.flv') or path.endswith('.m3u8')):
                return os.path.splitext(os.path.basename(path))[0]
        except Exception as e:
            logger.error(f"从URL '{url}' 提取 stream key 失败: {e}")
        return None

    async def process_single_frame(
        self, frame: np.ndarray, camera_id: str, enable_face_recognition: bool,
        enable_object_detection: bool, enable_behavior_detection: bool,
        enable_fire_detection: bool, enable_liveness_detection: bool, **kwargs
    ) -> Dict[str, Any]:
        """处理单帧图像，执行所有已启用的AI分析。"""
        all_detections = []
        if enable_object_detection and self._detectors.get("object"):
            # 【修复】调用正确的方法名 predict
            all_detections.extend(self._detectors["object"].predict(frame))
        if enable_fire_detection and self._detectors.get("fire"):
            # 【确认】火焰检测器的方法名是 detect，此处调用正确
            all_detections.extend(self._detectors["fire"].detect(frame))
        if enable_face_recognition and self._detectors.get("face"):
            # 【确认】人脸识别器的方法名是 detect_and_recognize，此处调用正确
            face_results = self._detectors["face"].detect_and_recognize(frame, enable_liveness=enable_liveness_detection)
            for face in face_results:
                identity = face.get("identity", {})
                all_detections.append({
                    "type": "face_recognition", "class_name": identity.get("name", "unknown"),
                    "confidence": identity.get("confidence", 0.0), "coordinates": face.get("bbox"),
                    "details": identity,
                })
        # Placeholder for behavior detection
        # if enable_behavior_detection and self._detectors.get("behavior"):
        #     all_detections.extend(self._detectors["behavior"].detect(all_detections))
        return {"detections": all_detections}

    async def shutdown_services(self):
        """关闭所有正在运行的服务和视频流。"""
        logger.info("正在关闭所有AI服务...")
        with self._video_streams_lock:
            for cam_id, stream in self._video_streams.items():
                if stream.is_running:
                    logger.info(f"正在停止摄像头 {cam_id} 的视频流...")
                    await stream.stop()
        self._video_streams.clear()
        self._thread_pool.shutdown(wait=True)
        logger.info("所有服务已关闭。")

    def update_detectors(self):
        """用已经初始化的全局检测器实例来更新内部字典"""
        global object_detector, fire_detector, face_recognizer
        self._detectors["object"] = object_detector
        self._detectors["fire"] = fire_detector
        self._detectors["face"] = face_recognizer
        if self._detectors["behavior"] is None:
            self._detectors["behavior"] = BehaviorDetector()

    # The rest of the AIServiceManager methods will be here...
    # ... (all other methods from AIServiceManager) ...
    # We are showing just the changed parts for brevity.
    # The full content will be used in the final file overwrite.
    # ...
# (We assume all other methods of AIServiceManager are present here)

# --- FastAPI 应用生命周期管理器 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 的生命周期管理器。"""
    global face_recognizer, fire_detector, object_detector, tracker, danger_zone_detector, service_manager, app_config, known_faces_path
    print("--- 1. 服务器启动: 开始执行生命周期管理 ---")

    app_config = AppConfig()
    assets_path = app_config.ASSET_BASE_PATH
    
    # 确保 assets 目录和 known_faces 目录存在
    known_faces_path = os.path.join(assets_path, 'known_faces')
    os.makedirs(known_faces_path, exist_ok=True)
    
    service_manager = AIServiceManager(app_config)
    
    # --- 统一和修复所有模型的初始化 ---
    print(f"--- 准备初始化人脸识别器，资源根目录: {assets_path} ---")
    try:
        face_recognizer = FaceRecognizer(asset_base_path=assets_path)
    except Exception as e:
        logger.error(f"初始化 FaceRecognizer 时发生严重错误: {e}", exc_info=True)
        face_recognizer = None

    try:
        # 【核心修复】使用正确的相对路径加载火焰检测模型
        fire_model_path = os.path.join(assets_path, 'models', 'torch', 'best.pt') 
        if os.path.exists(fire_model_path):
            fire_detector = FlameSmokeDetector(assets_path=assets_path) # 传递根目录
            print(f"--- 火焰检测器初始化成功，使用模型: {fire_model_path} ---")
        else:
            fire_detector = None
            print(f"--- 警告: 未找到火焰检测器模型于 '{fire_model_path}' ---")
    except Exception as e:
        print(f"--- 错误: 初始化火焰检测器时失败: {e} ---")
        fire_detector = None

    #【核心修复】统一初始化ObjectDetector
    try:
        model_weights_path = os.path.join(assets_path, "models", "torch", "yolov8n.pt")
        STATION_SCENE_CLASSES = [
            "person", "bicycle", "car", "motorcycle", "bus", "truck",
            "traffic light", "fire hydrant", "stop sign", "parking meter",
            "bench", "backpack", "umbrella", "handbag", "suitcase"
        ]
        object_detector = ObjectDetector(
            model_weights_path=model_weights_path,
            allowed_classes=STATION_SCENE_CLASSES
        )
        logger.info(f"在lifespan中成功初始化并设置了object_detector，限定类别: {STATION_SCENE_CLASSES}")
    except Exception as e:
        logger.error(f"在lifespan中初始化 object_detector 时发生严重错误: {e}", exc_info=True)
        object_detector = None

    try:
        tracker = DeepSORTTracker()
    except Exception as e:
        logger.error(f"初始化 tracker 时发生严重错误: {e}", exc_info=True)
        tracker = None

    try:
        danger_zone_detector = DangerZoneDetector()
    except Exception as e:
        logger.error(f"初始化 danger_zone_detector 时发生严重错误: {e}", exc_info=True)
        danger_zone_detector = None

    service_manager.update_detectors()
    logger.info("所有模型和服务初始化完成。")

    cleanup_task = asyncio.create_task(start_cleanup_task())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
    if service_manager:
        await service_manager.shutdown_services()

# --- FastAPI App Creation ---
app = FastAPI(
    title="SmartEye AI服务",
    description="提供视频流分析、AI检测和人脸识别服务",
    version="1.0.0",
    lifespan=lifespan
)

# --- 【核心修复】添加CORS中间件 ---
# 允许来自前端开发服务器的跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局帧ID计数器
frame_id_counters = {}
async def process_video_stream_async_loop(stream: VideoStream, camera_id: str):
    """异步处理视频流循环，从VideoStream获取帧并送入分析器"""
    print(f"[{camera_id}] 异步处理循环已启动。")
    frame_process_counter = 0
    loop_counter = 0
    video_start_time = time.time()  # 记录视频开始时间
    last_known_detections = [] # 【新增】用于在跳过的帧上保留检测框
    
    # 初始化此摄像头的帧ID计数器
    if camera_id not in frame_id_counters:
        frame_id_counters[camera_id] = 0
        
    stream_initialized_sent = False  # 只发送一次初始化消息
    while stream.is_running:
        loop_counter += 1
        try:
            # 这里直接从 VideoStream 获取帧，VideoStream 内部负责读取
            frame_get_start_time = time.time()
            success, frame = stream.get_raw_frame()  # VideoStream 需要暴露这个方法
            frame_get_time = (time.time() - frame_get_start_time) * 1000
            
            if not success or frame is None:
                # 【新增】添加日志，以便调试
                if loop_counter % 100 == 0: # 每100次循环打印一次，避免刷屏
                    print(f"[{camera_id}] 未能获取帧. Success: {success}, Frame is None: {frame is None}. 耗时 {frame_get_time:.2f}ms. Retrying...")
                await asyncio.sleep(0.02)  # 短暂等待，避免空转
                continue
            
            # 【修复】首次获取到帧时，直接发送stream_initialized消息，确保它是顶级消息
            if not stream_initialized_sent:
                height, width = frame.shape[:2]  # 获取图像的高度和宽度
                init_message = {
                    "type": "stream_initialized",
                    "data": {
                        "camera_id": camera_id,
                        "resolution": {"width": width, "height": height}
                    }
                }
                # 【修复】此处不应直接调用 send_to_websocket，因为它会再次封装
                await service_manager.broadcast_via_backend(camera_id, init_message)
                stream_initialized_sent = True
                print(f"已发送视频流初始化消息，分辨率: {width}x{height}")

            frame_process_counter += 1
            processed_frame = frame.copy() # 先复制一份帧用于绘制

            # 每 X 帧处理一次，以平衡性能
            if frame_process_counter % DETECTION_FRAME_SKIP == 0:
                print(f"正在处理帧: {frame_process_counter} (摄像头: {camera_id})")

                frame_id = f"frame_{camera_id}_{frame_process_counter}"
                frame_timestamp = time.time()
                video_time = frame_timestamp - video_start_time
                
                settings = service_manager.get_ai_settings(camera_id)
                performance_mode = "fast" if settings.get('realtime_mode', True) else "balanced"
                
                detection_task = asyncio.create_task(
                    service_manager.process_single_frame(
                        frame=processed_frame,
                        camera_id=camera_id,
                        enable_face_recognition=settings.get('face_recognition', True),
                        enable_object_detection=settings.get('object_detection', True),
                        enable_behavior_detection=settings.get('behavior_analysis', False),
                        enable_fire_detection=settings.get('fire_detection', True),
                        # 在视频流中默认关闭活体，仅在专门的人脸验证场景开启
                        enable_liveness_detection=False,
                        performance_mode=performance_mode
                    )
                )

                results = await detection_task
                results["frame_id"] = frame_id
                results["frame_timestamp"] = frame_timestamp
                results["video_time"] = video_time
                
                for detection in results.get("detections", []):
                    detection["frame_id"] = frame_id
                    detection["frame_timestamp"] = frame_timestamp
                    detection["video_time"] = video_time
                
                last_known_detections = results.get("detections", [])
                
                # 只有在进行新检测时才发送详细结果到WebSocket
                await service_manager.send_detection_to_websocket(camera_id, results)

            # 【逻辑重构】总是在帧上绘制最新的检测框（或上一帧的框）
            draw_detections(processed_frame, last_known_detections)
            
            # 【逻辑重构】将最终的（可能是处理过的）帧推送到 WebRTC
            webrtc_pusher.push_frame(camera_id, processed_frame)
            
            await asyncio.sleep(0.01)
            
        except Exception as e:
            print(f"视频处理错误: {e}")
            traceback.print_exc()
            await asyncio.sleep(0.5)
    
    print(f"[{camera_id}] 视频流处理循环已停止 (is_running: {stream.is_running})。")


@app.post("/stream/stop/{camera_id}")
async def stop_stream(camera_id: str):
    if camera_id not in service_manager._video_streams:
        raise HTTPException(status_code=404, detail=f"未找到摄像头 {camera_id} 的视频流")

    # 关闭该摄像头的所有 WebRTC 连接
    await webrtc_pusher.close_all_camera_connections(camera_id)
    
    stream_processor = service_manager._video_streams[camera_id]
    await stream_processor.stop()  # VideoStream 内部会停止音频提取和帧循环

    del service_manager._video_streams[camera_id]
    if camera_id in service_manager._object_trackers:
        del service_manager._object_trackers[camera_id]
    if camera_id in service_manager._detection_cache:
        del service_manager._detection_cache[camera_id]
    print(f"已停止视频流: {stream_processor.stream_url}")
    return {"status": "success", "message": f"视频流处理已停止"}


# --- Pydantic Models for API ---
class LivenessFrame(BaseModel):
    """用于活体检测的单帧数据模型"""
    action: str = Field(..., description="该帧对应的动作指令, e.g., '请眨眨眼睛'")
    image_data: str = Field(..., description="该帧的Base64编码图像数据")

class FaceVerificationData(BaseModel):
    """人脸验证请求的数据模型 (增强版)"""
    primary_image: str = Field(..., description="用于身份识别的主要正面照 (Base64编码)")
    liveness_frames: List[LivenessFrame] = Field(..., description="用于活体检测的动作帧序列")

class FaceRegistrationResponse(BaseModel):
    """人脸注册响应的数据模型"""
    success: bool
    message: str
    person_id: Optional[str] = None
    
class FaceVerificationResponse(BaseModel):
    """人脸验证响应的数据模型"""
    success: bool
    message: str
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    user: Optional[Dict[str, Any]] = None

class FrameExtractionResponse(BaseModel):
    frames: List[str] = Field(..., description="从视频中提取的Base64编码的图像帧列表")

@app.post("/face/extract_frames/", response_model=FrameExtractionResponse, tags=["Face Recognition"])
async def extract_frames_from_video(video_file: UploadFile = File(...)):
    """
    从上传的视频文件中提取多个帧，用于用户手动选择。
    """
    logger.info("接收到视频帧提取请求...")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        content = await video_file.read()
        tmp.write(content)
        video_path = tmp.name

    extracted_frames = []
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="无法打开视频文件")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if total_frames == 0 or fps == 0:
            raise HTTPException(status_code=400, detail="视频文件无效或无法读取帧信息")

        # 目标是提取最多5个高质量帧
        target_indices = np.linspace(
            0, total_frames - 1, 
            min(5, total_frames) # 最多5帧，或视频总帧数
        ).astype(int)

        for idx in target_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                # 检查图像是否过暗或过亮
                if frame.mean() < 10 or frame.mean() > 245:
                    continue
                
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                encoded_string = base64.b64encode(buffer).decode("utf-8")
                extracted_frames.append(f"data:image/jpeg;base64,{encoded_string}")
        
    except Exception as e:
        logger.error(f"提取视频帧时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}")
    finally:
        if 'cap' in locals() and cap.isOpened():
            cap.release()
        os.unlink(video_path)

    if not extracted_frames:
        raise HTTPException(status_code=400, detail="无法从视频中提取任何有效的图像帧。")
        
    logger.info(f"成功从视频中提取了 {len(extracted_frames)} 帧。")
    return FrameExtractionResponse(frames=extracted_frames)

@app.get("/face/check/", tags=["Face Recognition"])
async def check_face_exists(username: str = Query(...), department: str = Query(...)):
    """
    检查指定用户是否已存在人脸数据。
    """
    person_id = f"{department}__{username}"
    user_dir = os.path.join(known_faces_path, person_id)
    
    # 检查目录是否存在且目录内有 .npy 文件
    exists = False
    if os.path.isdir(user_dir):
        for fname in os.listdir(user_dir):
            if fname.endswith(".npy"):
                exists = True
                break
                
    return {"exists": exists, "person_id": person_id}

@app.post("/face/register/", response_model=FaceRegistrationResponse, tags=["Face Recognition"])
async def register_face(
    username: str = Form(...),
    department: str = Form(...),
    face_image: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None)
):
    """
    接收用户提交的人脸图像或视频，进行注册。
    - 如果是图片，提取特征并保存。
    - 如果是视频，从中选出高质量的帧进行注册。
    """
    logger.info(f"开始为用户 '{username}' (部门: {department}) 处理人脸注册请求。")
    if not face_recognizer:
        logger.error("Face recognizer is not initialized.")
        raise HTTPException(status_code=503, detail="人脸识别服务当前不可用")

    if not face_image and not video_file:
        raise HTTPException(status_code=400, detail="必须提供人脸图片或视频文件")

    # 关键修复：不再拼接部门信息，直接使用纯粹的username作为唯一标识
    person_id = username

    try:
        if face_image:
            image_bytes = await face_image.read()
            result = face_recognizer.register_new_face(person_id, image_bytes)
        
        elif video_file:
            video_bytes = await video_file.read()
            result = face_recognizer.register_from_video(person_id, video_bytes)

        if result and result.get("success"):
            logger.info(f"用户 '{person_id}' 的人脸已成功注册。")
            # 重新加载人脸数据，确保新注册的人脸可用
            await service_manager.reload_face_recognizer()
            return FaceRegistrationResponse(success=True, message=result.get("message", "人脸注册成功"), person_id=person_id)
        else:
            error_message = result.get("message", "注册失败，未知原因。")
            logger.warning(f"为用户 '{person_id}' 注册人脸失败: {error_message}")
            raise HTTPException(status_code=400, detail=error_message)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"处理人脸注册时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@app.post("/face/verify", response_model=FaceVerificationResponse, tags=["Face Recognition"])
async def verify_face(data: FaceVerificationData):
    """
    通过人脸图像验证用户身份并执行活体检测。
    """
    try:
        face_recognizer = service_manager._detectors.get("face")
        if not face_recognizer:
            return {"success": False, "message": "人脸识别服务未初始化"}

        # 1. 解码主要识别图像并进行身份验证
        primary_image_data = base64.b64decode(data.primary_image)
        primary_image = cv2.imdecode(np.frombuffer(primary_image_data, np.uint8), cv2.IMREAD_COLOR)
        if primary_image is None:
            return {"success": False, "message": "无法解码用于识别的主图像"}
        
        recognized_faces = face_recognizer.detect_and_recognize(primary_image)
        
        best_match = None
        if recognized_faces:
            for face in recognized_faces:
                identity = face.get("identity", {})
                if identity.get("is_known"):
                    if best_match is None or identity.get("confidence", 0) > best_match.get("identity", {}).get("confidence", 0):
                        best_match = face

        if not best_match:
            logger.warning("人脸验证失败：未匹配到任何已知用户。")
            return {"success": False, "message": "未识别到注册用户，请重试"}

        # 2. 身份验证成功，开始进行活体检测
        liveness_passed_count = 0
        total_liveness_checks = len(data.liveness_frames)
        
        for frame_data in data.liveness_frames:
            action = frame_data.action
            liveness_image_data = base64.b64decode(frame_data.image_data)
            liveness_image = cv2.imdecode(np.frombuffer(liveness_image_data, np.uint8), cv2.IMREAD_COLOR)
            
            if liveness_image is None:
                logger.warning(f"活体检测解码失败，动作: {action}")
                continue # 跳过解码失败的帧

            if face_recognizer.verify_liveness_action(liveness_image, action):
                liveness_passed_count += 1
                logger.info(f"✅ 活体检测动作 '{action}' 验证通过。")
            else:
                logger.warning(f"❌ 活体检测动作 '{action}' 验证失败。")

        # 验证通过率可以自定义，例如要求全部通过
        if liveness_passed_count < total_liveness_checks:
            return {"success": False, "message": f"活体检测失败，请按提示完成所有动作。({liveness_passed_count}/{total_liveness_checks} 通过)"}

        # 3. 身份和活体均验证通过
        person_id = best_match["identity"]["name"]
        confidence = best_match["identity"]["confidence"]
        logger.info(f"人脸验证和活体检测全部通过: ID='{person_id}', 置信度='{confidence:.2f}'")

        # 【核心变更】person_id 现在直接就是 username
        username = person_id

        # 4. 【修复】调用主后端服务进行内部登录，使用实际识别出的用户名
        try:
            logger.info(f"准备为识别出的用户 '{username}' 请求内部登录以获取Token。")
            try:
                # 使用识别出的`username`
                response = requests.post(
                    service_manager.config.BACKEND_INTERNAL_LOGIN_URL,
                    json={'username': username},
                    headers={'X-Internal-API-Key': service_manager.config.INTERNAL_SERVICE_API_KEY},
                    timeout=5
                )
                response.raise_for_status()

                # 5. 直接透传主后端返回的数据
                backend_data = response.json()
                logger.info(f"从主后端获取到登录凭证，用户: {username}")
                
                return {
                    "success": True,
                    "message": "登录成功",
                    "token": backend_data.get('access'),
                    "refresh_token": backend_data.get('refresh'),
                    "user": backend_data.get('user')
                }

            except requests.exceptions.RequestException as e:
                logger.error(f"调用主后端内部登录接口失败: {e}", exc_info=True)
                error_message = "无法连接认证服务器，请稍后重试。"
                if e.response:
                    try:
                        error_detail = e.response.json().get('error', '未知认证错误')
                        error_message = f"认证失败: {error_detail}"
                    except json.JSONDecodeError:
                        error_message = f"认证服务器返回格式错误 (状态码: {e.response.status_code})"
                
                return {"success": False, "message": error_message}

        except Exception as e:
            logger.error(f"人脸验证API出现异常: {e}", exc_info=True)
            return {"success": False, "message": f"服务器内部错误: {e}"}

    except Exception as e:
        logger.error(f"人脸验证API出现异常: {e}", exc_info=True)
        return {"success": False, "message": f"服务器内部错误: {e}"}


@app.websocket("/ws/face_verification")
async def face_verification_ws(websocket: WebSocket):
    """
    通过WebSocket进行实时人脸验证。
    接收视频帧，进行活体检测和识别，并返回实时状态。
    """
    await websocket.accept()
    liveness_session = LivenessSession(timeout=15.0, num_challenges=2)
    # <--- FIX: No longer getting from service_manager._detectors as it is globally available
    
    if not face_recognizer:
        await websocket.send_json({"status": "failed", "message": "人脸识别服务未初始化"})
        await websocket.close()
        return

    print(f"开启新的活体检测会话: {liveness_session.session_id}")
    
    try:
        # 主循环，处理挑战和帧数据
        while not liveness_session.is_finished() and not liveness_session.is_timed_out():
            
            # 1. 发送当前挑战给前端
            current_challenge = liveness_session.get_current_challenge()
            challenge_map = {
                "blink": "请眨动您的眼睛",
                "shake_head": "请左右摇头",
                "nod_head": "请上下点头",
                "open_mouth": "请张开您的嘴巴"
            }
            await websocket.send_json({
                "status": "challenge", 
                "challenge": current_challenge,
                "message": challenge_map.get(current_challenge, "准备进行验证")
            })

            challenge_start_time = time.time()
            challenge_timeout = 7.0  # 每个动作的超时时间

            # 2. 等待并处理客户端视频帧，直到当前挑战完成或超时
            action_completed = False
            while not action_completed and time.time() - challenge_start_time < challenge_timeout:
                try:
                    # 使用 wait_for 确保接收操作不会无限期阻塞
                    # --- FIX: Changed from websocket.receive() to websocket.receive_bytes() ---
                    # This correctly handles the binary data being sent from the frontend.
                    frame_bytes = await asyncio.wait_for(websocket.receive_bytes(), timeout=1.0)
                    
                    if frame_bytes:
                        nparr = np.frombuffer(frame_bytes, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                        if frame is None:
                            logger.warning("接收到无法解码的视频帧。")
                            continue

                        # 进行人脸检测和关键点提取
                        landmarks, head_pose = face_recognizer.get_landmarks_and_pose(frame)
                        
                        if landmarks is not None and head_pose is not None:
                            liveness_session.process_frame(landmarks, head_pose)
                            if liveness_session.get_current_challenge() != current_challenge:
                                action_completed = True # 挑战已切换，说明当前动作完成
                        else:
                            await websocket.send_json({"status": "info", "message": "请将面部保持在画面中央"})
                
                except asyncio.TimeoutError:
                    if liveness_session.is_timed_out() or (time.time() - challenge_start_time > challenge_timeout):
                        liveness_session.failure_reason = f"challenge_timeout:{current_challenge}"
                        break
                    continue # 只是接收帧超时，继续等待
                except WebSocketDisconnect:
                    liveness_session.failure_reason = "client_disconnected"
                    print("客户端在挑战中意外断开")
                    raise  # 抛出异常，由外层 finally 处理

            if not action_completed:
                liveness_session.failure_reason = f"challenge_timeout:{current_challenge}"
                break

        # --- 循环结束，进行最终判断 ---
        if liveness_session.is_successful:
            await websocket.send_json({"status": "verifying", "message": "活体检测通过，正在进行身份识别..."})
            
            # 请求最后一张图片用于识别
            final_frame_data = await websocket.receive_bytes()
            nparr = np.frombuffer(final_frame_data, np.uint8)
            final_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            user_info = face_recognizer.recognize_in_frame(final_frame)
            
            # 关键修复：直接使用识别出的用户名（identity），不再进行任何拼接
            if user_info and user_info.get("identity") and user_info.get("identity") != "Unknown":
                recognized_username = user_info["identity"]
                logger.info(f"准备为用户 '{recognized_username}' 请求内部登录以获取Token。")
                token_data = await service_manager.get_user_token(recognized_username)
                if token_data:
                    await websocket.send_json({"status": "success", "message": "验证成功", **token_data})
                else:
                    await websocket.send_json({"status": "failed", "message": "获取用户凭证失败"})
            else:
                await websocket.send_json({"status": "failed", "message": "未识别到已注册用户"})
        else:
            failure_message = f"活体检测失败: {liveness_session.failure_reason}"
            await websocket.send_json({"status": "failed", "message": failure_message})
            
            # 【核心修复】添加 await
            await service_manager.send_alert_to_backend(
                AIAnalysisResult(
                    camera_id="FaceAuth", # 特殊标识
                    event_type="spoofing_attempt",
                    level="high",
                    timestamp=datetime.now().isoformat(),
                    details={
                        "message": "人脸识别登录时发生欺骗攻击尝试",
                        "reason": liveness_session.failure_reason,
                        "session_id": liveness_session.session_id
                    }
                )
            )

    except WebSocketDisconnect:
        print("客户端断开连接。")
    except Exception as e:
        print(f"WebSocket处理中发生未知错误: {e}")
        traceback.print_exc()
    finally:
        print(f"关闭会话: {liveness_session.session_id}，原因: {liveness_session.failure_reason or '正常结束'}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()


# --- 【核心修复】修改视频流连接测试端点 ---
@app.post("/stream/test/")
async def test_stream_connection_endpoint(url: str = Body(...), type: str = Body(...)):
    print(f"正在测试视频流连接: {url} (类型: {type})")

    # 自动将播放URL转换为AI服务需要的RTMP源URL
    source_url_for_ai = url
    stream_key = service_manager.get_stream_key_from_url(url, type)
    if stream_key and type in ['hls', 'flv']:
        source_url_for_ai = f"rtmp://localhost:1935/live/{stream_key}"
        print(f"测试连接: 检测到播放URL，已自动转换为AI服务的源URL: {source_url_for_ai}")

    stream = VideoStream(stream_url=source_url_for_ai, camera_id="test_connection_id")
    is_available = await stream.test_connection()
    
    # 无论成功失败，都返回200 OK，通过内容告诉前端结果
    if is_available:
        return {"status": "success", "message": "视频流可用"}
    else:
        return {"status": "error", "message": f"无法连接到视频流: {source_url_for_ai}"}


# --- 【核心修复】修改启动视频流处理端点 ---
@app.post("/stream/start/")
async def start_stream_endpoint(
    camera_id: str = Body(...),
    stream_url: str = Body(...),
    source_type: str = Body(...), # <--【新增】获取前端传入的原始类型
    enable_face_recognition: bool = Body(True),
    enable_object_detection: bool = Body(True),
    enable_behavior_detection: bool = Body(False),
    enable_fire_detection: bool = Body(True),
    enable_sound_detection: bool = Body(False),
    enable_liveness_detection: bool = Body(True)
):
    """启动视频流处理"""
    if camera_id in service_manager._video_streams:
        await service_manager._video_streams[camera_id].stop()
        del service_manager._video_streams[camera_id]

    # 自动将播放URL转换为AI服务需要的RTMP源URL
    source_url_for_ai = stream_url
    stream_key = service_manager.get_stream_key_from_url(stream_url, source_type)
    if stream_key and source_type in ['hls', 'flv']:
        source_url_for_ai = f"rtmp://localhost:1935/live/{stream_key}"
        print(f"启动流: 检测到播放URL，已自动转换为AI服务的源URL: {source_url_for_ai}")

    print(f"正在启动视频流: {source_url_for_ai} (摄像头ID: {camera_id})")
    
    stream_processor = VideoStream(
        stream_url=source_url_for_ai, # <-- 使用转换后的URL
        camera_id=camera_id,
    )
    
    service_manager._video_streams[camera_id] = stream_processor
    
    if camera_id not in service_manager._object_trackers:
        service_manager._object_trackers[camera_id] = DeepSORTTracker(max_age=30, n_init=3)
        
    # 【关键修复】必须调用 start() 方法来启动视频流的后台读取线程
    # 并检查其是否成功启动
    if not await stream_processor.start():
        # 如果启动失败，从管理器中移除实例并返回错误
        del service_manager._video_streams[camera_id]
        raise HTTPException(status_code=500, detail=f"无法启动视频流: {stream_url}")
        
    asyncio.create_task(process_video_stream_async_loop(stream_processor, camera_id))
    
    return {"status": "success", "message": f"视频流处理已在后台启动"}


# 添加一个健康检查接口
@app.get("/system/status/")
async def get_system_status():
    """
    获取系统状态，主要用于前端检查视频流是否准备好进行WebRTC推流。
    """
    try:
        if not service_manager:
            logger.warning("get_system_status called before service_manager is initialized.")
            raise HTTPException(status_code=503, detail="服务尚未完全初始化，请稍后再试。")

        active_running_streams = {}
        # 使用锁来安全地访问共享的 _video_streams 字典
        with service_manager._video_streams_lock:
            # 在锁内，我们仍然使用 .copy() 来迭代，这是一种更安全的做法，可以防止在 future 的某些实现中出现意外的副作用。
            active_running_streams = {
                cam_id: stream
                for cam_id, stream in service_manager._video_streams.copy().items()
                if stream.is_running
            }
        
        # 构建前端期望的响应结构。
        response_data = {
            "status": "ok",
            "active_streams": len(active_running_streams),
            "frame_buffers": {cam_id: {"is_ready": True} for cam_id in active_running_streams}
        }
        
        logger.debug(f"Returning system status: {response_data}")
        return response_data
    except Exception as e:
        logger.error(f"获取系统状态时发生严重错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取系统状态时发生内部服务器错误。")


@app.post("/alerts/")
async def create_alert(alert: AIAnalysisResult):
    """
    创建新的告警通知。
    """
    try:
        # 将告警通知发送给后端
        await service_manager.send_alert_to_backend(alert)
        return {"status": "success", "message": "告警通知已成功发送"}
    except Exception as e:
        logger.error(f"创建告警通知时发生错误: {e}", exc_info=True)
        return {"status": "error", "message": f"服务器内部错误: {e}"}


# AI分析设置
@app.post("/frame/analyze/settings/{camera_id}")
async def update_ai_settings(camera_id: str, settings: AISettings = Body(...)):
    """更新AI分析设置并将其传播到视频流"""
    # 【核心修复】使用 exclude_unset=True 来获取一个只包含客户端实际发送字段的字典
    update_data = settings.model_dump(exclude_unset=True)
    
    updated_settings = service_manager.update_stream_settings(camera_id, update_data)
    
    if updated_settings:
        return {"status": "success", "message": "AI分析设置已更新", "settings": updated_settings}
    else:
        # 如果视频流不存在，仍然更新全局设置，以便在流启动时使用
        service_manager.update_ai_settings(camera_id, update_data)
        return {
            "status": "success",
            "message": "AI分析设置已为未来的流更新",
            "settings": service_manager.get_ai_settings(camera_id)
        }


@app.get("/frame/analyze/settings/{camera_id}")
async def get_ai_settings(camera_id: str):
    """获取指定摄像头的AI分析配置"""
    settings = service_manager.get_ai_settings(camera_id)
    return settings


# 添加 WebRTC 相关的 API 端点
class WebRTCSessionDescription(BaseModel):
    """WebRTC 会话描述模型"""
    sdp: str
    type: str

class WebRTCConnectionResponse(BaseModel):
    """WebRTC 连接响应模型"""
    connection_id: str
    sdp: str
    type: str

@app.post("/webrtc/offer/{camera_id}", response_model=WebRTCConnectionResponse, tags=["WebRTC"])
async def create_webrtc_offer(camera_id: str):
    """
    为指定摄像头创建 WebRTC offer
    """
    logger.info(f"正在为摄像头 {camera_id} 创建WebRTC offer")
    
    # 检查摄像头是否存在
    if camera_id not in service_manager._video_streams:
        error_msg = f"未找到摄像头 {camera_id} 的视频流"
        logger.error(error_msg)
        raise HTTPException(status_code=404, detail=error_msg)
    
    try:
        # 确保视频流中有数据
        stream = service_manager._video_streams[camera_id]
        success, _ = stream.get_raw_frame()
        if not success:
            logger.warning(f"摄像头 {camera_id} 尚未接收到视频帧，WebRTC连接可能没有内容")
        
        # 创建 WebRTC offer
        offer_data = await webrtc_pusher.create_offer(camera_id)
        logger.info(f"为摄像头 {camera_id} 创建WebRTC offer成功，连接ID: {offer_data['connection_id']}")
        
        return {
            "connection_id": offer_data["connection_id"],
            "sdp": offer_data["sdp"],
            "type": offer_data["type"]
        }
    except Exception as e:
        error_msg = f"创建WebRTC offer失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/webrtc/answer/{connection_id}", tags=["WebRTC"])
async def process_webrtc_answer(connection_id: str, answer: WebRTCSessionDescription):
    """
    处理来自浏览器的 WebRTC answer
    """
    logger.info(f"正在处理连接ID {connection_id} 的WebRTC answer")
    
    try:
        success = await webrtc_pusher.process_answer(connection_id, answer.sdp, answer.type)
        if not success:
            error_msg = f"处理WebRTC answer失败，可能是连接ID {connection_id} 不存在"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
        logger.info(f"成功处理连接ID {connection_id} 的WebRTC answer")
        return {"status": "success", "message": "WebRTC连接已建立"}
    except Exception as e:
        error_msg = f"处理WebRTC answer时发生错误: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)

@app.delete("/webrtc/connection/{connection_id}", tags=["WebRTC"])
async def close_webrtc_connection(connection_id: str):
    """
    关闭指定的 WebRTC 连接
    """
    logger.info(f"正在关闭WebRTC连接 {connection_id}")
    
    try:
        await webrtc_pusher.close_connection(connection_id)
        logger.info(f"已成功关闭WebRTC连接 {connection_id}")
        return {"status": "success", "message": f"已关闭WebRTC连接 {connection_id}"}
    except Exception as e:
        error_msg = f"关闭WebRTC连接时发生错误: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # 即使发生错误，也返回成功，因为客户端已经断开连接
        return {"status": "success", "message": f"尝试关闭WebRTC连接 {connection_id}，但发生错误: {str(e)}"}

# 添加一个新的调试接口
@app.get("/webrtc/status", tags=["WebRTC"])
async def get_webrtc_status():
    """
    获取当前WebRTC连接的状态信息
    """
    try:
        # 确保导入了必要的模块和变量
        from smart_station_platform.ai_service.core.webrtc_pusher import active_connections, frame_buffers
        
        active_count = len(active_connections)
        active_cameras = {}
        
        # 统计每个摄像头的连接数
        for connection_id, data in active_connections.items():
            camera_id = data.get("camera_id", "unknown")
            if camera_id not in active_cameras:
                active_cameras[camera_id] = []
            active_cameras[camera_id].append(connection_id)
        
        # 统计帧缓冲区信息
        buffer_info = {}
        for camera_id, frame in frame_buffers.items():
            if frame is not None:
                height, width = frame.shape[:2]
                buffer_info[camera_id] = {
                    "width": width,
                    "height": height,
                    "channels": frame.shape[2] if len(frame.shape) > 2 else 1,
                    "dtype": str(frame.dtype)
                }
        
        return {
            "active_connections": active_count,
            "active_cameras": {camera_id: len(connections) for camera_id, connections in active_cameras.items()},
            "connection_details": {camera_id: connections for camera_id, connections in active_cameras.items()},
            "frame_buffers": buffer_info
        }
    except Exception as e:
        logger.error(f"获取WebRTC状态时出错: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=200,  # 即使出错也返回200，避免前端因错误状态码而不显示错误消息
            content={
                "status": "error",
                "message": f"获取WebRTC状态时出错: {str(e)}",
                "error_detail": traceback.format_exc()
            }
        )


if __name__ == "__main__":
    # 启动Uvicorn服务器
    # 监听所有网络接口(0.0.0.0)，端口为8002
    # 注意：在生产环境中，建议关闭热重载 (reload=False)
    # 【修复】为了启用热重载(reload=True)，必须以字符串形式传递应用 "文件名:FastAPI实例名"
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=True)

