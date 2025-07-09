# 文件: ai_service/app.py
# 描述: AI智能分析服务的主应用文件，整合了视频流处理和AI模型。

import os
import base64
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

# 导入我们自定义的核心模块
from core.video_stream import VideoStream
from core.object_detection import GenericPredictor

# from core.behavior_detection import BehaviorDetector  # (下一步可以取消注释)
# from core.face_recognition import FaceRecognizer    # (下一步可以取消注释)

# 在应用启动时，从 .env 文件加载环境变量 (例如模型路径)
load_dotenv()

# --- 全局变量 ---
# 使用一个字典来存储和管理所有正在运行的视频流实例
# 键是 camera_id, 值是 VideoStream 类的实例
video_streams: Dict[str, VideoStream] = {}
# 使用一个字典来存储所有已初始化的AI模型实例
detectors: Dict[str, object] = {}
# 创建一个线程池，专门用于异步发送网络请求，避免阻塞主AI处理流程
thread_pool = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)


# --- FastAPI 应用生命周期管理 ---

def init_detectors():
    """
    初始化所有AI检测器模型。这个函数在服务启动时只执行一次。
    """
    try:
        print("正在初始化所有检测器...")

        # 1. 初始化通用目标检测器 (GenericPredictor)
        class_names_path = os.getenv("CLASS_NAMES_PATH", "path/to/your/class_names.txt")
        class_names = []
        try:
            with open(class_names_path, 'r') as f:
                class_names = [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            # 如果找不到类别文件，至少要保证有一个背景类，避免程序崩溃
            print(f"警告: 找不到类别名称文件 at '{class_names_path}'。将使用默认类别。")
            class_names = ["background", "person"]

        detectors["object"] = GenericPredictor(
            model_weights_path=os.getenv("OBJECT_DETECTION_MODEL_PATH", "path/to/your/model.pt"),
            num_classes=len(class_names),
            class_names=class_names
        )

        # 2. (未来步骤) 初始化行为检测器
        # detectors["behavior"] = BehaviorDetector(...)

        # 3. (未来步骤) 初始化人脸识别器
        # detectors["face"] = FaceRecognizer(...)

        print("所有检测器初始化完成。")

    except Exception as e:
        print(f"致命错误: 检测器初始化失败: {e}")
        # 如果模型加载失败，服务启动将失败
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 的生命周期管理器。
    在 'yield' 之前的代码在服务启动时运行。
    在 'yield' 之后的代码在服务关闭时运行。
    """
    # --- 启动任务 ---
    init_detectors()
    # --- 启动任务结束 ---

    yield  # 服务在此运行时，处理API请求

    # --- 关闭任务 ---
    print("服务正在关闭，开始清理资源...")
    # 停止所有正在运行的视频流线程
    for stream in video_streams.values():
        stream.stop()
    # 等待所有挂起的网络请求完成
    thread_pool.shutdown(wait=True)
    print("资源清理完毕。")


# 创建FastAPI应用实例，并应用生命周期管理器
app = FastAPI(
    title="AI 智能分析服务",
    description="提供视频流处理、人脸识别、目标检测等AI分析能力",
    version="1.2.0",  # 版本升级
    lifespan=lifespan
)


# --- 数据模型 (用于API请求和响应) ---

class StreamConfig(BaseModel):
    camera_id: str
    stream_url: str
    enable_face_recognition: bool = False
    enable_behavior_detection: bool = True


class FaceData(BaseModel):
    person_name: str
    image_data: str  # Base64编码的图像数据


# --- 核心AI处理器 ---

def create_master_processor(camera_id: str):
    """
    创建一个主AI处理器。
    这个函数会被每个视频帧调用，它负责协调调用所有需要的AI检测器。

    Args:
        camera_id (str): 当前视频流对应的摄像头ID。

    Returns:
        Callable: 一个接收单帧图像(np.ndarray)作为输入的处理器函数。
    """

    def master_processor(frame: np.ndarray):
        # 1. 使用目标检测器进行预测
        try:
            # 我们只关心置信度高于0.6的结果，以减少误报
            detected_objects = detectors["object"].predict(frame, confidence_threshold=0.6)

            # (调试用) 打印出检测到的物体
            if detected_objects:
                object_names = [obj['class_name'] for obj in detected_objects]
                print(f"[{camera_id}] 实时检测到: {object_names}")

            # 2. (未来步骤) 基于目标检测结果，进行行为分析
            # person_boxes = [obj["coordinates"] for obj in detected_objects if obj["class_name"] == "person"]
            # if person_boxes and "behavior" in detectors:
            #     behaviors = detectors["behavior"].detect_behavior(frame, person_boxes)
            #     # ... 根据行为结果进行处理和上报

        except Exception as e:
            print(f"处理帧时发生错误 [{camera_id}]: {e}")

    return master_processor


# --- API 端点 (Endpoints) ---

@app.post("/stream/start/", status_code=202)
async def start_stream(config: StreamConfig):
    """
    启动一个新的视频流处理任务。
    它会创建一个VideoStream实例，并根据配置注册相应的AI处理器。
    """
    if config.camera_id in video_streams:
        raise HTTPException(status_code=400, detail=f"摄像头 {config.camera_id} 已在处理中。")

    try:
        print(f"正在为摄像头 {config.camera_id} 初始化视频流...")
        stream = VideoStream(config.stream_url)

        # 注册主AI处理器
        stream.add_processor(create_master_processor(config.camera_id))

        # 启动视频流的后台捕获线程
        if not stream.start():
            raise HTTPException(status_code=500, detail="无法启动视频流处理线程。")

        # 将创建好的实例存入全局字典以便管理
        video_streams[config.camera_id] = stream

        return {"status": "accepted", "message": f"已启动摄像头 {config.camera_id} 的AI分析任务。"}

    except Exception as e:
        # 如果在启动过程中发生任何错误，确保清理
        if config.camera_id in video_streams:
            video_streams[config.camera_id].stop()
            del video_streams[config.camera_id]
        raise HTTPException(status_code=500, detail=f"启动处理失败: {str(e)}")


@app.post("/stream/stop/{camera_id}")
async def stop_stream(camera_id: str):
    """停止指定摄像头的视频流处理。"""
    if camera_id in video_streams:
        video_streams[camera_id].stop()
        del video_streams[camera_id]  # 从字典中移除，释放资源
        return {"status": "success", "message": f"已停止摄像头 {camera_id} 的处理。"}
    raise HTTPException(status_code=404, detail=f"未找到正在处理的摄像头 {camera_id}。")


@app.get("/system/status/")
async def get_system_status():
    """获取整个AI服务的当前状态，包括活动的视频流信息。"""
    return {
        "active_streams_count": len(video_streams),
        "detectors_initialized": {name: det is not None for name, det in detectors.items()},
        "active_streams_details": {
            cam_id: stream.get_stream_info() for cam_id, stream in video_streams.items()
        }
    }


# (人脸注册等其他API端点可以保持不变)

if __name__ == "__main__":
    # 这段代码使得你可以直接运行 "python app.py" 来启动服务
    # 这对于在非Docker环境或不使用gunicorn/uvicorn命令行时进行调试非常方便
    uvicorn.run(app, host="0.0.0.0", port=8001)