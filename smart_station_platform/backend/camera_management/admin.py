from django.contrib import admin
from .models import Camera, DangerousArea


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    """摄像头管理界面配置"""
    list_display = ['name', 'location_desc', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['name', 'location_desc']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'rtsp_url', 'location_desc')
        }),
        ('状态管理', {
            'fields': ('is_active',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DangerousArea)
class DangerousAreaAdmin(admin.ModelAdmin):
    """危险区域管理界面配置"""
    list_display = ['name', 'camera', 'is_active', 'min_distance_threshold', 'time_in_area_threshold', 'created_at']
    list_filter = ['is_active', 'camera', 'created_at']
    search_fields = ['name', 'camera__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['camera', 'name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('camera', 'name')
        }),
        ('区域配置', {
            'fields': ('coordinates', 'min_distance_threshold', 'time_in_area_threshold')
        }),
        ('状态管理', {
            'fields': ('is_active',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """优化查询，预加载摄像头信息"""
        return super().get_queryset(request).select_related('camera')
