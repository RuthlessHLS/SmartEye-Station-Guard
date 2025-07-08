from django.db import models

# Create your models here.

class Alert(models.Model):
    """
    告警事件模型，用于记录所有识别到的异常事件。
    """
    camera_id = models.CharField(max_length=100, help_text="摄像头ID")
    event_type = models.CharField(max_length=50, help_text="告警类型，如 'stranger_intrusion', 'person_fall'") # [cite: 71]
    timestamp = models.DateTimeField(auto_now_add=True, help_text="告警发生时间") # [cite: 72]
    location = models.JSONField(null=True, blank=True, help_text="存储坐标信息") # [cite: 72]
    confidence = models.FloatField(null=True, blank=True, help_text="算法置信度") # [cite: 73]
    image_snapshot_url = models.URLField(max_length=512, null=True, blank=True, help_text="告警截图URL") # [cite: 73]
    video_clip_url = models.URLField(max_length=512, null=True, blank=True, help_text="视频片段URL") # [cite: 73]
    status = models.CharField(
        max_length=20,
        default='pending',
        help_text="告警状态，如 'pending', 'in_progress', 'resolved'" # [cite: 73]
    )
    handler = models.CharField(max_length=100, null=True, blank=True, help_text="处理人") # [cite: 73]
    processing_notes = models.TextField(null=True, blank=True, help_text="处理备注") # [cite: 73]

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "告警事件"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"[{self.status}] {self.event_type} at {self.camera_id}"