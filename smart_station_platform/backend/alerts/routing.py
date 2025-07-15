# backend/alerts/routing.py

from django.urls import re_path # 从 Django 的 urls 模块导入 re_path，用于正则表达式匹配
from . import consumers # 导入当前应用下的 consumers 模块，假设您的 WebSocket 处理逻辑（消费者）在里面

websocket_urlpatterns = [
    # 【最终修复】使用包含完整路径的、不带开头锚点'^'的正则表达式，以确保匹配成功
    re_path(r'ws/alerts/(?P<camera_id>[^/]+)/?$', consumers.AlertConsumer.as_asgi()),
]