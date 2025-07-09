from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Swagger 相关导入
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.authentication import JWTAuthentication

def redirect_to_docs(request):
    return redirect('/swagger/')

# Swagger schema 配置
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
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # 👇 根路径跳转到 swagger 页面
    path('', redirect_to_docs),

    path('admin/', admin.site.urls),

    # JWT 登录认证 - 使用自定义的验证码登录视图
    # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  # 注释掉原来的
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # 保留刷新token

    # 模块路由
    path('api/users/', include('users.urls')),
    path('api/alerts/', include('alerts.urls')),
    path('api/cameras/', include('camera_management.urls')),
    path('api/reports/', include('ai_reports.urls')),
    path('api/data-analysis/', include('data_analysis.urls')),

    # Swagger 文档
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]


urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# 仅在 DEBUG 模式下生效
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

