# backend/alerts/routing.py

from django.urls import re_path # 从 Django 的 urls 模块导入 re_path，用于正则表达式匹配
from . import consumers # 导入当前应用下的 consumers 模块，假设您的 WebSocket 处理逻辑（消费者）在里面

websocket_urlpatterns = [
    # 【修复】恢复路径定义，以匹配前端 'ws/alerts/<camera_id>/' 格式的请求
    # (?P<camera_id>\w+) 会捕获路径中的摄像头ID字符串
    re_path(r'^ws/alerts/(?P<camera_id>\w+)/$', consumers.AlertConsumer.as_asgi()),
]