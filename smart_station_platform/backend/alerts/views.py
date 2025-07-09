# smart_station_platform/backend/alerts/views.py

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Q  # 用于复杂查询

from .models import Alert
from .serializers import AlertSerializer, AIResultReceiveSerializer, AlertUpdateSerializer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from datetime import datetime, timedelta


class AlertListView(generics.ListAPIView):
    """
    获取告警列表，支持筛选、排序和分页。
    """
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]  # 只有认证用户才能访问

    def get_queryset(self):
        queryset = super().get_queryset()

        # 筛选条件
        alert_type = self.request.query_params.get('alert_type')
        status = self.request.query_params.get('status')
        start_time_str = self.request.query_params.get('start_time')
        end_time_str = self.request.query_params.get('end_time')

        if alert_type:
            queryset = queryset.filter(event_type=alert_type)
        if status:
            queryset = queryset.filter(status=status)

        # 时间范围筛选
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str)
                queryset = queryset.filter(timestamp__gte=start_time)
            except ValueError:
                pass  # 忽略无效时间格式

        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str)
                queryset = queryset.filter(timestamp__lte=end_time)
            except ValueError:
                pass  # 忽略无效时间格式

        # 默认按时间倒序
        return queryset.order_by('-timestamp')


class AIResultReceiveView(APIView):
    """
    接收AI服务发送的分析结果，保存为告警记录，并实时推送到前端。
    """
    # 允许任何来源访问，因为AI服务可能没有认证（或者使用内部API Key认证）
    permission_classes = []  # 或者自定义一个内部API Key的权限类
    authentication_classes = []  # 不需要JWT认证

    def post(self, request, *args, **kwargs):
        serializer = AIResultReceiveSerializer(data=request.data)
        if serializer.is_valid():
            try:
                alert = serializer.save()  # 保存告警记录
                print(f"成功接收并保存AI告警: {alert.event_type} (ID: {alert.id})")

                # 获取 Channel Layer 实例
                channel_layer = get_channel_layer()
                if channel_layer:
                    # 准备要发送给前端的数据
                    # 使用 AlertSerializer 再次序列化，确保包含所有前端需要显示的字段
                    # 并且将外键关联的名称也包含进去
                    alert_data = AlertSerializer(alert).data
                    # 将 datetime 对象转换为 ISO 格式字符串，以便 JSON 序列化
                    alert_data['timestamp'] = alert.timestamp.isoformat()
                    if alert.created_at:
                        alert_data['created_at'] = alert.created_at.isoformat()
                    if alert.updated_at:
                        alert_data['updated_at'] = alert.updated_at.isoformat()

                    # 发送消息到 alerts_group
                    async_to_sync(channel_layer.group_send)(
                        "alerts_group",  # 组名，前端会订阅这个组
                        {
                            "type": "alert_message",  # 消息类型，对应 consumer 中的方法名
                            "message": alert_data,
                        }
                    )
                    print(f"告警 {alert.id} 已推送到 WebSocket alerts_group。")
                else:
                    print("警告: Channel Layer 未配置或无法获取。无法推送WebSocket消息。")

                return Response(AlertSerializer(alert).data, status=status.HTTP_201_CREATED)
            except Exception as e:
                print(f"保存告警或推送WebSocket时发生错误: {e}")
                return Response({"error": "处理告警时发生内部错误", "details": str(e)},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AlertUpdateView(generics.RetrieveUpdateAPIView):
    """
    更新指定ID的告警状态和处理备注。
    """
    queryset = Alert.objects.all()
    serializer_class = AlertUpdateSerializer  # 只允许更新状态和备注
    permission_classes = [IsAuthenticated]  # 只有认证用户才能访问

    def perform_update(self, serializer):
        # 自动设置处理人
        serializer.save(handler=self.request.user)
        # 可以在这里添加额外的WebSocket推送，通知告警状态更新


class AlertTestView(APIView):
    """
    测试Alert模型的视图
    """
    permission_classes = []  # 测试时暂时不需要认证
    
    def get(self, request, *args, **kwargs):
        try:
            # 1. 测试查询所有告警
            all_alerts = Alert.objects.all()
            print(f"总共找到 {all_alerts.count()} 条告警记录")

            # 2. 测试查询最新的一条告警
            latest_alert = Alert.objects.order_by('-timestamp').first()
            if latest_alert:
                print(f"最新告警: {latest_alert.event_type} - {latest_alert.timestamp}")

            # 3. 测试过滤查询
            pending_alerts = Alert.objects.filter(status='pending').count()
            print(f"待处理告警数量: {pending_alerts}")

            return Response({
                'status': 'success',
                'message': '模型测试成功',
                'data': {
                    'total_alerts': all_alerts.count(),
                    'latest_alert': AlertSerializer(latest_alert).data if latest_alert else None,
                    'pending_alerts': pending_alerts
                }
            })
        except Exception as e:
            print(f"测试时发生错误: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'测试失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)