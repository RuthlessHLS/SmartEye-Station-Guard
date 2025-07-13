# backend/alerts/routing.py

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/alerts/$', consumers.AlertConsumer.as_asgi()),
    re_path(r'ws/alerts/(?P<camera_id>[^/]+)/$', consumers.AlertConsumer.as_asgi()),
]