# smart_station_platform/backend/alerts/urls.py

from django.urls import path
from .views import (
    AlertListView, 
    AlertDetailView,
    AlertHandleView,
    AlertUpdateView,
    AIResultReceiveView, 
    AlertStatsView,

    AlertLogListView,  # 新增

    WebSocketBroadcastView

)

urlpatterns = [
    # 图片中显示的API接口
    path('', AlertListView.as_view(), name='alerts-list-root'),
    path('ai-results/', AIResultReceiveView.as_view(), name='alerts_ai_results_create'),  # POST
    path('list/', AlertListView.as_view(), name='alerts_list_list'),  # GET
    path('<int:pk>/handle/', AlertHandleView.as_view(), name='alerts_handle_update'),  # PUT/PATCH
    path('<int:pk>/update/', AlertUpdateView.as_view(), name='alerts_update_update'),  # PUT/PATCH
    
    # 额外的实用接口
    path('<int:pk>/', AlertDetailView.as_view(), name='alert-detail'),  # GET 获取详情
    path('stats/', AlertStatsView.as_view(), name='alert-stats'),  # GET 获取统计信息
    

    path('<int:alert_id>/logs/', AlertLogListView.as_view(), name='alert-logs'),  # 新增

    
    # WebSocket广播接口
    path('websocket/broadcast/', WebSocketBroadcastView.as_view(), name='websocket-broadcast'),  # POST

]