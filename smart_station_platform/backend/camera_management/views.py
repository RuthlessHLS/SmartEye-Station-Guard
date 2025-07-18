from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import AuthenticationFailed
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.views import APIView
from django.http import HttpResponse
from django.conf import settings
import os
import re
import datetime
import logging

logger = logging.getLogger(__name__)


from .models import Camera, DangerousArea
from .serializers import (
    CameraSerializer, CameraDetailSerializer,
    DangerousAreaSerializer, DangerousAreaCreateSerializer
)


class CameraViewSet(viewsets.ModelViewSet):
    """
    摄像头管理视图集
    提供摄像头的增删改查功能
    """
    queryset = Camera.objects.all()
    serializer_class = CameraSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """根据操作类型返回不同的序列化器"""
        if self.action == 'retrieve':
            return CameraDetailSerializer
        return CameraSerializer
    
    def get_queryset(self):
        """支持按名称、位置描述和状态筛选"""
        queryset = Camera.objects.all()
        
        # 搜索参数
        name = self.request.query_params.get('name', None)
        location = self.request.query_params.get('location', None)
        is_active = self.request.query_params.get('is_active', None)
        
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        if location:
            queryset = queryset.filter(location_desc__icontains=location)
        
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """切换摄像头启用状态"""
        camera = self.get_object()
        camera.is_active = not camera.is_active
        camera.save()
        
        return Response({
            'id': camera.id,
            'name': camera.name,
            'is_active': camera.is_active,
            'message': f'摄像头 {camera.name} 已{"启用" if camera.is_active else "禁用"}'
        })
    
    @action(detail=False, methods=['get'])
    def active_cameras(self, request):
        """获取所有启用的摄像头"""
        cameras = Camera.objects.filter(is_active=True)
        serializer = self.get_serializer(cameras, many=True)
        return Response(serializer.data)


class DangerousAreaViewSet(viewsets.ModelViewSet):
    """
    危险区域管理视图集
    提供危险区域的增删改查功能
    """
    queryset = DangerousArea.objects.all()
    serializer_class = DangerousAreaSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """根据操作类型返回不同的序列化器"""
        if self.action == 'create':
            return DangerousAreaCreateSerializer
        return DangerousAreaSerializer
    
    def get_queryset(self):
        """支持按摄像头、区域名称和状态筛选"""
        queryset = DangerousArea.objects.select_related('camera')
        
        # 筛选参数
        camera_id = self.request.query_params.get('camera_id', None)
        name = self.request.query_params.get('name', None)
        is_active = self.request.query_params.get('is_active', None)
        
        if camera_id:
            # 支持数字ID和字符串名称
            if camera_id.isdigit():
                queryset = queryset.filter(camera_id=camera_id)
            else:
                queryset = queryset.filter(camera__name=camera_id)
        
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """创建危险区域"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # 增强坐标验证
            coordinates = serializer.validated_data.get('coordinates')
            if len(coordinates) < 3 or not all(len(point) == 2 for point in coordinates):
                return Response({'error': '坐标需要至少3个二维点'}, status=status.HTTP_400_BAD_REQUEST)

            # 检查区域名称重复
            camera_id = serializer.validated_data['camera'].id
            name = serializer.validated_data['name']
            if DangerousArea.objects.filter(camera_id=camera_id, name=name).exists():
                return Response({
                    'error': f'摄像头下已存在名为 "{name}" 的危险区域',
                    'code': 'duplicate_name'
                }, status=status.HTTP_400_BAD_REQUEST)

            self.perform_create(serializer)
            return Response({
                'data': serializer.data,
                'warning': '保存后需要5-10分钟生效'
            }, status=status.HTTP_201_CREATED)

        except AuthenticationFailed as e:
            return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f'危险区域创建失败: {str(e)}', exc_info=True)
            return Response({'error': f'服务器内部错误: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def update(self, request, *args, **kwargs):
        """更新危险区域"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # 检查名称重复（排除当前实例）
        camera_id = serializer.validated_data.get('camera', instance.camera).id
        name = serializer.validated_data.get('name', instance.name)
        
        if DangerousArea.objects.filter(
            camera_id=camera_id, 
            name=name
        ).exclude(id=instance.id).exists():
            return Response({
                'error': f'摄像头下已存在名为 "{name}" 的危险区域'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_update(serializer)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """切换危险区域启用状态"""
        area = self.get_object()
        area.is_active = not area.is_active
        area.save()
        
        return Response({
            'id': area.id,
            'name': area.name,
            'camera_name': area.camera.name,
            'is_active': area.is_active,
            'message': f'危险区域 {area.name} 已{"启用" if area.is_active else "禁用"}'
        })
    
    @action(detail=False, methods=['get'])
    def by_camera(self, request):
        """获取指定摄像头的所有危险区域"""
        camera_id = request.query_params.get('camera_id')
        if not camera_id:
            return Response({
                'error': '请提供 camera_id 参数'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 尝试通过ID查找摄像头
            if camera_id.isdigit():
                areas = DangerousArea.objects.filter(camera_id=camera_id)
            else:
                # 如果是字符串格式，尝试通过名称查找摄像头
                camera = Camera.objects.filter(name=camera_id).first()
                if camera:
                    areas = DangerousArea.objects.filter(camera=camera)
                else:
                    # 如果找不到摄像头，返回空列表
                    areas = DangerousArea.objects.none()

            serializer = self.get_serializer(areas, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({
                'error': f'获取危险区域失败: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def active_areas(self, request):
        """获取所有启用的危险区域"""
        areas = DangerousArea.objects.filter(is_active=True).select_related('camera')
        serializer = self.get_serializer(areas, many=True)
        return Response(serializer.data)


class PlaybackView(APIView):
    """根据摄像头、起始时间和时长动态生成 HLS m3u8 播放列表。\n\n    请求参数:\n        camera_id: 摄像头 ID (必填)\n        start:     ISO8601 起始时间，例如 2025-07-17T10:00:00 (必填)\n        duration:  回放时长，单位秒，默认 60，最大 300 (可选)\n    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        camera_id = request.query_params.get("camera_id")
        start_str = request.query_params.get("start")
        duration = int(request.query_params.get("duration", "60"))

        # 参数校验
        if not camera_id or not start_str:
            return Response({"error": "camera_id 和 start 参数必填"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            start_dt = datetime.datetime.fromisoformat(start_str)
        except ValueError:
            return Response({"error": "start 参数格式不正确，需 ISO8601"}, status=status.HTTP_400_BAD_REQUEST)

        # 限制最大回放时长
        max_duration = int(getattr(settings, "HLS_PLAYBACK_MAX_DURATION", 300))
        duration = max(10, min(duration, max_duration))
        end_dt = start_dt + datetime.timedelta(seconds=duration)

        # 查找切片文件
        base_dir = getattr(settings, "HLS_ARCHIVE_BASE_DIR", "/data/hls/archive")
        url_prefix = getattr(settings, "HLS_ARCHIVE_URL_PREFIX", "/archive")
        segment_duration = int(getattr(settings, "HLS_SEGMENT_DURATION", 10))

        pattern = re.compile(rf"camera_{camera_id}_(\d{{14}})\.ts$")
        segments = []  # (timestamp, abs_path)

        for root, _, files in os.walk(base_dir):
            for fname in files:
                match = pattern.match(fname)
                if not match:
                    continue
                ts_str = match.group(1)
                try:
                    ts_dt = datetime.datetime.strptime(ts_str, "%Y%m%d%H%M%S")
                except ValueError:
                    continue
                if start_dt <= ts_dt < end_dt:
                    segments.append((ts_dt, os.path.join(root, fname)))

        if not segments:
            return Response({"error": "未找到对应时间段的切片"}, status=status.HTTP_404_NOT_FOUND)

        # 按时间排序
        segments.sort(key=lambda x: x[0])

        # 生成 m3u8 内容
        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            f"#EXT-X-TARGETDURATION:{segment_duration}",
            "#EXT-X-MEDIA-SEQUENCE:0",
        ]

        for _ts, abs_path in segments:
            rel_path = os.path.relpath(abs_path, base_dir).replace(os.sep, "/")
            lines.append(f"#EXTINF:{segment_duration}.0,")
            lines.append(f"{url_prefix}/{rel_path}")

        lines.append("#EXT-X-ENDLIST")
        m3u8_content = "\n".join(lines)

        return HttpResponse(m3u8_content, content_type="application/vnd.apple.mpegurl")