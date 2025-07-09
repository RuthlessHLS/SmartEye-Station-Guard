# 文件: ai_service/app.py

# 导入必要的库
from fastapi import FastAPI, HTTPException, BackgroundTasks
import uvicorn
import requests
import os
from dotenv import load_dotenv

# --- 从我们自己创建的模块中导入 ---
from core.models import AlertPayload

# 下面这两行暂时注释掉，因为AI开发者A还没完成他的部分。
# 集成时，我们会把这两行的注释去掉。
# from core.video_stream import process_video_stream
# from core.analysis.object_detector import ObjectDetector


# 加载 .env 文件中的环境变量，这样 os.getenv 就能读取到配置
load_dotenv()

# 初始化FastAPI应用
app = FastAPI(
    title="AI 智能分析服务",
    description="提供视频流处理、人脸识别、目标检测等AI分析能力",
    version="1.0.0",
)


# 在服务启动时，先不加载AI模型，因为这是开发者A的任务。
# 集成时，我们会在这里添加: detector = ObjectDetector()

# --- 关键函数：负责将结果发送给Django后端 ---
def send_result_to_backend(result: AlertPayload):
    """
    这是一个后台任务函数，专门用于发送HTTP请求到Django后端。
    """
    # 从环境变量读取后端URL，如果没配置，则使用默认地址
    django_backend_url = os.getenv("DJANGO_BACKEND_URL", "http://127.0.0.1:8000/api/alerts/ai-results/")
    print(f"准备将告警上报给后端: {django_backend_url}")
    try:
        # 使用 .model_dump() 方法将Pydantic模型转换为字典
        response = requests.post(django_backend_url, json=result.model_dump(), timeout=10)
        response.raise_for_status()  # 如果请求失败(状态码4xx或5xx), 则会抛出异常
        print(f"成功上报告警，后端返回: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"上报告警至后端时出错: {e}")


# --- 后台处理逻辑（目前使用模拟数据） ---
def mock_ai_processing_logic(camera_id: str, video_url: str, background_tasks: BackgroundTasks):
    """
    这是一个模拟的后台处理函数。
    它展示了当AI分析出结果后，应该如何调用上报函数。
    """
    print(f"模拟后台任务启动: 摄像头 {camera_id}, 地址 {video_url}")

    # 模拟AI分析过程，比如等待5秒
    import time
    time.sleep(5)

    # 模拟AI分析得出了一个“人员跌倒”的告警结果
    mock_alert = AlertPayload(
        camera_id=int(camera_id),
        event_type="person_fall_mock",  # 模拟事件
        confidence=0.92,
        location={"desc": "模拟位置 (x:100, y:200)"},
        details={"info": "这是一个由开发者B的框架生成的模拟告警"}
    )

    # 将上报任务添加到后台执行
    background_tasks.add_task(send_result_to_backend, mock_alert)
    print(f"模拟任务完成，已将上报告警 '{mock_alert.event_type}' 添加到后台队列。")


# --- API 入口 ---
@app.post("/analyze/video_stream/")
async def analyze_video_stream(camera_id: str, video_url: str, background_tasks: BackgroundTasks):
    """
    这个API接收到请求后，会立即将一个处理函数添加到后台任务队列。
    """
    # 将我们定义的模拟处理逻辑函数添加到后台
    background_tasks.add_task(mock_ai_processing_logic, camera_id, video_url, background_tasks)

    return {"status": "AI分析任务已在后台启动", "camera_id": camera_id, "video_url": video_url}


# --- 服务启动配置 ---
if __name__ == "__main__":
    # 使用 uvicorn 运行 FastAPI 应用，并开启热重载(reload=True)
    # 这意味着你修改并保存代码后，服务会自动重启，非常方便开发
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)