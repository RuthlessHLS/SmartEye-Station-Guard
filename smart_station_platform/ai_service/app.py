# 文件: ai_service/app.py

import os
import base64
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 导入我们自定义的所有核心AI模块
from core.video_stream import VideoStream
from core.object_detection import GenericPredictor
from core.behavior_detection import BehaviorDetector
from core.face_recognition import FaceRecognizer
from core.acoustic_detection import AcousticDetector
from models.alert_models import AIAnalysisResult  # 确保这个文件存在

# 在应用启动时，从 .env 文件加载环境变量
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

        # 1. 初始化通用目标检测器
        class_names_path = os.getenv("CLASS_NAMES_PATH", "models/coco.names")
        class_names = []
        try:
            with open(class_names_path, 'r') as f:
                class_names = [line.strip() for line in f.readlines()]
            print(f"成功加载 {len(class_names)} 个类别名称。")
        except FileNotFoundError:
            print(f"警告: 找不到类别名称文件 at '{class_names_path}'。")
            class_names = ["background", "person"]

        detectors["object"] = GenericPredictor(
            model_weights_path=os.getenv("OBJECT_DETECTION_MODEL_PATH", "models/fasterrcnn_resnet50_fpn.pt"),
            num_classes=len(class_names),
            class_names=class_names
        )

        # 2. 初始化行为检测器
        detectors["behavior"] = BehaviorDetector()

        # 3. 初始化人脸识别器
        detectors["face"] = FaceRecognizer(
            known_faces_dir=os.getenv("KNOWN_FACES_DIR", "known_faces")
        )

        # 4. 初始化声学事件检测器 (如果启用了)
        if os.getenv("ENABLE_SOUND_DETECTION", "false").lower() == "true":
            try:
                detectors["acoustic"] = AcousticDetector()
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
    if "acoustic" in detectors:
        detectors["acoustic"].start_listening()
        asyncio.create_task(run_acoustic_analysis())

    yield  # 服务在此运行时，处理API请求

    # 关闭任务
    print("服务正在关闭，开始清理资源...")
    for stream in video_streams.values():
        stream.stop()
    if "acoustic" in detectors and detectors["acoustic"].is_running:
        detectors["acoustic"].stop_listening()
    thread_pool.shutdown(wait=True)
    print("资源清理完毕。")


# 创建FastAPI应用实例
app = FastAPI(
    title="AI 智能分析服务 (最终版)",
    description="提供视频流处理、目标检测、行为识别、人脸识别和声学事件检测能力",
    version="2.0.0",
    lifespan=lifespan
)


# --- 数据模型 ---

class StreamConfig(BaseModel):
    camera_id: str
    stream_url: str
    enable_face_recognition: bool = True  # 默认启用
    enable_behavior_detection: bool = True  # 默认启用


class FaceData(BaseModel):
    person_name: str
    image_data: str  # Base64编码的图像数据


# --- 核心函数 ---

def send_result_to_backend(result: AIAnalysisResult):
    """将分析结果异步发送到后端Django服务。"""

    def task():
        backend_url = os.getenv("DJANGO_BACKEND_URL", "http://127.0.0.1:8000/api/alerts/ai-results/")
        try:
            response = requests.post(backend_url, json=result.dict(), timeout=10)
            if 200 <= response.status_code < 300:
                print(f"✅ [结果上报] 成功发送事件 '{result.event_type}' 到后端。")
            else:
                # 打印后端返回的更详细的错误信息
                print(f"❌ [结果上报] 发送失败，状态码: {response.status_code}, 后端响应: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"❌ [请求异常] 无法连接到后端服务: {e}")

    thread_pool.submit(task)


async def run_acoustic_analysis():
    """在后台持续运行的协程，用于分析音频数据。"""
    print("声学分析后台任务已启动。")
    acoustic_detector = detectors.get("acoustic")
    if not acoustic_detector: return

    while acoustic_detector.is_running:
        result = acoustic_detector.analyze_audio_chunk(volume_threshold=0.1)
        if result and result["need_alert"]:
            print(f"🚨 [音频] 检测到异常声音! 音量: {result['details']['volume']}")
            alert = AIAnalysisResult(
                camera_id="audio_sensor_01",
                event_type=result["event_type"],
                location={"source": "microphone", "details": result['details']},
                confidence=result["confidence"],
                timestamp=time.time(),
            )
            send_result_to_backend(alert)
        await asyncio.sleep(0.1)


def create_master_processor(camera_id: str, config: StreamConfig):
    """
    创建一个主AI处理器，它负责协调调用所有视觉相关的AI检测器。
    """

    def master_processor(frame: np.ndarray):
        try:
            # 1. 目标检测 (总是执行，因为是其他分析的基础)
            detected_objects = detectors["object"].predict(frame, confidence_threshold=0.6)

            # 2. 行为检测
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
                                timestamp=time.time(),
                            )
                            send_result_to_backend(alert)

            # 3. 人脸识别
            if config.enable_face_recognition:
                recognized_faces = detectors["face"].detect_and_recognize(frame)
                for face in recognized_faces:
                    if face["identity"] == "Unknown":
                        print(f"🚨 [{camera_id}] 检测到未知人员!")
                        alert = AIAnalysisResult(
                            camera_id=camera_id,
                            event_type="unknown_face_detected",
                            location={"box": face["box"]},
                            confidence=face.get("confidence", 0.9),  # 使用识别出的置信度，若无则默认
                            timestamp=time.time(),
                        )
                        send_result_to_backend(alert)

        except Exception as e:
            print(f"处理帧时发生致命错误 [{camera_id}]: {e}")

    return master_processor


# --- API 端点 (Endpoints) ---

@app.post("/stream/start/", status_code=202)
async def start_stream(config: StreamConfig):
    """启动一个新的视频流处理任务。"""
    if config.camera_id in video_streams:
        raise HTTPException(status_code=400, detail=f"摄像头 {config.camera_id} 已在处理中。")
    try:
        stream = VideoStream(config.stream_url)
        stream.add_processor(create_master_processor(config.camera_id, config))
        if not stream.start():
            raise HTTPException(status_code=500, detail="无法启动视频流处理线程。")
        video_streams[config.camera_id] = stream
        return {"status": "accepted", "message": f"已启动摄像头 {config.camera_id} 的AI分析任务。"}
    except Exception as e:
        if config.camera_id in video_streams:
            video_streams[config.camera_id].stop()
            del video_streams[config.camera_id]
        raise HTTPException(status_code=500, detail=f"启动处理失败: {str(e)}")


@app.post("/stream/stop/{camera_id}")
async def stop_stream(camera_id: str):
    """停止指定摄像头的视频流处理。"""
    if camera_id in video_streams:
        video_streams[camera_id].stop()
        del video_streams[camera_id]
        return {"status": "success", "message": f"已停止摄像头 {camera_id} 的处理。"}
    raise HTTPException(status_code=404, detail=f"未找到正在处理的摄像头 {camera_id}。")


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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)