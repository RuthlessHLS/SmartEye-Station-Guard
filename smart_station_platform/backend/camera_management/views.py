from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q

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
            queryset = queryset.filter(camera_id=camera_id)
        
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """创建危险区域"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # 检查同一摄像头下区域名称是否重复
        camera_id = serializer.validated_data['camera'].id
        name = serializer.validated_data['name']
        
        if DangerousArea.objects.filter(camera_id=camera_id, name=name).exists():
            return Response({
                'error': f'摄像头下已存在名为 "{name}" 的危险区域'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
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
        
        areas = DangerousArea.objects.filter(camera_id=camera_id)
        serializer = self.get_serializer(areas, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active_areas(self, request):
        """获取所有启用的危险区域"""
        areas = DangerousArea.objects.filter(is_active=True).select_related('camera')
        serializer = self.get_serializer(areas, many=True)
        return Response(serializer.data)