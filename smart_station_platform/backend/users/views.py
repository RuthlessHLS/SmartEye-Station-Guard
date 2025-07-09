import uuid
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
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from django.core.cache import cache
import uuid
import base64
from io import BytesIO
from PIL import Image, ImageDraw
import random


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


# 验证码生成接口
@api_view(['GET'])
@permission_classes([AllowAny])
def generate_captcha(request):
    """生成滑动验证码"""
    try:
        # 生成验证码背景图和滑块图
        width, height = 280, 150
        slider_size = 40
        
        # 创建背景图
        background = Image.new('RGB', (width, height), color=(200, 220, 240))
        draw = ImageDraw.Draw(background)
        
        # 添加一些随机干扰线
        for _ in range(5):
            x1, y1 = random.randint(0, width), random.randint(0, height)
            x2, y2 = random.randint(0, width), random.randint(0, height)
            draw.line([x1, y1, x2, y2], fill=(100, 150, 200), width=2)
        
        # 随机生成滑块位置
        slider_x = random.randint(slider_size + 10, width - slider_size - 10)
        slider_y = random.randint(10, height - slider_size - 10)
        
        # 创建滑块图案（简单的拼图形状）
        slider = Image.new('RGBA', (slider_size, slider_size), color=(0, 0, 0, 0))
        slider_draw = ImageDraw.Draw(slider)
        
        # 绘制滑块形状
        slider_draw.rectangle([0, 0, slider_size-1, slider_size-1], 
                             fill=(150, 180, 220, 255), outline=(100, 130, 170, 255), width=2)
        
        # 在背景图上挖出滑块位置
        background_copy = background.copy()
        background_copy.paste(slider, (slider_x, slider_y), slider)
        
        # 转换为base64
        def image_to_base64(img):
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode()
        
        background_b64 = f"data:image/png;base64,{image_to_base64(background_copy)}"
        slider_b64 = f"data:image/png;base64,{image_to_base64(slider)}"
        
        # 生成验证码key并存储正确位置
        captcha_key = str(uuid.uuid4())
        cache.set(f"captcha_{captcha_key}", slider_x, timeout=300)  # 5分钟过期
        
        return Response({
            'captcha_key': captcha_key,
            'background_image': background_b64,
            'slider_image': slider_b64,
            'slider_y': slider_y,
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 自定义登录视图，包含验证码验证
class CustomTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')
        captcha_key = request.data.get('captcha_key')
        captcha_position = request.data.get('captcha_position')
        
        # 验证用户名密码
        if not username or not password:
            return Response({'detail': '用户名和密码不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 验证验证码
        if captcha_key and captcha_position is not None:
            correct_position = cache.get(f"captcha_{captcha_key}")
            if correct_position is None:
                return Response({'detail': '验证码已过期，请重新获取'}, status=status.HTTP_400_BAD_REQUEST)
            
            # 允许一定的误差范围（+-10像素）
            position_diff = abs(float(captcha_position) - correct_position)
            if position_diff > 10:
                return Response({'detail': '验证码验证失败'}, status=status.HTTP_400_BAD_REQUEST)
            
            # 验证成功后删除验证码
            cache.delete(f"captcha_{captcha_key}")
        
        # 验证用户身份
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({'detail': '用户名或密码错误'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not user.is_active:
            return Response({'detail': '用户账户已被禁用'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # 调用父类方法生成token
        return super().post(request, *args, **kwargs)