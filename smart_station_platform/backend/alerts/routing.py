# backend/alerts/routing.py

from django.urls import re_path # 从 Django 的 urls 模块导入 re_path，用于正则表达式匹配
from . import consumers # 导入当前应用下的 consumers 模块，假设您的 WebSocket 处理逻辑（消费者）在里面

websocket_urlpatterns = [
    # 修改后的路由规则：
    # r'ws/alerts/(?P<camera_id>\w+)/$'
    # - (?P<camera_id>...)：捕获括号内的内容，并将其命名为 "camera_id"。
    # - \w+：匹配一个或多个“单词字符”（包括字母、数字和下划线）。
    #   您的前端生成的摄像头ID (例如 camera_1752413399221) 包含字母、数字和下划线，符合 \w+ 的匹配规则。
    re_path(r'ws/alerts/(?P<camera_id>\w+)/$', consumers.AlertConsumer.as_asgi()),
]