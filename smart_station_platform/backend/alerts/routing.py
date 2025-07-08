# G:\Web\smart_station_platform\backend\alerts\routing.py

from django.urls import re_path
from . import consumers # 导入 alerts 应用的 consumers 模块

# 定义 WebSocket URL 模式列表
websocket_urlpatterns = [
    re_path(r'ws/alerts/$', consumers.AlertConsumer.as_asgi()), # WebSocket 连接到 /ws/alerts/ 路径时，由 AlertConsumer 处理
]