# backend/alerts/views.py (升级版)

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Alert
from .serializers import AlertSerializer, AlertCreateSerializer, AlertUpdateSerializer


class CustomPagination(PageNumberPagination):
    """
    自定义分页器，以匹配前端的 `total` 和 `results` 格式。
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class AlertListView(generics.ListAPIView):
    """
    告警列表API视图 (升级版)
    支持按类型、状态、时间范围筛选和分页。
    """
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        queryset = Alert.objects.all().order_by('-timestamp')

        # 从前端的请求参数中获取筛选条件
        alert_type = self.request.query_params.get('alert_type', None)
        status = self.request.query_params.get('status', None)
        start_time = self.request.query_params.get('start_time', None)
        end_time = self.request.query_params.get('end_time', None)

        if alert_type:
            queryset = queryset.filter(event_type=alert_type)
        if status:
            queryset = queryset.filter(status=status)
        if start_time:
            queryset = queryset.filter(timestamp__gte=start_time)
        if end_time:
            queryset = queryset.filter(timestamp__lte=end_time)

        return queryset


class AIResultReceiveView(generics.CreateAPIView):
    """
    接收AI服务发送的告警结果，并实时推送到前端。
    """
    queryset = Alert.objects.all()
    serializer_class = AlertCreateSerializer
    authentication_classes = []
    permission_classes = []

    def perform_create(self, serializer):
        instance = serializer.save()
        channel_layer = get_channel_layer()
        alert_data = AlertSerializer(instance).data

        async_to_sync(channel_layer.group_send)(
            'alerts_group',
            {
                'type': 'alert.message',
                'data': alert_data
            }
        )
        print(f"已通过WebSocket广播新告警: {alert_data['id']}")


class AlertUpdateView(generics.UpdateAPIView):
    """
    处理和更新单个告警的状态和备注 (通过PATCH方法)。
    这个视图将同时满足前端的“处理”和“更新状态”按钮的需求。
    """
    queryset = Alert.objects.all()
    serializer_class = AlertUpdateSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        # 自动将当前登录用户设置为处理人
        serializer.save(handler=self.request.user.username)