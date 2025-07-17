# 文件: ai_service/models/alert_models.py
# 描述: AI分析结果数据模型，用于发送告警信息到后端Django服务，以及服务配置模型。

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
import datetime


class AIAnalysisResult(BaseModel):
    """
    AI分析结果模型，用于向后端Django服务发送告警信息。
    此模型需要与Django后端的Alert模型字段保持一致。
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "camera_001",
                "event_type": "person_fall",
                "timestamp": "2023-12-30T10:00:00.000000",  # ISO 8601 格式
                "location": {
                    "box": [100, 150, 200, 300],
                    "description": "车站大厅A区"
                },
                "confidence": 0.85,
                "image_snapshot_url": "http://example.com/snapshot.jpg",
                "video_clip_url": "http://example.com/clip.mp4",
                "details": {
                    "person_count": 1,
                    "behavior_type": "fall_down",
                    "tracking_id": "FB_123"
                }
            }
        },
        extra='allow'  # 允许额外的字段，以便更灵活地传递details等
    )

    camera_id: str = Field(..., description="摄像头ID")
    event_type: str = Field(..., description="事件类型", examples=[
        "fire_detected", "smoke_detected", "person_detected", 
        "fall_detected", "fighting_detected", 
        "unknown_person_detected"
    ])
    timestamp: str = Field(..., description="事件发生的时间戳 (ISO格式)")
    location: Optional[Dict[str, Any]] = Field({}, description="事件发生的位置信息")
    confidence: float = Field(..., description="事件检测的置信度")
    image_snapshot_url: Optional[str] = Field(None, description="事件快照图片的URL")
    video_clip_url: Optional[str] = Field(None, description="事件录像片段的URL")
    details: Optional[Dict[str, Any]] = Field({}, description="事件的详细信息")
    image_data: Optional[str] = Field(None, description="事件快照的Base64编码图像")
    metadata: Optional[Dict[str, Any]] = Field({}, description="其他元数据")


class CameraConfig(BaseModel):
    """
    用于启动视频流时传递的摄像头配置信息。
    """
    model_config = ConfigDict(extra='ignore')  # 忽略未定义的额外字段

    camera_id: str = Field(..., description="要启动的摄像头的唯一标识符")
    stream_url: str = Field(..., description="视频流的URL，可以是RTSP、RTMP、HTTP等")
    location_description: str = Field("", description="摄像头的物理位置描述，例如 '大厅入口', '仓库A区'")

    # AI功能启用/禁用标志
    enable_face_recognition: bool = Field(True, description="是否启用人脸识别")
    enable_behavior_detection: bool = Field(False, description="是否启用行为检测")
    enable_object_detection: bool = Field(True, description="是否启用目标检测")
    enable_sound_detection: bool = Field(False, description="是否启用声学事件检测")
    enable_fire_detection: bool = Field(True, description="是否启用火焰烟雾检测")


class SystemStatus(BaseModel):
    """
    AI服务系统的当前运行状态信息。
    """
    model_config = ConfigDict(extra='allow')  # 允许额外的状态信息

    active_streams_count: int = Field(..., description="当前活跃的视频流数量")
    detectors_initialized: Dict[str, bool] = Field(..., description="各个AI检测器是否已成功初始化")

    # 可选的性能指标
    system_load: Optional[float] = Field(None, description="系统CPU使用率 (%)")
    memory_usage: Optional[float] = Field(None, description="系统内存使用率 (%)")
    gpu_status: Optional[Dict[str, Any]] = Field(None, description="GPU使用状态（如果可用）")

    # 活跃流的详细信息 (例如，哪些流在运行，它们的帧率等)
    active_streams_details: Dict[str, Dict[str, Any]] = Field(default_factory=dict,
                                                              description="每个活跃视频流的详细状态")