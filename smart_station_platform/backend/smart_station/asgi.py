# backend/smart_station/asgi.py

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack # 暂时使用这个，如果登录有问题再换
import alerts.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_station.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            alerts.routing.websocket_urlpatterns
        )
    ),
})