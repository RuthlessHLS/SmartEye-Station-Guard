# smart_station_platform/backend/alerts/serializers.py

from rest_framework import serializers
from .models import Alert
from camera_management.models import Camera # 导入 Camera 模型
from django.utils import timezone  # 添加导入

# Alert 列表和详情的序列化器
class AlertSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    handler_username = serializers.CharField(source='handler.username', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Alert
        fields = '__all__' # 包含所有字段，包括外键关联的名称

# 用于接收AI服务发送的告警数据的序列化器
# 这个序列化器将直接用于 /api/alerts/ai-results/ 接口
class AIResultReceiveSerializer(serializers.Serializer):
    # 这里的字段必须与 ai_service/app.py 中 AIAnalysisResult 的字段严格匹配
    camera_id = serializers.CharField(max_length=100) # 对应 Camera 模型的 name 字段
    event_type = serializers.CharField(max_length=50)
    timestamp = serializers.DateTimeField(required=False) # AI服务发送，后端也可以自动生成
    location = serializers.JSONField()
    confidence = serializers.FloatField()
    image_snapshot_url = serializers.URLField(max_length=500, required=False, allow_blank=True, allow_null=True)
    video_clip_url = serializers.URLField(max_length=500, required=False, allow_blank=True, allow_null=True)

    def create(self, validated_data):
        # 根据 camera_id 查找对应的 Camera 实例
        camera_name = validated_data.pop('camera_id')
        try:
            camera_instance = Camera.objects.get(name=camera_name)
        except Camera.DoesNotExist:
            print(f"警告: 未找到名为 '{camera_name}' 的摄像头。告警将不关联摄像头。")
            camera_instance = None

        # 如果没有提供timestamp，使用当前时间
        if 'timestamp' not in validated_data or validated_data['timestamp'] is None:
            validated_data['timestamp'] = timezone.now()

        # 获取当前时间
        current_time = timezone.now()

        # 创建 Alert 实例
        alert = Alert.objects.create(
            camera=camera_instance,
            event_type=validated_data['event_type'],
            timestamp=validated_data['timestamp'],
            location=validated_data['location'],
            confidence=validated_data['confidence'],
            image_snapshot_url=validated_data.get('image_snapshot_url'),
            video_clip_url=validated_data.get('video_clip_url'),
            status='pending', # 初始状态设置为待处理
            created_at=current_time,  # 手动设置创建时间
            updated_at=current_time   # 手动设置更新时间
        )
        return alert

# Alert 创建和更新的序列化器 (用于前端)
class AlertCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        # 允许前端创建时只提供部分字段
        fields = ['camera', 'event_type', 'location', 'confidence', 'image_snapshot_url', 'video_clip_url']

class AlertUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        # 允许前端更新状态和备注
        fields = ['status', 'handler', 'processing_notes']