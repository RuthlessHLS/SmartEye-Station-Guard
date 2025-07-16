# smart_station_platform/backend/alerts/views.py
import os
import json
import logging
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser # Added for WebSocketBroadcastView
from rest_framework.permissions import AllowAny # Added for WebSocketBroadcastView

from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Alert, AlertLog, Camera
from .serializers import (
    AlertSerializer,
    AlertDetailSerializer,
    AIResultReceiveSerializer,
    AlertUpdateSerializer,
    AlertHandleSerializer,
    AlertLogSerializer
)

logger = logging.getLogger(__name__)

# --- 自定义权限 ---
class IsAuthenticatedOrInternal(IsAuthenticated):
    """
    一个自定义的权限类，用于区分普通用户和内部服务。
    """
    def has_permission(self, request, view):
        # 如果是受信任的内部服务调用（由中间件标记），则直接允许访问
        if getattr(request, 'is_internal_call', False):
            return True
        # 否则，回退到标准的IsAuthenticated检查，确保登录用户才能访问
        return super().has_permission(request, view)

# --- 分页配置 ---
class AlertPagination(PageNumberPagination):
    """告警列表分页配置"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

# --- 视图 ---
class AlertListView(generics.ListAPIView):
    """
    获取告警列表，支持筛选、排序和分页。
    GET /alerts/list/
    """
    queryset = Alert.objects.select_related('camera', 'handler').all()
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AlertPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = {
        'status': ['exact', 'in'],
        'camera': ['exact'],
        'confidence': ['gte', 'lte'],
        'timestamp': ['gte', 'lte', 'date'],
    }
    ordering_fields = ['timestamp', 'confidence', 'created_at', 'updated_at']
    ordering = ['-timestamp']
    search_fields = ['event_type', 'camera__name', 'processing_notes']

    def get_queryset(self):
        queryset = super().get_queryset()
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        start_time_str = self.request.query_params.get('start_time')
        end_time_str = self.request.query_params.get('end_time')
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                queryset = queryset.filter(timestamp__gte=start_time)
            except ValueError: pass
        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                queryset = queryset.filter(timestamp__lte=end_time)
            except ValueError: pass
        return queryset

class AlertDetailView(generics.RetrieveAPIView):
    """
    获取告警详情。
    GET /alerts/{id}/
    """
    queryset = Alert.objects.select_related('camera', 'handler').all()
    serializer_class = AlertDetailSerializer
    permission_classes = [IsAuthenticated]

class AlertHandleView(generics.RetrieveUpdateAPIView):
    """
    处理告警：更新告警状态和添加处理备注。
    PUT/PATCH /alerts/{id}/handle/
    """
    queryset = Alert.objects.select_related('camera', 'handler').all()
    serializer_class = AlertHandleSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        alert = serializer.save(handler=self.request.user)
        action = '处理告警' if alert.status == 'in_progress' else '标记为已解决'
        AlertLog.objects.create(
            alert=alert, user=self.request.user, action=action,
            detail=f'状态变为{alert.get_status_display()}，备注：{alert.processing_notes}'
        )
        self._send_alert_update_notification(alert, 'handle')

    def _send_alert_update_notification(self, alert, action_type):
        _send_websocket_notification(alert, action_type)

class AlertUpdateView(generics.RetrieveUpdateAPIView):
    """
    更新告警基本信息。
    PUT/PATCH /alerts/{id}/update/
    """
    queryset = Alert.objects.all()
    serializer_class = AlertUpdateSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        alert = serializer.save()
        self._send_alert_update_notification(alert, 'update')

    def _send_alert_update_notification(self, alert, action_type):
        _send_websocket_notification(alert, action_type)

# --- 内部API视图 ---

class AIResultReceiveView(APIView):
    """
    接收AI服务发送的分析结果 (ai-results)。
    这个视图现在使用 IsAuthenticatedOrInternal 权限。
    """
    permission_classes = [IsAuthenticatedOrInternal]

    @swagger_auto_schema(request_body=AIResultReceiveSerializer)
    def post(self, request, *args, **kwargs):
        serializer = AIResultReceiveSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"AI结果序列化失败: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        alert = serializer.save()
        _send_websocket_notification(alert, 'new_alert')
        return Response(AlertDetailSerializer(alert).data, status=status.HTTP_201_CREATED)

class WebSocketBroadcastView(APIView):
    permission_classes = [AllowAny]  # 注意：在生产中应使用更安全的权限

    def post(self, request, *args, **kwargs):
        # AI服务发送的数据结构是: {"camera_id": "...", "payload": {"type": "...", "data": {...}}}
        # 我们关心的是 'payload' 的内容
        payload = request.data.get('payload')
        logger.info(f"Broadcast view received payload: {payload}")

        if not payload or not isinstance(payload, dict):
            logger.error(f"Broadcast view received invalid or missing 'payload': {request.data}")
            return Response(
                {"error": "A valid 'payload' object is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # payload 内部包含了前端需要的所有信息 (e.g., {"type": "...", "data": {...}})
        message_to_send = payload

        logger.info(f"Broadcasting message to 'alerts' group: {message_to_send}")

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "alerts",
            {
                "type": "send_alert",
                "message": message_to_send,
            },
        )
        return Response({"status": "ok", "message": "Broadcast successful"}, status=status.HTTP_200_OK)

# --- 辅助函数 ---
def _send_websocket_notification(alert, action_type):
    """发送告警相关的WebSocket通知的辅助函数"""
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.error("Channel layer 未配置，无法发送通知。")
            return

        alert_data = AlertDetailSerializer(alert).data
        # 确保时间字段可序列化
        for key in ['timestamp', 'created_at', 'updated_at']:
            if alert_data.get(key) and isinstance(alert_data[key], datetime):
                alert_data[key] = alert_data[key].isoformat()

        camera_id = alert.camera.id if alert.camera else 'unknown'
        group_name = f"camera_{camera_id}"
        
        event_map = {
            'new_alert': 'new_alert',
            'handle': 'alert_update',
            'update': 'alert_update'
        }
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": event_map.get(action_type, "alert_update"),
                "message": {"action": action_type, "alert": alert_data}
            }
        )
    except Exception as e:
        logger.error(f"发送WebSocket通知时发生错误: {e}", exc_info=True)

# --- 其他视图 ---
class AlertStatsView(generics.GenericAPIView):
    """获取告警统计信息。"""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        total_alerts = Alert.objects.count()
        event_type_stats = {item['event_type']: item['count'] for item in Alert.objects.values('event_type').annotate(count=models.Count('id'))}
        
        return Response({
            'total_alerts': total_alerts,
            'pending_alerts': Alert.objects.filter(status='pending').count(),
            'in_progress_alerts': Alert.objects.filter(status='in_progress').count(),
            'resolved_alerts': Alert.objects.filter(status='resolved').count(),
            'recent_alerts': Alert.objects.filter(timestamp__gte=timezone.now() - timedelta(hours=24)).count(),
            'event_type_stats': event_type_stats,
        })

class AlertLogListView(generics.ListAPIView):
    """获取指定告警的操作日志列表。"""
    serializer_class = AlertLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        alert_id = self.kwargs['alert_id']
        return AlertLog.objects.filter(alert_id=alert_id).order_by('-timestamp')