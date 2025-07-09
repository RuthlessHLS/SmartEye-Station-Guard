# G:\Web\smart_station_platform\backend\camera_management\urls.py (或 ai_reports/urls.py, data_analysis/urls.py)

from django.urls import path
from . import views

urlpatterns = [
    # your specific urls for this app
]



from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# 创建路由器
router = DefaultRouter()
router.register(r'cameras', views.CameraViewSet, basename='camera')
router.register(r'dangerous-areas', views.DangerousAreaViewSet, basename='dangerous-area')

urlpatterns = [
    # 包含路由器生成的URL
    path('', include(router.urls)),
]