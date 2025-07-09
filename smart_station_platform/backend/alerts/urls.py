# smart_station_platform/backend/alerts/urls.py

from django.urls import path
from .views import AlertListView, AIResultReceiveView, AlertUpdateView, AlertTestView

urlpatterns = [
    path('list/', AlertListView.as_view(), name='alert-list'),
    path('ai-results/', AIResultReceiveView.as_view(), name='ai-results'),
    path('update/<int:pk>/', AlertUpdateView.as_view(), name='alert-update'),
    path('test/', AlertTestView.as_view(), name='alert-test'),  # 新增测试路由
]