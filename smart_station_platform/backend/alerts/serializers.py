# smart_station_platform/backend/alerts/serializers.py

from rest_framework import serializers
from .models import Alert
from camera_management.models import Camera # 导入 Camera 模型
from django.utils import timezone  # 添加导入
from .models import AlertLog

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
            print(f"找到摄像头记录: {camera_name}")
        except Camera.DoesNotExist:
            # 自动创建摄像头记录
            print(f"未找到摄像头 '{camera_name}'，正在自动创建...")
            camera_instance = Camera.objects.create(
                name=camera_name,
                location_desc=f"AI服务自动创建 - {camera_name}",
                rtsp_url="",  # 空RTSP URL，稍后可以手动配置
                is_active=True
            )
            print(f"成功创建摄像头记录: {camera_name} (ID: {camera_instance.id})")

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

# Alert 创建序列化器 (用于前端)
class AlertCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        # 允许前端创建时只提供部分字段
        fields = ['camera', 'event_type', 'location', 'confidence', 'image_snapshot_url', 'video_clip_url']

# Alert 处理序列化器 (专门用于处理告警状态和备注)
class AlertHandleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        # 允许更新处理相关的字段
        fields = ['status', 'processing_notes', 'handler']  # 加上 handler
    
    def validate_status(self, value):
        """验证状态值是否有效"""
        valid_statuses = [choice[0] for choice in Alert.STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"无效的状态值。有效选项：{valid_statuses}")
        return value

# Alert 一般更新序列化器 (用于更新告警的基本信息)
class AlertUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        # 允许更新除了处理相关字段外的其他字段
        fields = ['event_type', 'location', 'confidence', 'image_snapshot_url', 'video_clip_url']
        
    def validate_event_type(self, value):
        """验证事件类型是否有效"""
        valid_types = [choice[0] for choice in Alert.EVENT_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(f"无效的事件类型。有效选项：{valid_types}")
        return value

# Alert 详情序列化器 (包含更多详细信息)
class AlertDetailSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    camera_location = serializers.CharField(source='camera.location', read_only=True)
    handler_username = serializers.CharField(source='handler.username', read_only=True)
    handler_full_name = serializers.SerializerMethodField()
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Alert
        fields = '__all__'
        
    def get_handler_full_name(self, obj):
        """获取处理人的完整姓名"""
        if obj.handler:
            return f"{obj.handler.first_name} {obj.handler.last_name}".strip() or obj.handler.username
        return None

class AlertLogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    class Meta:
        model = AlertLog
        fields = ['id', 'user', 'action', 'detail', 'created_at']