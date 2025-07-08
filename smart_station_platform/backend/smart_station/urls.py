# G:\Web\smart_station_platform\backend\smart_station\urls.py

from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,    # 用于获取JWT Token
    TokenRefreshView,       # 用于刷新JWT Token
)

# [cite_start]Swagger UI 相关的导入 [cite: 70, 110]
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# [cite_start]Swagger API 文档 schema 配置 [cite: 70, 110]
schema_view = get_schema_view(
   openapi.Info(
      title="智慧车站智能监控与大数据分析平台 API",
      default_version='v1',
      description="项目的API接口文档",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@yourproject.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,), # 允许任何人访问API文档页面
)

urlpatterns = [
    path('admin/', admin.site.urls), # Django 管理后台

    # [cite_start]JWT 认证相关的 API 路由 [cite: 78, 80]
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),       # 登录获取 Token
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),     # 刷新 Token

    # 应用 API 路由 (将各个 app 的 urls 包含进来)
    path('api/users/', include('users.urls')),               # 用户管理模块
    path('api/alerts/', include('alerts.urls')),             # 告警与报告模块
    path('api/cameras/', include('camera_management.urls')), # 摄像头与危险区域管理模块
    path('api/reports/', include('ai_reports.urls')),       # AI日报模块
    path('api/data-analysis/', include('data_analysis.urls')), # 数据大屏分析模块

    # [cite_start]Swagger API 文档路由 [cite: 70, 110]
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'), # Swagger UI 界面
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),     # Redoc UI 界面
]