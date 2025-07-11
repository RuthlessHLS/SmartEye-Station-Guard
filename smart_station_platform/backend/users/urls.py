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
]