# G:\Web\smart_station_platform\backend\users\urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserLoginAPIView,
    UserRegisterAPIView,
    UserProfileAPIView,
    ChangePasswordAPIView,
    UpdateAvatarAPIView,
    PasswordResetRequestAPIView,
    PasswordResetConfirmAPIView,
    UsersDirectoryViewSet,
    CaptchaAPIView,
    FaceDataViewSet,
    RegisteredFaceViewSet
)

router = DefaultRouter()
router.register(r'directory', UsersDirectoryViewSet, basename='user-directory')
router.register(r'faces', FaceDataViewSet, basename='face-data')
router.register(r'registered-faces', RegisteredFaceViewSet, basename='registered-face')

urlpatterns = [
    path('login/', UserLoginAPIView.as_view(), name='user-login'),
    path('token/', UserLoginAPIView.as_view(), name='token-obtain'),
    path('register/', UserRegisterAPIView.as_view(), name='user-register'),
    path('profile/', UserProfileAPIView.as_view(), name='user-profile'),
    path('change-password/', ChangePasswordAPIView.as_view(), name='change-password'),
    path('update-avatar/', UpdateAvatarAPIView.as_view(), name='update-avatar'),
    path('reset-password/', PasswordResetRequestAPIView.as_view(), name='reset-password-request'),
    path('reset-password-confirm/', PasswordResetConfirmAPIView.as_view(), name='reset-password-confirm'),
    path('captcha/', CaptchaAPIView.as_view(), name='captcha'),
    path('captcha/generate/', CaptchaAPIView.as_view(), name='captcha-generate'),
    path('', include(router.urls)),



    # 生成验证码的路由
    path('captcha/generate/', views.GenerateCaptchaView.as_view(), name='captcha_generate'),

    # 用户注册
    path('register/', views.UserRegisterView.as_view(), name='register'),

    # 用户个人资料 (获取和更新)
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),

    # 修改密码路由
    path('profile/change-password/', views.PasswordChangeView.as_view(), name='change_password'),

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