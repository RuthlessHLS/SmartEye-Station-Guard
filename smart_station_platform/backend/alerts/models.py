# smart_station_platform/backend/alerts/models.py

from django.db import models
from django.conf import settings
from django.db.models import JSONField
from camera_management.models import Camera  # 添加导入
from django.contrib.auth import get_user_model  # 添加导入

class Alert(models.Model):
    """
    告警模型，存储由AI服务生成的告警事件。
    对应项目文档中的 F-AR-01:告警事件管理。
    """
    # 告警类型选项
    EVENT_TYPE_CHOICES = [
        ('stranger_intrusion', '陌生人入侵'),
        ('person_fall', '人员跌倒'),
        ('fire_smoke', '明火烟雾'),
        ('stranger_face_detected', '陌生人脸检测'), # 对应人脸识别 F-VM-01
        ('spoofing_attack', '活体欺骗攻击'), # 对应活体检测 F-VM-02
        ('abnormal_sound_scream', '异常声音: 尖叫'), # 对应异常声学 F-VM-05
        ('abnormal_sound_fight', '异常声音: 打架'),
        ('abnormal_sound_glass_break', '异常声音: 玻璃破碎'),
        ('other', '其他异常'),
    ]

    # 告警状态选项
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('in_progress', '处理中'),
        ('resolved', '已解决'),
        ('ignored', '已忽略'),
    ]

    id = models.BigAutoField(primary_key=True)
    camera = models.ForeignKey(Camera, models.DO_NOTHING, blank=True, null=True, verbose_name="关联摄像头")
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, verbose_name="告警类型")
    timestamp = models.DateTimeField(verbose_name="告警时间")
    location = JSONField(verbose_name="告警位置信息")
    confidence = models.FloatField(verbose_name="置信度")
    image_snapshot_url = models.CharField(max_length=500, blank=True, null=True, verbose_name="告警截图URL")
    video_clip_url = models.CharField(max_length=500, blank=True, null=True, verbose_name="告警视频片段URL")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name="告警状态")
    handler = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # 使用settings中配置的用户模型
        models.DO_NOTHING,
        blank=True,
        null=True,
        verbose_name="处理人"
    )
    processing_notes = models.TextField(blank=True, null=True, verbose_name="处理备注")
    created_at = models.DateTimeField(verbose_name="创建时间")
    updated_at = models.DateTimeField(verbose_name="更新时间")

    class Meta:
        managed = False  # 让Django不管理这个表的创建和删除
        db_table = 'alerts_alert'
        verbose_name = "告警"
        verbose_name_plural = "告警管理"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.event_type} - {self.camera.name if self.camera else '未知摄像头'} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"