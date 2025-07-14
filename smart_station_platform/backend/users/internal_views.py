from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
import os

User = get_user_model()

class InternalLoginAPIView(APIView):
    """
    内部服务专用的登录接口，用于通过人脸识别后的用户名直接获取Token。
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        # 1. 从请求中获取API Key和用户名
        api_key = request.headers.get('X-Internal-API-Key')
        username = request.data.get('username')
        
        # 2. 验证API Key
        internal_api_key = os.getenv('INTERNAL_SERVICE_API_KEY', 'default-internal-secret-key-for-dev')
        if not api_key or api_key != internal_api_key:
            return Response(
                {"error": "Unauthorized: Invalid or missing API Key."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 3. 验证用户名
        if not username:
            return Response(
                {"error": "Username is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 4. 查找用户
        try:
            user = User.objects.get(username=username, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found or is inactive."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 5. 生成JWT Token
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        # 6. 构建并返回响应数据
        response_data = {
            'refresh': str(refresh),
            'access': access_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'nickname': user.nickname,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK) 