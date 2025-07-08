# backend/alerts/urls.py

from django.urls import path
from .views import AIResultReceiveView, AlertListView, AlertUpdateView

urlpatterns = [
    path('ai-results/', AIResultReceiveView.as_view(), name='ai-result-receive'),
    path('list/', AlertListView.as_view(), name='alert-list'),

    # 你的前端代码会请求类似 /api/alerts/123/update/ 的地址
    # 我们用一个视图同时处理 handle 和 update 的逻辑
    path('<int:pk>/update/', AlertUpdateView.as_view(), name='alert-update'),
    path('<int:pk>/handle/', AlertUpdateView.as_view(), name='alert-handle'),  # 为了兼容两种可能的请求
]