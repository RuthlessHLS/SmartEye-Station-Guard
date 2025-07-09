# G:\Web\smart_station_platform\backend\users\urls.py

from django.urls import path
from . import views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    # 用户注册
    path('register/', views.UserRegisterView.as_view(), name='register'),

    # 用户个人资料 (获取和更新)
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),

    # 用户头像上传路由
    # 使用 PATCH 或 PUT 请求到这个 URL
    path('profile/avatar/', views.AvatarUpdateView.as_view(), name='user_avatar_update'),

    # JWT Token 相关路由
    # 'token/' 用于登录，用户提交 username 和 password，成功后返回 access 和 refresh tokens
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),

    # 'token/refresh/' 用于刷新 access token
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 密码重置相关路由
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]