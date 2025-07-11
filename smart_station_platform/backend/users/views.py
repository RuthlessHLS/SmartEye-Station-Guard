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
    PasswordResetConfirmSerializer,
    UserAdminSerializer
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
from rest_framework import viewsets
from rest_framework import filters
from .serializers import UserDirectorySerializer

import json
import requests
import base64
from io import BytesIO
import numpy as np

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .serializers import (
    UserRegisterSerializer, 
    UserProfileSerializer, 
    FaceDataSerializer,
    RegisteredFaceSerializer
)
from .models import FaceData, RegisteredFace
from PIL import Image

User = get_user_model()

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
# 视图 1-1: UserRegisterAPIView (新增)
# ==========================================================
class UserRegisterAPIView(UserRegisterView):
    """
    用户注册API视图，继承自UserRegisterView
    """
    pass

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
# 视图 2-1: UserProfileAPIView (新增)
# ==========================================================
class UserProfileAPIView(UserProfileView):
    """
    用户个人资料API视图，继承自UserProfileView
    """
    pass

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
# 视图 3-1: UpdateAvatarAPIView (新增)
# ==========================================================
class UpdateAvatarAPIView(AvatarUpdateView):
    """
    用户头像上传API视图，继承自AvatarUpdateView
    """
    pass

# ==========================================================
# 视图 3-2: ChangePasswordAPIView (新增)
# ==========================================================
class ChangePasswordAPIView(APIView):
    """
    修改密码API视图
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        
        if not old_password or not new_password:
            return Response({"error": "请提供旧密码和新密码"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not user.check_password(old_password):
            return Response({"error": "旧密码不正确"}, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        user.save()
        return Response({"message": "密码修改成功"}, status=status.HTTP_200_OK)

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
# 视图 4-1: PasswordResetRequestAPIView (新增)
# ==========================================================
class PasswordResetRequestAPIView(PasswordResetRequestView):
    """
    请求密码重置的API视图，继承自PasswordResetRequestView
    """
    pass

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
# 视图 5-1: PasswordResetConfirmAPIView (新增)
# ==========================================================
class PasswordResetConfirmAPIView(PasswordResetConfirmView):
    """
    确认密码重置的API视图，继承自PasswordResetConfirmView
    """
    pass

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

        # 3. [修复] 将包含位置和时间戳的字典存入缓存

        cache_data = {
            'position': image_data['position_x'],
            'timestamp': time.time()  # 记录当前时间的 Unix 时间戳
        }

        # 将 x 坐标作为答案存入缓存，有效期 5 分钟 (300秒)
        cache.set(f"captcha:{captcha_key}", image_data['position_x'], timeout=300)

        # 3. 准备返回给前端的数据

        # 使用 cache_data 变量进行设置，有效期 5 分钟 (300秒)
        cache.set(f"captcha:{captcha_key}", cache_data, timeout=300)

        # 4. 准备返回给前端的数据

        response_data = {
            "captcha_key": captcha_key,
            "background_image": f"data:image/png;base64,{image_data['background_base64']}",
            "slider_image": f"data:image/png;base64,{image_data['slider_base64']}",
            "slider_y": image_data['position_y']  # 滑块的 y 坐标，用于前端定位
        }

        return Response(response_data, status=status.HTTP_200_OK)

# ==========================================================
# 视图 6-1: CaptchaAPIView (新增)
# ==========================================================
class CaptchaAPIView(GenerateCaptchaView):
    """
    验证码API视图，继承自GenerateCaptchaView
    """
    pass

# ==========================================================
# 视图7: MyTokenObtainPairView
# ==========================================================
class MyTokenObtainPairView(TokenObtainPairView):
    """
    自定义的Token获取视图，使用我们自己的序列化器
    """
    serializer_class = MyTokenObtainPairSerializer

# ==========================================================
# 视图7-1: UserLoginAPIView (新增)
# ==========================================================
class UserLoginAPIView(MyTokenObtainPairView):
    """
    用户登录API视图，继承自MyTokenObtainPairView
    """
    pass

# ==========================================================
# 视图 8: UserAdminViewSet
# ==========================================================
class UserAdminViewSet(viewsets.ModelViewSet):
    """
    供管理员使用的用户管理API。
    - 权限: 仅限管理员 (is_staff=True) 访问。
    - 支持: 列表、创建、检索、更新、删除用户。
    """
    queryset = UserProfile.objects.all().order_by('-date_joined')
    serializer_class = UserAdminSerializer
    permission_classes = [permissions.IsAdminUser] # <-- 核心权限控制！

# ==========================================================
# 视图 9: UserDirectoryViewSet
# ==========================================================
class UsersDirectoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    提供一个公开的用户目录（通讯录）。
    - 权限: 任何已认证的用户 (IsAuthenticated) 均可访问。
    - 功能:
        - 列表查看所有用户。
        - 详情查看单个用户。
        - 支持按用户名、昵称、手机号、邮箱进行搜索。
    - 操作: 只读 (ReadOnlyModelViewSet)，不允许创建、修改、删除。
    """
    queryset = UserProfile.objects.filter(is_active=True).order_by('username') # 只显示激活的用户
    serializer_class = UserDirectorySerializer
    permission_classes = [permissions.IsAuthenticated] # <-- 权限修改为：任何登录用户

    # --- 实现搜索功能 ---
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'nickname', 'phone_number', 'email']

class FaceDataViewSet(viewsets.ModelViewSet):
    """人脸数据视图集"""
    serializer_class = FaceDataSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """获取当前用户的人脸数据，管理员可以查看所有数据"""
        user = self.request.user
        if user.is_staff:
            return FaceData.objects.all()
        return FaceData.objects.filter(user=user)
    
    @action(detail=False, methods=['post'])
    def upload_face(self, request):
        """上传人脸图像并提取特征"""
        user = request.user
        face_image = request.FILES.get('face_image')
        note = request.data.get('note', '')
        
        if not face_image:
            return Response({"error": "请上传人脸图像"}, status=status.HTTP_400_BAD_REQUEST)
        
        # 将图像转换为base64以便传输给AI服务
        image_data = base64.b64encode(face_image.read()).decode('utf-8')
        
        # 调用AI服务进行人脸检测和特征提取
        ai_service_url = "http://localhost:8001/process_face"  # AI服务端点
        
        try:
            response = requests.post(
                ai_service_url,
                json={"image": image_data},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                return Response({"error": f"AI服务处理失败: HTTP {response.status_code}"}, 
                              status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            result = response.json()
            
            if not result.get('success', False):
                return Response({"error": result.get('message', '未检测到有效人脸')}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            # 重置文件指针以便保存图像
            face_image.seek(0)
            
            # 创建人脸数据记录
            face_data = FaceData(
                user=user,
                face_image=face_image,
                note=note,
            )
            
            # 保存人脸编码
            face_data.set_face_encoding(result.get('face_encoding'))
            face_data.save()
            
            serializer = self.get_serializer(face_data)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({"error": f"处理人脸数据时出错: {str(e)}"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def verify_face(self, request):
        """验证人脸图像是否匹配已存储的人脸"""
        user = request.user
        face_image = request.FILES.get('face_image')
        
        if not face_image:
            return Response({"error": "请上传人脸图像"}, status=status.HTTP_400_BAD_REQUEST)
        
        # 将图像转换为base64以便传输给AI服务
        image_data = base64.b64encode(face_image.read()).decode('utf-8')
        
        # 调用AI服务进行人脸验证
        ai_service_url = "http://localhost:8001/verify_face"
        
        try:
            response = requests.post(
                ai_service_url,
                json={"image": image_data, "user_id": user.id},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                return Response({"error": "AI服务处理失败"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            result = response.json()
            return Response(result)
            
        except Exception as e:
            return Response({"error": f"验证人脸时出错: {str(e)}"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)/encodings')
    def get_user_face_encodings(self, request, user_id=None):
        """获取用户的所有人脸编码数据"""
        try:
            # 管理员可以查看任何用户的人脸编码，普通用户只能查看自己的
            if not request.user.is_staff and str(request.user.id) != user_id:
                return Response({"error": "无权访问其他用户的人脸数据"}, 
                              status=status.HTTP_403_FORBIDDEN)
            
            user = User.objects.get(pk=user_id)
            face_data = FaceData.objects.filter(user=user, is_active=True)
            
            encodings = []
            for data in face_data:
                try:
                    encoding = data.get_face_encoding().tolist()
                    encodings.append(encoding)
                except Exception as e:
                    print(f"Error decoding face data: {e}")
            
            return Response({
                "user_id": user_id,
                "username": user.username,
                "encodings": encodings,
                "count": len(encodings)
            })
            
        except User.DoesNotExist:
            return Response({"error": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"获取人脸编码时出错: {str(e)}"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RegisteredFaceViewSet(viewsets.ModelViewSet):
    """已注册人脸视图集，主要用于非用户的人脸数据管理"""
    serializer_class = RegisteredFaceSerializer
    queryset = RegisteredFace.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """只有管理员可以执行创建、更新和删除操作"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]
    
    @action(detail=False, methods=['post'])
    def register_face(self, request):
        """注册新的人脸"""
        if not request.user.is_staff:
            return Response({"error": "只有管理员可以注册人脸"}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        name = request.data.get('name')
        category = request.data.get('category', 'visitor')
        face_image = request.FILES.get('face_image')
        note = request.data.get('note', '')
        
        if not name or not face_image:
            return Response({"error": "请提供姓名和人脸图像"}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # 将图像转换为base64以便传输给AI服务
        image_data = base64.b64encode(face_image.read()).decode('utf-8')
        
        # 调用AI服务进行人脸检测和特征提取
        ai_service_url = "http://localhost:8001/process_face"
        
        try:
            response = requests.post(
                ai_service_url,
                json={"image": image_data},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                return Response({"error": f"AI服务处理失败: HTTP {response.status_code}"}, 
                              status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            result = response.json()
            
            if not result.get('success', False):
                return Response({"error": result.get('message', '未检测到有效人脸')}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            # 重置文件指针以便保存图像
            face_image.seek(0)
            
            # 创建已注册人脸记录
            registered_face = RegisteredFace(
                name=name,
                category=category,
                face_image=face_image,
                note=note,
            )
            
            # 保存人脸编码
            registered_face.set_face_encoding(result.get('face_encoding'))
            registered_face.save()
            
            serializer = self.get_serializer(registered_face)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({"error": f"处理人脸数据时出错: {str(e)}"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)