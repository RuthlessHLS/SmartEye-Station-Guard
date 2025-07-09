# smart_station_platform/backend/alerts/urls.py

from django.urls import path
from .views import AlertListView, AIResultReceiveView, AlertUpdateView, AlertTestView

urlpatterns = [
    path('', AlertListView.as_view(), name='alert-list'),  # 根路径指向列表视图
    path('list/', AlertListView.as_view(), name='alert-list-alt'),  # 保留备用路径
    path('ai-results/', AIResultReceiveView.as_view(), name='ai-results'),
    path('<int:pk>/update/', AlertUpdateView.as_view(), name='alert-update'),  # 修正路径
    path('<int:pk>/handle/', AlertUpdateView.as_view(), name='alert-handle'),  # 添加处理路径
    path('test/', AlertTestView.as_view(), name='alert-test'),  # 测试路由
]