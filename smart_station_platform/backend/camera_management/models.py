from django.db import models

# Create your models here.

class Camera(models.Model):
    """
    摄像头信息模型
    """
    name = models.CharField(max_length=100, unique=True, help_text="摄像头名称")
    rtsp_url = models.CharField(max_length=512, help_text="摄像头的RTSP或视频流地址") # [cite: 81]
    location_desc = models.CharField(max_length=255, blank=True, null=True, help_text="具体位置描述") # [cite: 81]

    class Meta:
        verbose_name = "摄像头"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

class DangerousArea(models.Model):
    """
    危险区域模型，与摄像头关联
    """
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='dangerous_areas', help_text="关联的摄像头") # [cite: 82]
    name = models.CharField(max_length=100, help_text="危险区域名称")
    coordinates = models.JSONField(help_text="存储前端绘制的多边形顶点坐标数组") # [cite: 82]

    class Meta:
        verbose_name = "危险区域"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.name} for {self.camera.name}"