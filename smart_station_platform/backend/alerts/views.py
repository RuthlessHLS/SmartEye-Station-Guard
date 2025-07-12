# smart_station_platform/backend/alerts/views.py
from drf_yasg.utils import swagger_auto_schema
from .serializers import AIResultReceiveSerializer  # 如果没import的话
from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Q  # 用于复杂查询
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model

from .models import Alert
from .serializers import (
    AlertSerializer, 
    AlertDetailSerializer,
    AIResultReceiveSerializer, 
    AlertUpdateSerializer,
    AlertHandleSerializer
)
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from datetime import datetime, timedelta
from drf_yasg.utils import swagger_auto_schema
import logging
import os # Added for API key validation
logger = logging.getLogger(__name__)


class AlertPagination(PageNumberPagination):
    """告警列表分页配置"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AlertListView(generics.ListAPIView):
    """
    获取告警列表，支持筛选、排序和分页。
    GET /alerts/list/
    """
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AlertPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    
    # 支持的筛选字段
    filterset_fields = {
        # 'event_type': ['exact', 'in'],  # 移除或注释掉
        'status': ['exact', 'in'],
        'camera': ['exact'],
        'confidence': ['gte', 'lte'],
        'timestamp': ['gte', 'lte', 'date'],
    }
    
    # 支持的排序字段
    ordering_fields = ['timestamp', 'confidence', 'created_at', 'updated_at']
    ordering = ['-timestamp']  # 默认按时间倒序
    
    # 支持搜索的字段
    search_fields = ['event_type', 'camera__name', 'processing_notes']

    def get_queryset(self):
        queryset = super().get_queryset()
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        # 自定义时间范围筛选
        start_time_str = self.request.query_params.get('start_time')
        end_time_str = self.request.query_params.get('end_time')
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                queryset = queryset.filter(timestamp__gte=start_time)
            except ValueError:
                pass
        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                queryset = queryset.filter(timestamp__lte=end_time)
            except ValueError:
                pass
        return queryset.select_related('camera', 'handler')


class AlertDetailView(generics.RetrieveAPIView):
    """
    获取告警详情。
    GET /alerts/{id}/
    """
    queryset = Alert.objects.all()
    serializer_class = AlertDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().select_related('camera', 'handler')


class AlertHandleView(generics.RetrieveUpdateAPIView):
    """
    处理告警：更新告警状态和添加处理备注。
    PUT/PATCH /alerts/{id}/handle/
    """
    queryset = Alert.objects.all()
    serializer_class = AlertHandleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().select_related('camera', 'handler')

    def perform_update(self, serializer):
        print("=== perform_update called ===")
        alert = serializer.save(handler=self.request.user)
        
        # 发送WebSocket通知告警状态更新
        self._send_alert_update_notification(alert, 'handle')

    def _send_alert_update_notification(self, alert, action_type):
        """发送告警更新的WebSocket通知"""
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                alert_data = AlertDetailSerializer(alert).data
                # 确保时间字段可以序列化
                alert_data['timestamp'] = alert.timestamp.isoformat()
                if alert.created_at:
                    alert_data['created_at'] = alert.created_at.isoformat()
                if alert.updated_at:
                    alert_data['updated_at'] = alert.updated_at.isoformat()

                async_to_sync(channel_layer.group_send)(
                    "alerts_group",
                    {
                        "type": "alert_update_message",
                        "message": {
                            "action": action_type,
                            "alert": alert_data
                        }
                    }
                )
                print(f"告警 {alert.id} 的{action_type}操作已推送到WebSocket。")
        except Exception as e:
            print(f"发送WebSocket通知时发生错误: {e}")


class AlertUpdateView(generics.RetrieveUpdateAPIView):
    """
    更新告警基本信息。
    PUT/PATCH /alerts/{id}/update/
    """
    queryset = Alert.objects.all()
    serializer_class = AlertUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().select_related('camera', 'handler')

    def perform_update(self, serializer):
        alert = serializer.save()
        
        # 发送WebSocket通知告警信息更新
        self._send_alert_update_notification(alert, 'update')

    def _send_alert_update_notification(self, alert, action_type):
        """发送告警更新的WebSocket通知"""
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                alert_data = AlertDetailSerializer(alert).data
                # 确保时间字段可以序列化
                alert_data['timestamp'] = alert.timestamp.isoformat()
                if alert.created_at:
                    alert_data['created_at'] = alert.created_at.isoformat()
                if alert.updated_at:
                    alert_data['updated_at'] = alert.updated_at.isoformat()

                async_to_sync(channel_layer.group_send)(
                    "alerts_group",
                    {
                        "type": "alert_update_message",
                        "message": {
                            "action": action_type,
                            "alert": alert_data
                        }
                    }
                )
                print(f"告警 {alert.id} 的{action_type}操作已推送到WebSocket。")
        except Exception as e:
            print(f"发送WebSocket通知时发生错误: {e}")


class AIResultReceiveView(APIView):
    """
    接收AI服务发送的分析结果，保存为告警记录，并实时推送到前端。
    POST /alerts/ai-results/
    """
    permission_classes = []
    authentication_classes = []

    def check_api_key(self, request):
        """验证API密钥"""
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return False
        # 从环境变量或设置中获取有效的API密钥，提供默认值
        valid_api_key = os.getenv('AI_SERVICE_API_KEY', 'smarteye-ai-service-key-2024')
        return api_key == valid_api_key

    @swagger_auto_schema(request_body=AIResultReceiveSerializer)
    def post(self, request, *args, **kwargs):
        """处理AI服务发送的分析结果"""
        # 验证API密钥
        if not self.check_api_key(request):
            return Response(
                {"error": "Invalid or missing API key"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            serializer = AIResultReceiveSerializer(data=request.data)
            if serializer.is_valid():
                # 数据预处理和验证
                data = serializer.validated_data
                
                # 检查必要字段
                required_fields = ['camera_id', 'event_type', 'confidence', 'timestamp']
                if not all(field in data for field in required_fields):
                    return Response(
                        {"error": "Missing required fields"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # 创建告警记录
                alert = serializer.save()

                try:
                    # 发送WebSocket通知
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        alert_data = AlertDetailSerializer(alert).data
                        async_to_sync(channel_layer.group_send)(
                            "alerts_group",
                            {
                                "type": "alert_message",
                                "message": {
                                    "action": "new_alert",
                                    "alert": alert_data
                                }
                            }
                        )
                except Exception as ws_error:
                    logger.error(f"WebSocket通知发送失败: {str(ws_error)}")
                    # 即使WebSocket发送失败，我们仍然返回成功，因为告警已经保存
                
                return Response(
                    {"message": "Alert created successfully", "id": alert.id},
                    status=status.HTTP_201_CREATED
                )
            else:
                logger.error(f"AI结果数据验证失败: {serializer.errors}")
                return Response(
                    {"error": "Invalid data", "details": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(f"处理AI分析结果时发生异常: {str(e)}")
            return Response(
                {"error": "Internal server error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WebSocketBroadcastView(APIView):
    """
    WebSocket广播接口，用于向前端推送实时数据
    POST /alerts/websocket/broadcast/
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        """广播消息到WebSocket客户端"""
        try:
            message_data = request.data
            message_type = message_data.get('type', 'unknown')
            
            print(f"📡 收到WebSocket广播请求: {message_type}")
            
            # 发送到WebSocket组
            channel_layer = get_channel_layer()
            if channel_layer:
                # 根据消息类型选择合适的处理方式
                if message_type == 'detection_result':
                    # 检测结果不保存到数据库，只推送给前端
                    async_to_sync(channel_layer.group_send)(
                        "alerts_group",
                        {
                            "type": "alert_message",
                            "message": {
                                "type": "detection_result",
                                "data": message_data.get('data', {})
                            }
                        }
                    )
                elif message_type == 'system_status':
                    # 系统状态更新
                    async_to_sync(channel_layer.group_send)(
                        "alerts_group",
                        {
                            "type": "alert_message", 
                            "message": {
                                "type": "system_status",
                                "data": message_data.get('data', {})
                            }
                        }
                    )
                else:
                    # 其他类型的消息
                    async_to_sync(channel_layer.group_send)(
                        "alerts_group",
                        {
                            "type": "alert_message",
                            "message": message_data
                        }
                    )
                
                print(f"✅ WebSocket消息已广播: {message_type}")
                return Response({"status": "success", "message": "Message broadcasted"})
            else:
                return Response(
                    {"status": "error", "message": "WebSocket not available"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            print(f"WebSocket广播失败: {e}")
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AlertStatsView(APIView):
    """
    获取告警统计信息。
    GET /alerts/stats/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            # 基础统计
            total_alerts = Alert.objects.count()
            pending_alerts = Alert.objects.filter(status='pending').count()
            in_progress_alerts = Alert.objects.filter(status='in_progress').count()
            resolved_alerts = Alert.objects.filter(status='resolved').count()
            
            # 按事件类型统计
            event_type_stats = {}
            for event_type, display_name in Alert.EVENT_TYPE_CHOICES:
                count = Alert.objects.filter(event_type=event_type).count()
                event_type_stats[event_type] = {
                    'count': count,
                    'display_name': display_name
                }
            
            # 最近24小时告警数量
            from django.utils import timezone
            twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
            recent_alerts = Alert.objects.filter(timestamp__gte=twenty_four_hours_ago).count()
            
            return Response({
                'total_alerts': total_alerts,
                'pending_alerts': pending_alerts,
                'in_progress_alerts': in_progress_alerts,
                'resolved_alerts': resolved_alerts,
                'recent_alerts': recent_alerts,
                'event_type_stats': event_type_stats,
            })
        except Exception as e:
            return Response(
                {'error': f'获取统计信息失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AlertTestView(APIView):
    """
    测试Alert模型的视图
    """
    permission_classes = []
    
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