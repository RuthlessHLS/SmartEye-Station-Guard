import datetime
import os
import base64
import time
import asyncio
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import torch
import uvicorn
import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Body, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 导入我们自定义的所有核心AI模块
import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.video_stream import VideoStream
from core.object_detection import GenericPredictor
from core.behavior_detection import BehaviorDetector
from core.face_recognition import FaceRecognizer
from core.acoustic_detection import AcousticEventDetector  # 更新为新的类名
from models.alert_models import AIAnalysisResult  # 确保这个文件存在

# 在应用启动时，从 .env 文件加载环境变量
current_dir = os.path.dirname(os.path.abspath(__file__))
# 构建 .env 文件的完整路径
dotenv_path = os.path.join(current_dir, '.env')
# 从指定路径加载环境变量
if os.path.exists(dotenv_path):
    print(f"--- 正在从 '{dotenv_path}' 加载环境变量 ---")
    load_dotenv(dotenv_path=dotenv_path)
else:
    print(f"--- 警告: 未找到 .env 文件 at '{dotenv_path}'，将使用系统环境变量 ---")
load_dotenv()

# --- 全局变量 ---
video_streams: Dict[str, VideoStream] = {}
detectors: Dict[str, object] = {}
thread_pool = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)


# --- FastAPI 应用生命周期管理 ---

def init_detectors():
    """初始化所有AI检测器模型。这个函数在服务启动时只执行一次。"""
    try:
        print("--- 正在初始化所有检测器 ---")


        # 我们不再硬编码任何路径，而是从 .env 文件中读取统一的根路径。
        ASSET_BASE_PATH = os.getenv("G_DRIVE_ASSET_PATH")
        if not ASSET_BASE_PATH or not os.path.isdir(ASSET_BASE_PATH):
            raise FileNotFoundError(
                f"致命错误: 环境变量 'G_DRIVE_ASSET_PATH' 指向的资源目录 '{ASSET_BASE_PATH}' 不存在或未配置。请检查 .env 文件和G盘目录。")

        print(f"--- 使用资源根目录: {ASSET_BASE_PATH} ---")

        # 所有资源的路径都将基于 ASSET_BASE_PATH 构建，实现集中管理。
        model_weights_path = os.path.join(ASSET_BASE_PATH, "models", "torch",
                                          "fasterrcnn_resnet50_fpn_coco-258fb6c6.pth")
        class_names_path = os.path.join(ASSET_BASE_PATH, "models", "coco.names")
        known_faces_dir = os.path.join(ASSET_BASE_PATH, "known_faces")

        # 1. 初始化通用目标检测器
        class_names = []
        try:
            with open(class_names_path, 'r', encoding='utf-8') as f:
                class_names = [line.strip() for line in f.readlines()]
            print(f"成功从 '{class_names_path}' 加载 {len(class_names)} 个类别名称。")
        except FileNotFoundError:
            print(f"警告: 找不到类别名称文件 at '{class_names_path}'。")
            # 即使找不到文件，也提供一个基础的默认值以维持运行
            class_names = ["background", "person"]

        # 使用YOLOv8模型
        model_weights_path = os.path.join(ASSET_BASE_PATH, "models", "torch", "yolov8n.pt")
        print(f"正在加载YOLOv8模型权重: {model_weights_path}")

        detectors["object"] = GenericPredictor(
            model_weights_path=model_weights_path,
            num_classes=len(class_names),
            class_names=class_names
        )

        # 2. 初始化行为检测器
        detectors["behavior"] = BehaviorDetector()

        # 3. 初始化人脸识别器
        print(f"正在从目录 '{known_faces_dir}' 加载已知人脸。")
        detectors["face"] = FaceRecognizer(
            known_faces_dir=known_faces_dir  # 使用我们新构建的路径
        )

        # 4. 初始化声学事件检测器 (如果启用了)
        if os.getenv("ENABLE_SOUND_DETECTION", "false").lower() == "true":
            try:
                acoustic_detector = AcousticEventDetector()  # 使用新的类名
                detectors["acoustic"] = acoustic_detector
            except Exception as e:
                print(f"警告: 声学检测器初始化失败，将禁用此功能。错误: {e}")

        print("--- 所有检测器初始化完成 ---")

    except Exception as e:
        print(f"致命错误: 检测器初始化失败: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 的生命周期管理器。"""
    # 启动任务
    init_detectors()
    # 移除对 start_listening 的调用，因为我们现在使用 process_audio_file 方法
    if "acoustic" in detectors:
        asyncio.create_task(run_acoustic_analysis())

    yield  # 服务在此运行时，处理API请求

    # 关闭任务
    print("服务正在关闭，开始清理资源...")
    for stream in video_streams.values():
        stream.stop()
    if "acoustic" in detectors:
        detectors["acoustic"].stop_monitoring()  # 使用正确的方法名
    thread_pool.shutdown(wait=True)
    print("资源清理完毕。")


# 创建FastAPI应用实例
app = FastAPI(
    title="AI 智能分析服务 (最终版)",
    description="提供视频流处理、目标检测、行为识别、人脸识别和声学事件检测能力",
    version="2.0.0",
    lifespan=lifespan
)

# 添加CORS中间件以支持前端跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # 允许前端域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有头部
)


# --- 数据模型 (保持不变) ---

class StreamConfig(BaseModel):
    camera_id: str
    stream_url: str
    enable_face_recognition: bool = True
    enable_behavior_detection: bool = True


class FaceData(BaseModel):
    person_name: str
    image_data: str


# --- 核心函数 (保持不变) ---

def send_result_to_backend(result: AIAnalysisResult):
    """将分析结果异步发送到后端Django服务。"""

    def task():
        backend_url = os.getenv("DJANGO_BACKEND_URL", "http://127.0.0.1:8000/api/alerts/ai-results/")
        try:
            response = requests.post(backend_url, json=result.model_dump(), timeout=10)
            if 200 <= response.status_code < 300:
                print(f"✅ [结果上报] 成功发送事件 '{result.event_type}' 到后端。")
            else:
                print(f"❌ [结果上报] 发送失败，状态码: {response.status_code}, 后端响应: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"❌ [请求异常] 无法连接到后端服务: {e}")

    thread_pool.submit(task)


async def run_acoustic_analysis():
    """在后台持续运行的协程，用于分析音频数据。"""
    print("声学分析后台任务已启动。")
    acoustic_detector = detectors.get("acoustic")
    if not acoustic_detector: 
        return

    while True:  # 持续运行，直到服务停止
        try:
            for stream in video_streams.values():
                # 检查流对象是否支持音频文件处理
                if not hasattr(stream, 'get_audio_file'):
                    # 跳过不支持音频的流（如WebcamProcessor）
                    continue
                    
                audio_file = stream.get_audio_file()
                if audio_file and os.path.exists(audio_file):
                    events = await acoustic_detector.process_audio_file(audio_file)
                    for event in events:
                        # 根据事件类型选择不同的emoji
                        event_emoji = {
                            "volume_anomaly": "📢",
                            "high_frequency_noise": "🔊",
                            "sudden_noise": "💥"
                        }.get(event['type'], "🔔")
                        
                        print(f"{event_emoji} [音频] {event['description']}")
                        print(f"   - 类型: {event['type']}")
                        print(f"   - 时间: {datetime.datetime.fromtimestamp(event['timestamp']).strftime('%H:%M:%S')}")
                        print(f"   - 置信度: {event['confidence']:.2f}")
                        
                        alert = AIAnalysisResult(
                            camera_id=stream.camera_id,
                            event_type=f"acoustic_{event['type']}",
                            location={"timestamp": event['timestamp']},
                            confidence=event['confidence'],
                            timestamp=datetime.datetime.now().isoformat(),
                            details={
                                "description": event['description'],
                                "audio_timestamp": event['timestamp']
                            }
                        )
                        send_result_to_backend(alert)
                else:
                    # 只对真正的视频流显示音频文件未找到的警告
                    print(f"⚠️ 未找到音频文件: {audio_file}")
        except Exception as e:
            print(f"声学分析过程中发生错误: {e}")
            traceback.print_exc()
        
        await asyncio.sleep(5)  # 每5秒检查一次，减少检测频率


def create_master_processor(camera_id: str, config: StreamConfig):
    """
    创建一个主AI处理器，它负责协调调用所有视觉相关的AI检测器。
    """

    def master_processor(frame: np.ndarray):
        try:
            # 目标检测
            detected_objects = detectors["object"].predict(frame, confidence_threshold=0.6)

            # 打印检测到的目标
            for obj in detected_objects:
                print(f"🎯 检测到 {obj['class_name']}: 置信度={obj['confidence']:.2f}, 位置={obj['coordinates']}")

            # 行为检测
            if config.enable_behavior_detection:
                person_boxes = [obj["coordinates"] for obj in detected_objects if obj["class_name"] == "person"]
                if person_boxes:
                    behaviors = detectors["behavior"].detect_behavior(frame, person_boxes, time.time())
                    for behavior in behaviors:
                        if behavior["is_abnormal"] and behavior["need_alert"]:
                            print(f"🚨 [{camera_id}] 检测到异常行为: {behavior['behavior']}!")
                            alert = AIAnalysisResult(
                                camera_id=camera_id,
                                event_type=f"abnormal_behavior_{behavior['behavior']}",
                                location={"box": behavior["box"]},
                                confidence=behavior["confidence"],
                                timestamp=datetime.datetime.now().isoformat(),
                            )
                            send_result_to_backend(alert)

            if config.enable_face_recognition:
                recognized_faces = detectors["face"].detect_and_recognize(frame)
                for face in recognized_faces:
                    if not face["identity"]["known"]:  # 修改这里，使用新的判断逻辑
                        print(f"🚨 [{camera_id}] 检测到未知人员!")
                        alert = AIAnalysisResult(
                            camera_id=camera_id,
                            event_type="unknown_face_detected",
                            location={
                                "box": [
                                    face["location"]["left"],
                                    face["location"]["top"],
                                    face["location"]["right"],
                                    face["location"]["bottom"]
                                ]
                            },
                            confidence=face.get("confidence", 0.9),
                            timestamp=datetime.datetime.now().isoformat(),
                            details={
                                "face_location": face["location"],
                                "best_match": face.get("best_match")
                            }
                        )
                        send_result_to_backend(alert)

        except Exception as e:
            print(f"处理帧时发生致命错误 [{camera_id}]: {e}")

    return master_processor


# --- API 端点 (保持不变) ---

@app.post("/stream/start/")
async def start_stream(
    camera_id: str = Body(...),
    stream_url: str = Body(...),
    enable_face_recognition: bool = Body(default=True),
    enable_behavior_detection: bool = Body(default=True),
    enable_sound_detection: bool = Body(default=True)  # 默认启用声音检测
):
    """启动视频流处理。"""
    if camera_id in video_streams:
        return {"status": "error", "message": f"摄像头 {camera_id} 已在运行"}

    def master_processor(frame: np.ndarray):
        try:
            # 目标检测 (提高置信度阈值到 0.85)
            detected_objects = detectors["object"].predict(frame, confidence_threshold=0.85)
            
            # 过滤掉一些可能的误报
            filtered_objects = []
            for obj in detected_objects:
                # 1. 检查目标大小是否合理
                box = obj["coordinates"]
                width = box[2] - box[0]
                height = box[3] - box[1]
                area_ratio = (width * height) / (frame.shape[0] * frame.shape[1])
                
                # 如果目标占据了超过80%的画面，可能是误报
                if area_ratio > 0.8:
                    continue
                    
                # 2. 对特定类别应用更严格的置信度要求
                if obj["class_name"] in ["bicycle", "sports ball", "bird", "traffic light"]:
                    if obj["confidence"] < 0.9:  # 对这些容易误报的类别要求更高的置信度
                        continue
                
                filtered_objects.append(obj)
            
            # 人脸识别（提前进行，以便与人物检测结果关联）
            recognized_faces = []
            if enable_face_recognition:
                recognized_faces = detectors["face"].detect_and_recognize(frame)

            # 处理检测到的目标
            for obj in filtered_objects:
                if obj["class_name"] == "person":
                    # 对人物进行身份识别
                    person_box = obj["coordinates"]
                    person_identity = "未知人员"
                    
                    for face in recognized_faces:
                        face_box = face["location"]
                        # 计算人脸框的中心点（注意：face_box格式为{top, right, bottom, left}）
                        face_center_x = (face_box["left"] + face_box["right"]) / 2
                        face_center_y = (face_box["top"] + face_box["bottom"]) / 2
                        
                        # 检查人脸中心点是否在人物框内，添加一些容差
                        # 有时YOLO的人物框可能比实际略小，所以我们扩大检查范围
                        box_width = person_box[2] - person_box[0]
                        box_height = person_box[3] - person_box[1]
                        tolerance_x = box_width * 0.1  # 10%的容差
                        tolerance_y = box_height * 0.1
                        
                        if (face_center_x >= (person_box[0] - tolerance_x) and 
                            face_center_x <= (person_box[2] + tolerance_x) and
                            face_center_y >= (person_box[1] - tolerance_y) and 
                            face_center_y <= (person_box[3] + tolerance_y)):
                            if face["identity"]["known"]:
                                person_identity = face["identity"]["name"]
                                print(f"✅ 成功匹配人脸到人物框: {person_identity}")
                                print(f"   人脸位置: ({face_center_x:.0f}, {face_center_y:.0f})")
                                print(f"   人物框: {person_box}")
                            break
                    
                    print(f"🎯 检测到人员 [{person_identity}]: 置信度={obj['confidence']:.2f}, 位置={obj['coordinates']}")
                    
                    # 如果是未知人员，发送告警
                    if person_identity == "未知人员":
                        alert = AIAnalysisResult(
                            camera_id=camera_id,
                            event_type="unknown_person_detected",
                            location={"box": person_box},
                            confidence=obj["confidence"],
                            timestamp=datetime.datetime.now().isoformat(),
                        )
                        send_result_to_backend(alert)
                else:
                    # 其他物体只显示基本检测信息
                    print(f"🎯 检测到物体 [{obj['class_name']}]: 置信度={obj['confidence']:.2f}, 位置={obj['coordinates']}")

            # 行为检测
            if enable_behavior_detection:
                person_boxes = [obj["coordinates"] for obj in filtered_objects if obj["class_name"] == "person"]
                if person_boxes:
                    behaviors = detectors["behavior"].detect_behavior(frame, person_boxes)  # 移除time.time()参数
                    for behavior in behaviors:
                        if behavior["is_abnormal"] and behavior["need_alert"]:
                            print(f"🚨 [{camera_id}] 检测到异常行为: {behavior['behavior']}!")
                            alert = AIAnalysisResult(
                                camera_id=camera_id,
                                event_type=f"abnormal_behavior_{behavior['behavior']}",
                                location={"box": behavior["box"]},
                                confidence=behavior["confidence"],
                                timestamp=datetime.datetime.now().isoformat(),
                            )
                            send_result_to_backend(alert)

            # 人脸识别
            if enable_face_recognition:
                recognized_faces = detectors["face"].detect_and_recognize(frame)
                for face in recognized_faces:
                    if not face["identity"]["known"]:
                        print(f"🚨 [{camera_id}] 检测到未知人脸!")
                        alert = AIAnalysisResult(
                            camera_id=camera_id,
                            event_type="unknown_face_detected",
                            location=face["location"],
                            confidence=face.get("identity", {}).get("confidence", 0.5),  # 使用 get 方法安全获取值
                            timestamp=datetime.datetime.now().isoformat(),
                        )
                        send_result_to_backend(alert)

        except Exception as e:
            print(f"处理器执行错误: {e}")
            traceback.print_exc()  # 现在可以正常使用 traceback

    try:
        # 创建视频流实例
        stream = VideoStream(stream_url=stream_url, camera_id=camera_id)
        
        # 如果启用了声音检测，启动音频提取
        if enable_sound_detection:
            await stream.start_audio_extraction()
        
        if not await stream.start():
            return {"status": "error", "message": "无法启动视频流"}

        # 添加主处理器
        stream.add_processor(master_processor)
        
        # 保存流实例
        video_streams[camera_id] = stream
        
        # 启动异步处理循环
        asyncio.create_task(process_video_stream_async(stream, camera_id))
        
        return {
            "status": "success",
            "message": f"成功启动摄像头 {camera_id}",
            "stream_info": stream.get_stream_info()
        }
        
    except Exception as e:
        print(f"启动视频流时出错: {e}")
        return {"status": "error", "message": str(e)}

async def process_video_stream_async(stream: VideoStream, camera_id: str):
    """异步处理视频流"""
    print(f"开始处理视频流: {camera_id}")
    while stream.is_running:
        try:
            success, frame = await stream.read_frame()
            if not success:
                print(f"读取视频帧失败: {camera_id}")
                continue
                
            # 处理帧
            with stream.lock:
                for processor in stream.processors:
                    try:
                        processor(frame)
                    except Exception as e:
                        print(f"处理器执行错误: {e}")
            
            # 控制帧率 (优化为更高频率)
            await asyncio.sleep(0.02)  # 约50fps
            
        except Exception as e:
            print(f"视频流处理错误 [{camera_id}]: {e}")
            await asyncio.sleep(1)

@app.post("/stream/stop/{camera_id}")
async def stop_stream(camera_id: str):
    """停止视频流处理。"""
    try:
        if camera_id in video_streams:
            # 停止视频流处理
            stream_processor = video_streams[camera_id]
            stream_processor.stop()
            del video_streams[camera_id]
            
            # 如果没有活跃的视频流了，停止声音检测
            if not video_streams and detectors.get("acoustic") and detectors["acoustic"].is_running:
                detectors["acoustic"].stop_listening()
                print("声音检测已停止")

            print(f"已停止视频流: {stream_processor.stream_url}")
            return {"status": "success", "message": "视频流处理已停止"}
        else:
            return {"status": "error", "message": f"未找到摄像头 {camera_id} 的视频流"}

    except Exception as e:
        print(f"停止视频流时发生错误: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.post("/face/register/")
async def register_face(face_data: FaceData):
    """注册新的人脸到人脸识别器中。"""
    try:
        image_bytes = base64.b64decode(face_data.image_data)
        image_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(status_code=400, detail="无效的Base64图像数据。")

        # 调用人脸识别器的添加方法 (需在FaceRecognizer类中实现此方法)
        # if detectors["face"].add_face(image, face_data.person_name):
        #     return {"status": "success", "message": f"人脸 '{face_data.person_name}' 注册成功。"}
        # else:
        #     raise HTTPException(status_code=400, detail="注册失败，可能未在图像中检测到人脸。")

        # 暂时返回成功，待FaceRecognizer实现add_face
        print(f"收到人脸注册请求: {face_data.person_name}")
        return {"status": "success", "message": "人脸注册请求已收到 (功能待实现)。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/system/status/")
async def get_system_status():
    """获取整个AI服务的当前状态。"""
    return {
        "active_streams_count": len(video_streams),
        "detectors_initialized": {name: det is not None for name, det in detectors.items()},
        "active_streams_details": {
            cam_id: stream.get_stream_info() for cam_id, stream in video_streams.items()
        }
    }


@app.post("/audio/settings/")
async def update_audio_settings(
    confidence_threshold: float = Body(default=None),
    detection_interval: float = Body(default=None), 
    event_cooldown: float = Body(default=None),
    sensitivity: str = Body(default=None)  # "low", "medium", "high"
):
    """更新音频检测设置"""
    try:
        acoustic_detector = detectors.get("acoustic")
        if not acoustic_detector:
            return {"status": "error", "message": "音频检测器未初始化"}
            
        # 验证敏感度参数
        if sensitivity is not None and sensitivity not in ["low", "medium", "high"]:
            return {"status": "error", "message": "敏感度必须是 'low', 'medium' 或 'high'"}
            
        # 更新设置
        acoustic_detector.update_settings(
            confidence_threshold=confidence_threshold,
            detection_interval=detection_interval,
            event_cooldown=event_cooldown,
            sensitivity=sensitivity
        )
        
        return {
            "status": "success", 
            "message": "音频检测设置已更新",
            "current_settings": {
                "confidence_threshold": acoustic_detector.confidence_threshold,
                "detection_interval": acoustic_detector.detection_interval,
                "event_cooldown": acoustic_detector.event_cooldown,
                "volume_multiplier": acoustic_detector.volume_multiplier,
                "frequency_multiplier": acoustic_detector.frequency_multiplier,
                "noise_multiplier": acoustic_detector.noise_multiplier
            }
        }
        
    except Exception as e:
        return {"status": "error", "message": f"更新设置失败: {str(e)}"}


@app.get("/audio/settings/")
async def get_audio_settings():
    """获取当前音频检测设置"""
    try:
        acoustic_detector = detectors.get("acoustic")
        if not acoustic_detector:
            return {"status": "error", "message": "音频检测器未初始化"}
            
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
        
    except Exception as e:
        return {"status": "error", "message": f"获取设置失败: {str(e)}"}


@app.post("/audio/reset/")
async def reset_audio_history():
    """重置音频事件历史"""
    try:
        acoustic_detector = detectors.get("acoustic")
        if not acoustic_detector:
            return {"status": "error", "message": "音频检测器未初始化"}
            
        acoustic_detector.reset_event_history()
        return {"status": "success", "message": "音频事件历史已重置"}
        
    except Exception as e:
        return {"status": "error", "message": f"重置失败: {str(e)}"}


@app.post("/audio/frontend/alert/")
async def process_frontend_audio_alert(
    camera_id: str = Body(...),
    audio_level: float = Body(...),
    event_type: str = Body(default="high_volume"),
    timestamp: str = Body(default=None)
):
    """处理前端发送的音频告警事件"""
    try:
        if not timestamp:
            timestamp = datetime.datetime.now().isoformat()
            
        # 创建音频告警结果
        alert_result = AIAnalysisResult(
            camera_id=camera_id,
            event_type=f"frontend_{event_type}",
            location={"audio_level": audio_level},
            confidence=min(audio_level / 100.0, 1.0),  # 将音量级别转换为置信度
            timestamp=timestamp,
            details={
                "source": "frontend_audio_detection",
                "audio_level": audio_level,
                "event_type": event_type
            }
        )
        
        # 发送到后端
        send_result_to_backend(alert_result)
        
        return {
            "status": "success", 
            "message": f"音频告警已处理: {event_type}, 音量级别: {audio_level}%"
        }
        
    except Exception as e:
        return {"status": "error", "message": f"处理音频告警失败: {str(e)}"}


@app.post("/frame/analyze/")
async def analyze_frame(
    frame: UploadFile = File(...),
    camera_id: str = Body(...),
    enable_face_recognition: bool = Body(default=True),
    enable_object_detection: bool = Body(default=True),
    enable_behavior_detection: bool = Body(default=False)
):
    """高性能单帧图像分析"""
    try:
        # 读取图像数据
        image_data = await frame.read()
        image_array = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        
        if image is None:
            return {"status": "error", "message": "无效的图像数据"}
        
        # 获取图像尺寸，如果图像太小，跳过某些检测以提高性能
        height, width = image.shape[:2]
        is_low_res = width < 300 or height < 300
        
        results = {
            "camera_id": camera_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "detections": [],
            "alerts": []
        }
        
        # 高性能目标检测
        if enable_object_detection:
            # 根据图像质量调整检测策略
            confidence_threshold = 0.8 if is_low_res else 0.7  # 低分辨率时提高阈值减少误检
            
            try:
                detected_objects = detectors["object"].predict(image, confidence_threshold=confidence_threshold)
                
                # 限制检测结果数量以提高处理速度
                detected_objects = detected_objects[:5] if is_low_res else detected_objects[:10]
                
                for obj in detected_objects:
                    # 确保坐标转换为Python原生int类型
                    bbox = [int(float(coord)) for coord in obj["coordinates"]]
                    detection = {
                        "type": "object",
                        "class_name": obj["class_name"],
                        "confidence": float(obj["confidence"]),
                        "bbox": bbox,
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                    results["detections"].append(detection)
                    
                    # 如果检测到人员，生成告警
                    if obj["class_name"] == "person" and obj["confidence"] > 0.8:
                        alert = {
                            "type": "person_detected",
                            "message": f"检测到人员 (置信度: {obj['confidence']:.2f})",
                            "confidence": float(obj["confidence"]),
                            "location": bbox  # 使用已转换的bbox
                        }
                        results["alerts"].append(alert)
            except Exception as e:
                print(f"目标检测失败: {e}")
                # 目标检测失败时不影响其他功能继续运行
        
        # 优化的人脸识别
        if enable_face_recognition and not is_low_res:  # 低分辨率时跳过人脸识别以提高性能
            try:
                recognized_faces = detectors["face"].detect_and_recognize(image)
                
                # 限制人脸检测结果数量
                recognized_faces = recognized_faces[:3]  # 最多处理3个人脸
                
                for face in recognized_faces:
                    # 确保人脸坐标转换为Python原生类型
                    face_bbox = [
                        int(float(face["location"]["left"])),
                        int(float(face["location"]["top"])),
                        int(float(face["location"]["right"])),
                        int(float(face["location"]["bottom"]))
                    ]
                    # 创建一个干净的location字典
                    clean_location = {
                        "left": int(float(face["location"]["left"])),
                        "top": int(float(face["location"]["top"])),
                        "right": int(float(face["location"]["right"])),
                        "bottom": int(float(face["location"]["bottom"]))
                    }
                    
                    detection = {
                        "type": "face",
                        "known": face["identity"]["known"],
                        "name": face["identity"].get("name", "未知"),
                        "confidence": float(face.get("confidence", 0.5)),
                        "bbox": face_bbox,
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                    results["detections"].append(detection)
                    
                    # 如果是未知人脸，生成告警
                    if not face["identity"]["known"]:
                        alert = {
                            "type": "unknown_face",
                            "message": "检测到未知人脸",
                            "confidence": float(face.get("confidence", 0.5)),
                            "location": clean_location  # 使用已清理的location
                        }
                        results["alerts"].append(alert)
                        
                        # 异步发送到后端（不阻塞当前处理）
                        backend_alert = AIAnalysisResult(
                            camera_id=camera_id,
                            event_type="unknown_face_detected",
                            location=clean_location,  # 使用已清理的location
                            confidence=float(face.get("confidence", 0.5)),
                            timestamp=datetime.datetime.now().isoformat(),
                            details={"realtime_detection": True}
                        )
                        # 使用线程池异步处理，不阻塞响应
                        import threading
                        threading.Thread(target=lambda: send_result_to_backend(backend_alert), daemon=True).start()
            except Exception as e:
                print(f"人脸识别失败: {e}")
                # 人脸识别失败时不影响其他功能继续运行
        
        return {"status": "success", "results": results}
        
    except Exception as e:
        print(f"分析帧时发生错误: {e}")
        return {"status": "error", "message": f"分析失败: {str(e)}"}


@app.get("/stream/webcam/start/{camera_id}")
async def start_webcam_stream(camera_id: str):
    """启动网络摄像头流处理（用于前端摄像头）"""
    try:
        # 为网络摄像头创建一个虚拟的视频流处理器
        if camera_id not in video_streams:
            # 创建虚拟流处理器
            class WebcamProcessor:
                def __init__(self, camera_id):
                    self.camera_id = camera_id
                    self.is_running = True
                    self.frame_count = 0
                    
                def get_status(self):
                    return {
                        "camera_id": self.camera_id,
                        "status": "running" if self.is_running else "stopped",
                        "type": "webcam",
                        "frame_count": self.frame_count
                    }
                    
                def stop(self):
                    self.is_running = False
                    
                def process_frame(self):
                    self.frame_count += 1
            
            video_streams[camera_id] = WebcamProcessor(camera_id)
        
        return {
            "status": "success",
            "message": f"网络摄像头流 {camera_id} 已启动",
            "camera_id": camera_id
        }
        
    except Exception as e:
        return {"status": "error", "message": f"启动失败: {str(e)}"}


@app.post("/stream/webcam/stop/{camera_id}")
async def stop_webcam_stream(camera_id: str):
    """停止网络摄像头流处理"""
    try:
        if camera_id in video_streams:
            video_streams[camera_id].stop()
            del video_streams[camera_id]
            return {"status": "success", "message": f"网络摄像头流 {camera_id} 已停止"}
        else:
            return {"status": "error", "message": f"未找到摄像头流: {camera_id}"}
            
    except Exception as e:
        return {"status": "error", "message": f"停止失败: {str(e)}"}


@app.get("/performance/optimize/")
async def get_performance_tips():
    """获取性能优化建议"""
    try:
        tips = []
        
        # 检查检测器状态
        if "object" in detectors:
            tips.append({
                "type": "info",
                "title": "目标检测优化",
                "description": "已启用智能检测阈值调整和结果数量限制"
            })
        
        if "face" in detectors:
            tips.append({
                "type": "info", 
                "title": "人脸识别优化",
                "description": "低分辨率图像自动跳过人脸识别，最多处理3个人脸"
            })
            
        tips.extend([
            {
                "type": "success",
                "title": "性能模式已激活",
                "description": "AI服务已启用高性能处理模式，包括异步后端通信和错误容错机制"
            },
            {
                "type": "warning",
                "title": "网络优化建议",
                "description": "前端已启用帧差检测、动态画质调整和智能跳帧机制"
            }
        ])
        
        return {
            "status": "success",
            "tips": tips,
            "performance_mode": "high_performance",
            "optimizations": [
                "动态检测阈值",
                "结果数量限制", 
                "低分辨率跳过",
                "异步后端通信",
                "错误容错机制"
            ]
        }
        
    except Exception as e:
        return {"status": "error", "message": f"获取性能信息失败: {str(e)}"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)