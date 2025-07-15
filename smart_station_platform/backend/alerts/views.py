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
from django.utils import timezone
from django.core.cache import cache

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

                # 【修复】使用动态的、与摄像头关联的组名
                camera_id = alert.camera.id if alert.camera else 'unknown'
                group_name = f"camera_{camera_id}"

                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "alert_update", # 使用与 consumer 中方法匹配的类型
                        "message": {
                            "action": action_type,
                            "alert": alert_data
                        }
                    }
                )
                print(f"告警 {alert.id} 的{action_type}操作已推送到WebSocket (Group: {group_name})。")
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

                # 【修复】使用动态的、与摄像头关联的组名
                camera_id = alert.camera.id if alert.camera else 'unknown'
                group_name = f"camera_{camera_id}"
                
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "alert_update", # 使用与 consumer 中方法匹配的类型
                        "message": {
                            "action": action_type,
                            "alert": alert_data
                        }
                    }
                )
                print(f"告警 {alert.id} 的{action_type}操作已推送到WebSocket (Group: {group_name})。")
        except Exception as e:
            print(f"发送WebSocket通知时发生错误: {e}")


class AlertThrottleManager:
    """
    告警限流管理器，用于限制短时间内重复的告警数量
    """
    # 默认限流时间（秒）
    DEFAULT_THROTTLE_SECONDS = 10
    
    # 缓存前缀
    CACHE_PREFIX = "alert_throttle_"
    
    @classmethod
    def should_throttle(cls, camera_id, event_type, throttle_seconds=None):
        """
        检查是否应该限流特定类型的告警
        
        参数:
            camera_id: 摄像头ID
            event_type: 告警类型
            throttle_seconds: 限流时间（秒），默认为10秒
            
        返回:
            (bool, int): 是否应该限流，以及当前累积的告警数量
        """
        if throttle_seconds is None:
            throttle_seconds = cls.DEFAULT_THROTTLE_SECONDS
            
        # 构建缓存键
        cache_key = f"{cls.CACHE_PREFIX}{camera_id}_{event_type}"
        
        # 获取当前缓存的告警信息
        alert_data = cache.get(cache_key)
        
        now = timezone.now()
        
        if alert_data is None:
            # 第一次出现该类型告警，不限流
            cache.set(
                cache_key, 
                {"first_alert_time": now, "count": 1},
                timeout=throttle_seconds * 2  # 设置缓存过期时间为限流时间的两倍
            )
            return False, 1
            
        # 更新计数
        alert_data["count"] += 1
        
        # 计算时间差
        first_alert_time = alert_data["first_alert_time"]
        time_diff = (now - first_alert_time).total_seconds()
        
        # 更新缓存
        cache.set(
            cache_key,
            alert_data,
            timeout=throttle_seconds * 2  # 重置过期时间
        )
        
        # 如果在限流时间内，则限流
        if time_diff < throttle_seconds:
            logger.info(
                f"告警限流: 摄像头={camera_id}, 类型={event_type}, "
                f"在{time_diff:.1f}秒内第{alert_data['count']}次触发"
            )
            return True, alert_data["count"]
            
        # 超过限流时间，重置计数器
        cache.set(
            cache_key,
            {"first_alert_time": now, "count": 1},
            timeout=throttle_seconds * 2
        )
        return False, 1
    
    @classmethod
    def get_throttle_stats(cls):
        """获取当前所有限流状态的统计信息"""
        # 注意：此方法在实际应用中可能不可行，因为Redis不支持键模式搜索
        # 这里只是一个示例，实际实现可能需要另外的跟踪机制
        return {"message": "统计功能未实现"}


class AIResultReceiveView(APIView):
    """
    接收AI服务发送的分析结果，保存为告警记录，并实时推送到前端。
    POST /alerts/ai-results/
    
    新增：集成告警限流功能，避免短时间内产生过多相同类型的告警
    """
    permission_classes = []
    authentication_classes = []
    
    # 告警限流时间（秒）
    ALERT_THROTTLE_SECONDS = 10

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
        """处理AI服务发送的分析结果，并应用告警限流机制"""
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
                
                # 应用告警限流逻辑
                camera_id = data['camera_id']
                event_type = data['event_type']
                
                should_throttle, count = AlertThrottleManager.should_throttle(
                    camera_id=camera_id,
                    event_type=event_type,
                    throttle_seconds=self.ALERT_THROTTLE_SECONDS
                )
                
                # 如果应该限流，则不创建新告警记录，但仍然通过WebSocket发送通知
                if should_throttle:
                    logger.info(
                        f"⏱️ 告警已限流: 摄像头={camera_id}, 类型={event_type}, "
                        f"在{self.ALERT_THROTTLE_SECONDS}秒内第{count}次触发"
                    )
                    
                    # 如果是第一次限流（count==2），发送一个通知
                    if count == 2:
                        try:
                            channel_layer = get_channel_layer()
                            if channel_layer:
                                # 发送限流通知给前端
                                throttle_message = {
                                    "type": "throttled_alert",
                                    "camera_id": camera_id,
                                    "event_type": event_type,
                                    "throttle_seconds": self.ALERT_THROTTLE_SECONDS,
                                    "count": count,
                                    "message": f"相同类型告警在{self.ALERT_THROTTLE_SECONDS}秒内多次触发，已限流",
                                    "timestamp": timezone.now().isoformat()
                                }
                                
                                # 【修复】发送到正确的摄像头组
                                group_name = f"camera_{camera_id}"
                                async_to_sync(channel_layer.group_send)(
                                    group_name,
                                    {
                                        "type": "throttled_alert",
                                        "message": throttle_message
                                    }
                                )
                        except Exception as e:
                            logger.error(f"发送告警限流通知时出错: {e}")
                    
                    # 仍然发送最新的检测结果到WebSocket（但不创建告警记录）
                    try:
                        channel_layer = get_channel_layer()
                        if channel_layer:
                            # 修改消息类型，表明这是被限流的检测结果
                            detection_data = data.copy()
                            detection_data["is_throttled"] = True
                            detection_data["throttle_count"] = count
                            
                            # 【修复】发送到正确的摄像头组
                            group_name = f"camera_{camera_id}"
                            async_to_sync(channel_layer.group_send)(
                                group_name,
                                {
                                    "type": "detection_result",
                                    "message": {
                                        "type": "detection_result",
                                        "data": detection_data
                                    }
                                }
                            )
                    except Exception as e:
                        logger.error(f"发送限流后的检测结果时出错: {e}")
                    
                    # 返回自定义响应，表明告警已被限流
                    return Response({
                        "status": "throttled",
                        "message": f"Alert throttled: {count} similar alerts in {self.ALERT_THROTTLE_SECONDS} seconds",
                        "event_type": event_type,
                        "camera_id": camera_id
                    }, status=status.HTTP_200_OK)
                
                # 未被限流，正常创建告警记录
                alert = serializer.save()

                try:
                    # 发送WebSocket通知
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        # 【修复】使用 serializer.validated_data 替代 AlertDetailSerializer(alert).data
                        # 因为前者包含AI服务发来的完整原始数据（包括坐标等 details），而后者可能会丢失字段
                        alert_data_for_ws = serializer.validated_data
                        # 手动将部分字段转换为字符串以确保JSON序列化成功
                        alert_data_for_ws['timestamp'] = alert.timestamp.isoformat()
                        
                        # 【修复】发送到正确的摄像头组
                        group_name = f"camera_{alert.camera_id}"
                        async_to_sync(channel_layer.group_send)(
                            group_name,
                            {
                                "type": "new_alert", # 注意这里是 new_alert
                                "message": {
                                    "action": "new_alert",
                                    "alert": alert_data_for_ws
                                }
                            }
                        )
                        logger.info(f"✅ 新告警 {alert.id} 已通过WebSocket推送到前端 (Group: {group_name})。")
                except Exception as e:
                    logger.error(f"发送WebSocket通知时发生严重错误: {e}", exc_info=True)

                return Response(
                    AlertDetailSerializer(alert).data, 
                    status=status.HTTP_201_CREATED
                )
            else:
                logger.error(f"AI结果序列化失败: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except json.JSONDecodeError:
            return Response(
                {"error": "Invalid JSON format"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"处理AI结果时发生未知错误: {e}", exc_info=True)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WebSocketBroadcastView(APIView):
    """
    WebSocket广播接口，用于向前端推送实时检测数据
    POST /alerts/websocket/broadcast/
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        """
        接收来自AI服务的实时检测数据并将其广播到WebSocket频道组。
        """
        # 验证API密钥
        api_key = request.headers.get('X-API-Key')
        valid_api_key = os.getenv('AI_SERVICE_API_KEY', 'smarteye-ai-service-key-2024')
        if not api_key or api_key != valid_api_key:
            return Response(
                {"error": "Invalid or missing API key"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 获取请求数据
        data = request.data
        
        # 【修复】从请求数据中获取camera_id来确定目标组
        camera_id = data.get("camera_id")
        if not camera_id:
            return Response({"error": "camera_id is required for broadcast"}, status=status.HTTP_400_BAD_REQUEST)
        
        group_name = f"camera_{camera_id}"
        message_type = data.get("type", "unknown_broadcast")
        logger.info(f"📡 收到定向WebSocket广播请求: Group={group_name}, Type={message_type}")

        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                # 【修复】使用与Consumer匹配的事件类型
                event_type = "detection_result" # 默认为检测结果
                if message_type == "stream_initialized":
                    event_type = "stream_initialized"
                elif message_type == "new_alert":
                    event_type = "new_alert"
                elif message_type == "alert_update":
                    event_type = "alert_update"
                elif message_type == "throttled_alert":
                    event_type = "throttled_alert"
                
                # 【关键修复】确保message以单独的键存在，而不是直接传递整个数据对象
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": event_type,
                        "message": data  # 发送完整的数据包作为message
                    }
                )
                logger.info(f"✅ WebSocket消息已定向广播到 {group_name}: {message_type}")
                return Response(
                    {"status": "broadcasted", "group": group_name, "type": message_type},
                    status=status.HTTP_200_OK
                )
            else:
                logger.error("❌ Channel layer 未正确配置，无法广播。")
                return Response(
                    {"error": "Server not configured for WebSocket broadcast"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            logger.error(f"❌ 广播WebSocket消息时发生错误: {e}", exc_info=True)
            return Response(
                {"error": f"Failed to broadcast message: {str(e)}"},
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