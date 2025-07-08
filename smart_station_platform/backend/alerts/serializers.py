from rest_framework import serializers
from .models import Alert

class AlertSerializer(serializers.ModelSerializer):
    """
    用于读取和展示告警信息的序列化器
    """
    class Meta:
        model = Alert
        fields = '__all__' # 显示所有字段

class AlertCreateSerializer(serializers.ModelSerializer):
    """
    专门用于创建新告警的序列化器
    """
    class Meta:
        model = Alert
        # 只包含需要从AI服务接收的字段
        fields = ['camera_id', 'event_type', 'location', 'confidence', 'image_snapshot_url', 'video_clip_url']

class AlertUpdateSerializer(serializers.ModelSerializer):
    """
    专门用于处理（更新）告警的序列化器
    """
    class Meta:
        model = Alert
        # 只包含处理告警时需要修改的字段
        fields = ['status', 'handler', 'processing_notes']