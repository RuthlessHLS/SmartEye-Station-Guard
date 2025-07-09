# G:\Web\smart_station_platform\backend\users\urls.py

from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # 生成验证码的路由
    path('captcha/generate/', views.GenerateCaptchaView.as_view(), name='captcha_generate'),

    # 用户注册
    path('register/', views.UserRegisterView.as_view(), name='register'),

    # 用户个人资料 (获取和更新)
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),

    # 用户头像上传路由
    # 使用 PATCH 或 PUT 请求到这个 URL
    path('profile/avatar/', views.AvatarUpdateView.as_view(), name='user_avatar_update'),

    # JWT Token 相关路由
    # 使用我们自定义的视图来处理登录请求
    path('token/', views.MyTokenObtainPairView.as_view(), name='token_obtain_pair'),

    # 'token/refresh/' 用于刷新 access token
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 密码重置相关路由
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]