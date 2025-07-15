# backend/smart_station/asgi.py

import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
from django.urls import path
import alerts.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_station.settings')

# application = get_asgi_application() # 旧的ASGI应用

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                alerts.routing.websocket_urlpatterns
            )
        )
    ),
})