from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import requests
import os
from dotenv import load_dotenv

load_dotenv() # 加载 .env 文件中的环境变量

app = FastAPI(
    title="AI 智能分析服务",
    description="提供视频流处理、人脸识别、目标检测等AI分析能力",
    version="1.0.0",
)

# 模拟AI分析结果的数据模型
class AIAnalysisResult(BaseModel):
    camera_id: str
    event_type: str # e.g., "stranger_detected", "intrusion", "fall_detection", "smoke_fire"
    timestamp: str
    location: dict # e.g., {"x": 0.5, "y": 0.5, "width": 0.1, "height": 0.1} or polygon coords
    confidence: float
    image_snapshot_url: str = None # 可选：事件截图URL
    video_clip_url: str = None # 可选：事件视频片段URL

# 接收分析结果并发送给Django后端
@app.post("/analyze/result/")
async def post_analysis_result(result: AIAnalysisResult):
    # 从环境变量获取Django后端URL
    django_backend_url = os.getenv("DJANGO_BACKEND_URL", "http://127.0.0.1:8000/api/alerts/ai-results/")
    try:
        # 假设后端有一个API端点来接收AI结果
        # 注意：实际中，你可能需要在后端alerts应用中定义这个具体的API endpoint
        response = requests.post(django_backend_url, json=result.dict())
        response.raise_for_status() # 如果是4xx或5xx响应，则抛出HTTPError
        return {"message": "Analysis result sent to Django backend successfully", "backend_response": response.json()}
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to send analysis result to Django backend: {e}")

# 模拟视频流处理端点
@app.post("/analyze/video_stream/")
async def analyze_video_stream(camera_id: str):
    # 在这里集成AI核心逻辑，例如：
    # 1. 使用OpenCV接入视频流 (根据camera_id获取RTSP/HTTP地址)
    # 2. 调用 core 模块中的AI模型进行人脸识别、目标检测、行为分析等
    # 3. 如果检测到异常，构建AIAnalysisResult对象并通过post_analysis_result发送给Django后端
    print(f"Receiving video stream from camera: {camera_id}. Starting AI analysis...")

    # 示例：模拟AI分析结果（实际中通过AI模型生成）
    # from core.face_recognition import detect_faces
    # from core.behavior_detection import detect_fall

    # 模拟每隔一段时间发送结果 (在实际AI服务中，这会在视频处理循环中发生)
    # await post_analysis_result(
    #     AIAnalysisResult(
    #         camera_id=camera_id,
    #         event_type="mock_fall_detected",
    #         timestamp="2025-07-07T15:00:00Z",
    #         location={"x": 0.3, "y": 0.4, "width": 0.2, "height": 0.3},
    #         confidence=0.98,
    #         image_snapshot_url="http://example.com/snapshot_mock.jpg"
    #     )
    # )

    return {"status": "AI analysis task initiated for camera", "camera_id": camera_id}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) # AI服务默认运行在8001端口