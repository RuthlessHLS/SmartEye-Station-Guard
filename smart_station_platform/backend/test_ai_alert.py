import requests
import json
from datetime import datetime

def test_ai_alert():
    # 1. 模拟AI服务分析视频流
    ai_service_url = "http://127.0.0.1:8001/analyze/video_stream/"
    params = {
        "camera_id": "test_camera_001",
        "video_stream_url": "http://example.com/stream/cam001"
    }
    response = requests.post(ai_service_url, params=params)
    print("AI服务响应:", response.json())

    # 2. 直接向后端发送告警数据
    backend_url = "http://127.0.0.1:8000/api/alerts/ai-results/"
    alert_data = {
        "camera_id": "test_camera_001",
        "event_type": "stranger_intrusion",
        "timestamp": datetime.now().isoformat(),
        "location": {
            "x": 100,
            "y": 200,
            "width": 50,
            "height": 100
        },
        "confidence": 0.95,
        "image_snapshot_url": "http://example.com/snapshots/test001.jpg",
        "video_clip_url": "http://example.com/clips/test001.mp4"
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    response = requests.post(
        backend_url,
        data=json.dumps(alert_data),
        headers=headers
    )

    print("\n告警发送结果:")
    print("状态码:", response.status_code)
    print("响应内容:", response.text)

if __name__ == "__main__":
    test_ai_alert() 