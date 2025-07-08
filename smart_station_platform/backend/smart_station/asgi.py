# G:\Web\smart_station_platform\backend\smart_station\asgi.py

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_station.settings')

# 获取 Django 的 ASGI 应用实例，用于处理 HTTP 请求
django_asgi_app = get_asgi_application()

# 导入 alerts 应用的 routing 模块，其中定义了 WebSocket URL 模式
import alerts.routing

# 定义主 ASGI 应用程序，根据协议类型路由请求
application = ProtocolTypeRouter({
    "http": django_asgi_app, # HTTP 请求路由到 Django 的 ASGI 应用
    "websocket": AllowedHostsOriginValidator( # WebSocket 请求
        AuthMiddlewareStack( # 添加认证中间件，可以解析用户认证信息
            URLRouter( # 路由 WebSocket URL 模式
                alerts.routing.websocket_urlpatterns # 导入 alerts 应用的 WebSocket URL 模式
            )
        )
    ),
})