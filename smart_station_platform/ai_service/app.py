from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uvicorn
import requests
import os
from dotenv import load_dotenv
import datetime # 导入datetime模块来获取当前时间

load_dotenv() # 加载 .env 文件中的环境变量

app = FastAPI(
    title="AI 智能分析服务",
    description="提供视频流处理、人脸识别、目标检测等AI分析能力",
    version="1.0.0",
)

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


# --- 这是模拟视频流处理的主入口 ---
@app.post("/analyze/video_stream/")
async def analyze_video_stream(camera_id: str, background_tasks: BackgroundTasks):
    """
    这个API接收到请求后，会开始模拟AI分析流程。
    当分析出结果后，它会把发送结果的任务添加到后台去执行。
    """
    print(f"接收到来自摄像头 {camera_id} 的视频流，开始进行AI分析...")

    # =================================================================
    #  ↓↓↓ 在这里集成你真正的AI核心逻辑 ↓↓↓
    #
    #  例如:
    #  1. 使用OpenCV从RTSP地址读取视频帧
    #  2. 将视频帧喂给YOLOv8模型进行目标检测
    #  3. 如果检测到比如 "人员跌倒" 事件...
    #
    # =================================================================

    # --- 示例：模拟AI分析后得出了一个结果 ---
    # (在你的实际代码中，这些值都应该由AI模型动态生成)
    mock_result = AIAnalysisResult(
        camera_id=camera_id,
        event_type="person_fall_mock", # 模拟的事件类型：人员跌倒
        # timestamp=datetime.datetime.now().isoformat(), # 使用当前时间的ISO格式
        location={"x": 350, "y": 510, "width": 60, "height": 120}, # 模拟的坐标
        confidence=0.92, # 模拟的置信度
        image_snapshot_url="http://your-storage-server.com/snapshots/fall_event_123.jpg" # 模拟的截图URL
    )

    # --- 关键改动在这里 ---
    # 我们不直接在这里发送请求，而是把发送任务交给FastAPI的后台任务系统
    # 这样做的好处是，即使发送请求很慢，也不会影响AI服务响应下一个分析任务
    background_tasks.add_task(send_result_to_backend, mock_result)

    return {"status": "AI分析任务已启动，结果将由后台发送", "camera_id": camera_id}


# --- 如何修改端口 ---
if __name__ == "__main__":
    #  ↓↓↓ 要修改端口，直接修改这里的 port 数字即可 ↓↓↓
    uvicorn.run(app, host="0.0.0.0", port=8001)
    # 例如，想改成 8080 端口，就写成:
    # uvicorn.run(app, host="0.0.0.0", port=8080)