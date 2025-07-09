# smart_station_platform/backend/camera_management/models.py

from django.db import models
from django.db.models import JSONField # 确保是这一行
from django.utils import timezone # 新增
import datetime # 新增
class Camera(models.Model):
    """
    摄像头模型，存储摄像头的基本信息。
    对应项目文档中的 F-VM-01:人脸识别与门禁 中的摄像头信息。
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="摄像头名称")
    rtsp_url = models.URLField(max_length=255, blank=True, null=True, verbose_name="RTSP流地址")
    location_desc = models.CharField(max_length=255, blank=True, null=True, verbose_name="位置描述")
    is_active = models.BooleanField(default=True, verbose_name="是否启用") # 新增字段
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间") # 新增字段
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间") # 新增字段

    class Meta:
        verbose_name = "摄像头"
        verbose_name_plural = "摄像头管理"
        ordering = ['name']

    def __str__(self):
        return self.name


class DangerousArea(models.Model):
    """
    危险区域模型，存储与摄像头关联的危险区域信息。
    对应项目文档中的 F-VM-03:危险区域入侵检测。
    """
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='dangerous_areas', verbose_name="关联摄像头")
    name = models.CharField(max_length=100, verbose_name="区域名称")
    # coordinates 存储多边形坐标，使用 JSONField 存储列表的列表，例如：
    # [[x1, y1], [x2, y2], [x3, y3]]
    coordinates = JSONField(verbose_name="区域坐标 (JSON)")
    # 告警规则配置 (新增字段)
    min_distance_threshold = models.FloatField(default=0.0, verbose_name="距离边缘最小距离阈值(米)", help_text="人员距离边缘小于此值时告警") # 新增字段
    time_in_area_threshold = models.IntegerField(default=0, verbose_name="区域内停留时间阈值(秒)", help_text="人员在区域内停留超过此值时告警") # 新增字段
    is_active = models.BooleanField(default=True, verbose_name="是否启用") # 新增字段
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间") # 新增字段
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间") # 新增字段

    class Meta:
        verbose_name = "危险区域"
        verbose_name_plural = "危险区域管理"
        unique_together = ('camera', 'name') # 同一摄像头下区域名称唯一
        ordering = ['camera', 'name']

    def __str__(self):
        return f"{self.camera.name} - {self.name}"