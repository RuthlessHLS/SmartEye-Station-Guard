# 文件: ai_service/models/alert_models.py
# 描述: AI分析结果数据模型，用于发送告警信息到后端Django服务

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import datetime


class AIAnalysisResult(BaseModel):
    """
    AI分析结果模型，用于向后端Django服务发送告警信息
    此模型需要与Django后端的Alert模型字段保持一致
    """
    
    camera_id: str = Field(..., description="摄像头ID或传感器ID")
    event_type: str = Field(..., description="事件类型，如 'person_fall', 'stranger_intrusion' 等")
    timestamp: float = Field(..., description="事件发生的时间戳")
    location: Dict[str, Any] = Field(default_factory=dict, description="事件位置信息")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="AI检测的置信度，0-1之间")
    
    # 可选字段
    image_snapshot_url: Optional[str] = Field(None, description="事件快照图片URL")
    video_clip_url: Optional[str] = Field(None, description="事件视频片段URL")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="详细信息")
    
    class Config:
        # 提供示例数据，方便API文档生成
        schema_extra = {
            "example": {
                "camera_id": "camera_001",
                "event_type": "person_fall",
                "timestamp": 1703958400.0,
                "location": {
                    "box": [100, 150, 200, 300],
                    "description": "车站大厅A区"
                },
                "confidence": 0.85,
                "image_snapshot_url": "http://example.com/snapshot.jpg",
                "video_clip_url": "http://example.com/clip.mp4",
                "details": {
                    "person_count": 1,
                    "behavior_type": "fall_down"
                }
            }
        }


class CameraConfig(BaseModel):
    """
    摄像头配置信息
    """
    camera_id: str
    stream_url: str
    location_description: str = ""
    enable_face_recognition: bool = True
    enable_behavior_detection: bool = True
    enable_object_detection: bool = True
    
    
class SystemStatus(BaseModel):
    """
    AI系统状态信息
    """
    active_streams_count: int
    detectors_initialized: Dict[str, bool]
    system_load: Optional[float] = None
    memory_usage: Optional[float] = None 