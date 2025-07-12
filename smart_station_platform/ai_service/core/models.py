# 文件: ai_service/core/models.py
import os

# 模型路径配置 - 使用相对路径
MODEL_BASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
YOLO_MODEL_PATH = os.path.join(MODEL_BASE_PATH, "yolov8n.pt")
FASTER_RCNN_MODEL_PATH = os.path.join(MODEL_BASE_PATH, "fasterrcnn_resnet50_fpn_coco-258fb6c6.pth")
COCO_NAMES_PATH = os.path.join(MODEL_BASE_PATH, "coco.names")

# 其他配置保持不变
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
from datetime import datetime

# 这个模型需要严格对应后端 Django 的 Alert 模型字段
class AlertPayload(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
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
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    location: dict = Field(default_factory=lambda: {"desc": "车站大厅A区"})
    confidence: Optional[float] = Field(None, example=0.95)
    image_snapshot_url: Optional[str] = None
    video_clip_url: Optional[str] = None
    status: str = "pending"
    details: Optional[dict[str, Any]] = None
