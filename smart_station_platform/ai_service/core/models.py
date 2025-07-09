# 文件: ai_service/core/models.py
from pydantic import BaseModel, Field
from typing import Optional, Any
import datetime

# [cite_start]这个模型需要严格对应后端 Django 的 Alert 模型字段 [cite: 17-18]
# 它定义了发送给后端的数据应该长什么样
class AlertPayload(BaseModel):
    camera_id: int = 1
    event_type: str = Field(..., example="人员检测") # "..."表示这个字段是必需的
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    location: dict = Field(default_factory=lambda: {"desc": "车站大厅A区"})
    confidence: Optional[float] = Field(None, example=0.95)
    image_snapshot_url: Optional[str] = None
    video_clip_url: Optional[str] = None
    status: str = "pending"  # 告警的初始状态
    details: Optional[dict[str, Any]] = None # 用于存放AI分析的具体原始数据