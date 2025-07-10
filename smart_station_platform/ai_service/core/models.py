# 文件: ai_service/core/models.py (修复后)
from pydantic import BaseModel, Field, ConfigDict # 新增导入 ConfigDict
from typing import Optional, Any
from datetime import datetime

# 这个模型需要严格对应后端 Django 的 Alert 模型字段
# 它定义了发送给后端的数据应该长什么样
class AlertPayload(BaseModel):
    # 使用 model_config 来替代旧的 Config 类
    model_config = ConfigDict( # 使用 ConfigDict 来定义模型配置
        json_schema_extra={ # 将 schema_extra 更名为 json_schema_extra
            "example": {
                "camera_id": 1,
                "event_type": "fall_down",
                "timestamp": "2023-10-27T10:00:00.000000",
                "location": {"desc": "大厅B区"},
                "confidence": 0.98,
                "image_snapshot_url": "http://example.com/snapshot.jpg",
                "video_clip_url": "http://example.com/clip.mp4",
                "status": "new",
                "details": {"person_id": "P001", "behavior": "摔倒"}
            }
        }
    )

    camera_id: int = 1
    event_type: str = Field(..., example="人员检测")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    location: dict = Field(default_factory=lambda: {"desc": "车站大厅A区"})
    confidence: Optional[float] = Field(None, example=0.95)
    image_snapshot_url: Optional[str] = None
    video_clip_url: Optional[str] = None
    status: str = "pending"
    details: Optional[dict[str, Any]] = None