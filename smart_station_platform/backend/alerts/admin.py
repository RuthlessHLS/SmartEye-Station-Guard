# smart_station_platform/backend/alerts/admin.py

from django.contrib import admin
from .models import Alert

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('id', 'camera', 'event_type', 'timestamp', 'status', 'handler', 'confidence', 'created_at')
    list_filter = ('event_type', 'status', 'timestamp', 'camera')
    search_fields = ('event_type', 'processing_notes', 'camera__name') # 允许按摄像头名称搜索
    raw_id_fields = ('camera', 'handler') # 对于外键字段，使用原始ID输入框，避免下拉列表过长
    date_hierarchy = 'timestamp' # 添加日期导航
    readonly_fields = ('created_at', 'updated_at', 'timestamp') # 这些字段在Admin界面只读

    fieldsets = (
        (None, {
            'fields': ('camera', 'event_type', 'timestamp', 'location', 'confidence')
        }),
        ('媒体信息', {
            'fields': ('image_snapshot_url', 'video_clip_url'),
            'classes': ('collapse',) # 可折叠
        }),
        ('处理信息', {
            'fields': ('status', 'handler', 'processing_notes'),
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )