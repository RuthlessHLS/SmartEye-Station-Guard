import uuid
import time
from django.core.cache import cache
from django.shortcuts import render
from .models import UserProfile
from .serializers import (
    UserRegisterSerializer,
    UserProfileSerializer,
    AvatarUpdateSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)
from rest_framework import generics, permissions, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.mail import send_mail
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import MyTokenObtainPairSerializer
from .captcha_generator import create_captcha_images


# ==========================================================
# 视图 1: UserRegisterView
# ==========================================================
class UserRegisterView(generics.CreateAPIView):
    """
    用户注册API视图
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]


# ==========================================================
# 视图 2: UserProfileView
# ==========================================================
class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    用户个人资料API视图
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ==========================================================
# 视图 3: AvatarUpdateView
# ==========================================================
class AvatarUpdateView(generics.UpdateAPIView):
    """
    用户头像上传API视图
    """
    queryset = UserProfile.objects.all()
    serializer_class = AvatarUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        return self.request.user


# ==========================================================
# 视图 4: PasswordResetRequestView
# ==========================================================
class PasswordResetRequestView(APIView):
    """
    请求密码重置的视图
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = UserProfile.objects.get(email=email)

        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(user)
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

        # [注意] 这里的域名需要换成你的前端应用的实际地址
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uidb64}/{token}/"

        send_mail(
            '您的密码重置请求',
            f'你好， {user.username}，\n\n请点击以下链接以重置您的密码：\n{reset_link}\n\n如果您没有请求此操作，请忽略此邮件。\n\n谢谢！',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )

        return Response({"message": "密码重置链接已发送到您的邮箱。"}, status=status.HTTP_200_OK)


# ==========================================================
# 视图 5: PasswordResetConfirmView
# ==========================================================
class PasswordResetConfirmView(APIView):
    """
    确认密码重置的视图
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        uidb64 = serializer.validated_data['uidb64']
        token = serializer.validated_data['token']
        password = serializer.validated_data['password']

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = UserProfile.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, UserProfile.DoesNotExist):
            user = None

        token_generator = PasswordResetTokenGenerator()
        if user is not None and token_generator.check_token(user, token):
            user.set_password(password)
            user.save()
            return Response({"message": "密码重置成功！"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "密码重置链接无效或已过期。"}, status=status.HTTP_400_BAD_REQUEST)


# ==========================================================
# 视图 6: GenerateCaptchaView
# ==========================================================
class GenerateCaptchaView(APIView):
    """
    生成滑动验证码的视图。
    调用辅助函数生成图片，并处理HTTP请求和响应。
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        # 1. 调用辅助函数生成图片数据
        image_data = create_captcha_images()

        # 2. 生成唯一的 key 并将正确答案存入缓存
        captcha_key = str(uuid.uuid4())
        # 我们将一个字典存入缓存，而不是单个值
        cache_data = {
            'position': image_data['position_x'],
            'timestamp': time.time()  # 记录当前时间的 Unix 时间戳
        }
        # 将 x 坐标作为答案存入缓存，有效期 5 分钟 (300秒)
        cache.set(f"captcha:{captcha_key}", image_data['position_x'], timeout=300)

        # 3. 准备返回给前端的数据
        response_data = {
            "captcha_key": captcha_key,
            "background_image": f"data:image/png;base64,{image_data['background_base64']}",
            "slider_image": f"data:image/png;base64,{image_data['slider_base64']}",
            "slider_y": image_data['position_y']  # 滑块的 y 坐标，用于前端定位
        }

        return Response(response_data, status=status.HTTP_200_OK)


# ==========================================================
# 视图: MyTokenObtainPairView
# ==========================================================
class MyTokenObtainPairView(TokenObtainPairView):
    """
    自定义的Token获取视图，使用我们自己的序列化器
    """
    serializer_class = MyTokenObtainPairSerializer