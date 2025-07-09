from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile # <--- 修改这里
from pydantic import BaseModel
import uvicorn
import requests
import os
import shutil  # <--- 添加这一行
from dotenv import load_dotenv
# ...其他import语句...
from core.acoustic_detection import AcousticEventDetector # 导入我们刚创建的类
# import datetime  <--- 删除或注释掉这一行
# ...其他import语句...
from core.fire_smoke_detection import FlameSmokeDetector # 导入我们刚创建的类

from core.object_detection import GenericPredictor
from core.face_recognition import FaceRecognizer
# ...其他import语句...
import cv2
from core.behavior_detection import BehaviorDetector # 导入我们刚创建的类
load_dotenv()
app = FastAPI(
    title="AI 智能分析服务",
    description="提供视频流处理、人脸识别、目标检测等AI分析能力",
    version="1.0.0",
)

# ==========================================================
#  ↓↓↓ 在这里添加模型加载代码 ↓↓↓ (修改后)
# ==========================================================
# --- 1. 定义模型配置 ---
MODEL_WEIGHTS_PATH = "ai_service/weights/object_detection_best.pth"
# !! 这里的类别数量和名称需要和您的模型完全匹配
# 我们现在使用在COCO数据集上预训练的模型，它有91个类别
NUM_CLASSES = 91
# COCO数据集的91个类别名称列表
COCO_INSTANCE_CATEGORY_NAMES = [
    '__background__', 'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus',
    'train', 'truck', 'boat', 'traffic light', 'fire hydrant', 'N/A', 'stop sign',
    'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
    'elephant', 'bear', 'zebra', 'giraffe', 'N/A', 'backpack', 'umbrella', 'N/A', 'N/A',
    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'N/A', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl',
    'banana', 'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
    'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed', 'N/A', 'dining table',
    'N/A', 'N/A', 'toilet', 'N/A', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
    'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'N/A', 'book',
    'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]
CLASS_NAMES = COCO_INSTANCE_CATEGORY_NAMES

# --- 2. 在服务启动时加载模型 ---
try:
    object_detector = GenericPredictor(
        model_weights_path=MODEL_WEIGHTS_PATH,
        num_classes=NUM_CLASSES,
        class_names=CLASS_NAMES
    )
    print("Object Detection model loaded successfully.")
except Exception as e:
    object_detector = None
    print(f"Failed to load Object Detection model: {e}")
# ...在 object_detector 加载代码的下面添加...

# --- 3. 加载人脸识别模型 ---
try:
    face_recognizer = FaceRecognizer(face_db_path="ai_service/face_db/")
    print("Face Recognition model loaded successfully.")
except Exception as e:
    face_recognizer = None
    print(f"Failed to load Face Recognition model: {e}")


# ...在 face_recognizer 加载代码的下面添加...

# --- 4. 加载声音识别模型 ---
try:
    acoustic_detector = AcousticEventDetector()
except Exception as e:
    acoustic_detector = None
    print(f"Failed to load Acoustic Event Detector: {e}")


# ...在 acoustic_detector 加载代码的下面添加...

# --- 5. 加载火焰烟雾检测模型 ---
try:
    FIRE_SMOKE_MODEL_PATH = "ai_service/weights/fire_smoke_yolov8.pt"
    flame_smoke_detector = FlameSmokeDetector(model_path=FIRE_SMOKE_MODEL_PATH)
except Exception as e:
    flame_smoke_detector = None
    print(f"Failed to load FlameSmokeDetector: {e}")


# ...在 flame_smoke_detector 加载代码的下面添加...

# --- 6. 加载行为检测模型 ---
try:
    behavior_detector = BehaviorDetector()
except Exception as e:
    behavior_detector = None
    print(f"Failed to load BehaviorDetector: {e}")
# ==========================================================
#  ↑↑↑ 模型加载代码结束 ↑↑↑ (修改后)
# ==========================================================

# AI分析结果的数据模型，与后端保持一致
# AI分析结果的数据模型，与后端保持一致
class AIAnalysisResult(BaseModel):
    camera_id: str
    event_type: str # 例如: "stranger_intrusion", "person_fall"
    location: dict # 例如: {"x": 150, "y": 230, "w": 80, "h": 160}
    confidence: float
    image_snapshot_url: str | None = None # 使用 | None 表示可选
    video_clip_url: str | None = None   # 使用 | None 表示可选


# --- 这是关键函数，负责将结果发送给Django后端 ---
def send_result_to_backend(result: AIAnalysisResult):
    """
    这是一个后台任务函数，专门用于发送HTTP请求到Django后端。
    我们把它独立出来，这样发送网络请求就不会阻塞主程序的AI分析流程。
    """
    django_backend_url = os.getenv("DJANGO_BACKEND_URL", "http://127.0.0.1:8000/api/alerts/ai-results/")
    print(f"准备将告警上报给后端: {django_backend_url}")
    try:
        # 使用 .model_dump() 方法将Pydantic模型转换为字典
        response = requests.post(django_backend_url, json=result.model_dump(), timeout=10) # 设置10秒超时
        response.raise_for_status() # 如果请求失败(状态码4xx或5xx), 则会抛出异常
        print(f"成功上报告警，后端返回: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"上报告警至后端时出错: {e}")


# --- 这是修改后的视频流处理入口 ---
@app.post("/analyze/video_stream/")
async def analyze_video_stream(camera_id: str, background_tasks: BackgroundTasks):
    """
    这个API接收到请求后，会开始进行AI分析。
    当分析出结果后，它会将发送结果的任务添加到后台去执行。
    """
    print(f"接收到来自摄像头 {camera_id} 的视频流，开始进行AI分析...")

    if not object_detector:
        print(f"摄像头 {camera_id} 的分析任务中止，因为目标检测模型未加载。")
        raise HTTPException(status_code=503, detail="Object Detection model is not available.")

    # =================================================================
    #  ↓↓↓ 在这里集成你真正的AI核心逻辑 ↓↓↓
    # =================================================================

    # 1. 从视频流中获取一帧图像
    #    这里需要您自己实现视频流读取逻辑（例如使用OpenCV读取RTSP流）
    #    我们假设您已经读取到了一帧，并保存为临时图片文件 `temp_frame.jpg`
    #    (这是一个示例，您需要替换成真实的帧捕获和保存代码)
    #    frame = get_frame_from_rtsp(f"rtsp://.../{camera_id}")
    #    cv2.imwrite("temp_frame.jpg", frame)
    image_to_predict = "temp_frame.jpg"  # 假设的图片路径

    # 为了能运行示例，我们先创建一个虚拟的图片文件
    # 在您的真实代码中请删除下面这两行
    from PIL import Image
    Image.new('RGB', (800, 600)).save(image_to_predict)

    # 2. 调用模型进行预测
    print(f"摄像头 {camera_id}: 开始对帧进行目标检测...")
    detection_results = object_detector.predict(image_to_predict)
    print(f"摄像头 {camera_id}: 检测到 {len(detection_results)} 个目标。")

    # 在真实代码中请删除这个临时文件
    os.remove(image_to_predict)

    # 3. 遍历检测结果，并上报给后端
    for result in detection_results:
        # 您可以根据检测到的类别名(result['class_name'])来判断事件类型
        # 例如，如果检测到 "dangerous_good"，就上报

        event_type_to_report = f"detected_{result['class_name']}"

        # 将检测结果构造成后端需要的数据模型
        analysis_result = AIAnalysisResult(
            camera_id=camera_id,
            event_type=event_type_to_report,
            location={
                "x": result['coordinates'][0],
                "y": result['coordinates'][1],
                "w": result['coordinates'][2] - result['coordinates'][0],  # 计算宽度
                "h": result['coordinates'][3] - result['coordinates'][1]  # 计算高度
            },
            confidence=result['confidence'],
            # 如果您有保存截图的逻辑，可以在这里填写真实的URL
            image_snapshot_url=f"http://your-storage-server.com/snapshots/{event_type_to_report}_{camera_id}.jpg"
        )

        # 使用您已有的后台任务系统，将格式化后的结果发送出去
        background_tasks.add_task(send_result_to_backend, analysis_result)
        print(f"摄像头 {camera_id}: 已将事件 '{event_type_to_report}' 添加到后台发送队列。")

    return {"status": "AI分析任务完成，结果已交由后台处理", "camera_id": camera_id,
            "detected_objects": len(detection_results)}

    # 例如，想改成 8080 端口，就写成:
    # uvicorn.run(app, host="0.0.0.0", port=8080)


# ...在 analyze_video_stream 函数的下面添加...

@app.post("/recognize/faces")
async def api_recognize_faces(file: UploadFile = File(...)):
    """
    接收上传的图片文件，进行人脸识别，并返回结果。
    """
    if not face_recognizer:
        raise HTTPException(status_code=503, detail="Face Recognition model is not available.")

    temp_file_path = f"temp_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        recognition_results = face_recognizer.recognize_faces(temp_file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during face recognition: {e}")
    finally:
        os.remove(temp_file_path)  # 清理临时文件

    return {
        "filename": file.filename,
        "faces": recognition_results
    }


# ...在 api_recognize_faces 函数的下面添加...

@app.post("/detect/acoustic_events")
async def api_detect_acoustic_events(camera_id: str, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    接收上传的音频文件，进行声音事件识别，并将高置信度的异常事件上报给后端。
    """
    if not acoustic_detector:
        raise HTTPException(status_code=503, detail="Acoustic Event Detector is not available.")

    temp_file_path = f"temp_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        detection_results = acoustic_detector.detect_events(temp_file_path)

        # 筛选出我们关心的、并且置信度较高的异常事件进行上报
        # 您可以根据需要调整这个列表和阈值
        events_of_interest = ["Screaming", "Glass", "Crying_and_sobbing", "Shout"]
        confidence_threshold = 0.5

        for result in detection_results:
            if result["event"] in events_of_interest and result["confidence"] > confidence_threshold:
                print(f"检测到高置信度异常声音: {result['event']}")

                # 复用您已有的AI结果上报流程
                analysis_result = AIAnalysisResult(
                    camera_id=camera_id,  # 关联到某个摄像头ID
                    event_type=f"acoustic_{result['event'].lower()}",
                    location={"x": 0, "y": 0, "w": 0, "h": 0},  # 声音事件通常没有空间坐标
                    confidence=result['confidence'],
                    image_snapshot_url=None  # 声音事件没有快照
                )
                background_tasks.add_task(send_result_to_backend, analysis_result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during acoustic event detection: {e}")
    finally:
        os.remove(temp_file_path)
    return {
        "filename": file.filename,
        "detected_events": detection_results
    }


# ...在 api_detect_acoustic_events 函数的下面添加...

@app.post("/detect/fire_smoke")
async def api_detect_fire_smoke(camera_id: str, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    接收上传的图片文件，进行火焰和烟雾检测，并将结果上报给后端。
    """
    if not flame_smoke_detector:
        raise HTTPException(status_code=503, detail="Flame/Smoke Detector is not available.")

    temp_file_path = f"temp_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        detection_results = flame_smoke_detector.detect(temp_file_path)

        # 遍历所有检测结果并上报
        for result in detection_results:
            print(f"检测到紧急情况: {result['class_name']}")

            # 复用您已有的AI结果上报流程
            analysis_result = AIAnalysisResult(
                camera_id=camera_id,
                event_type=f"emergency_{result['class_name'].lower()}",
                location={
                    "x": result['coordinates'][0],
                    "y": result['coordinates'][1],
                    "w": result['coordinates'][2] - result['coordinates'][0],
                    "h": result['coordinates'][3] - result['coordinates'][1]
                },
                confidence=result['confidence'],
                image_snapshot_url=f"http://your-storage-server.com/snapshots/fire_{camera_id}.jpg"  # 示例URL
            )
            background_tasks.add_task(send_result_to_backend, analysis_result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during fire/smoke detection: {e}")
    finally:
        os.remove(temp_file_path)

    return {
        "filename": file.filename,
        "detected_objects": detection_results
    }


# ...在 api_detect_fire_smoke 函数的下面添加...

@app.post("/detect/behavior")
async def api_detect_behavior(camera_id: str, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    接收上传的图片文件，进行行为检测（如跌倒），并将异常行为上报给后端。
    """
    if not behavior_detector:
        raise HTTPException(status_code=503, detail="Behavior Detector is not available.")

    temp_file_path = f"temp_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 使用OpenCV读取图片为NumPy数组
        image = cv2.imread(temp_file_path)
        if image is None:
            raise HTTPException(status_code=400, detail="Could not read image file.")

        detection_results, _ = behavior_detector.detect_fall(image)

        # 遍历所有检测结果并上报
        for result in detection_results:
            if result["status"] == "fallen":
                print(f"检测到跌倒行为!")

                # 复用您已有的AI结果上报流程
                analysis_result = AIAnalysisResult(
                    camera_id=camera_id,
                    event_type="behavior_person_fall",
                    location=result["location"],
                    confidence=0.9,  # 行为检测通常没有直接的置信度，可设为固定值
                    image_snapshot_url=f"http://your-storage-server.com/snapshots/fall_{camera_id}.jpg"
                )
                background_tasks.add_task(send_result_to_backend, analysis_result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during behavior detection: {e}")
    finally:
        os.remove(temp_file_path)

    return {
        "filename": file.filename,
        "detected_behaviors": detection_results
    }
# --- 如何修改端口 ---
if __name__ == "__main__":
    #  ↓↓↓ 要修改端口，直接修改这里的 port 数字即可 ↓↓↓
    uvicorn.run(app, host="0.0.0.0", port=8001)