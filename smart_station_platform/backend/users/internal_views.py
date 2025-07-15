from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
import os
from .serializers import UserSerializer
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny

User = get_user_model()

# --- 内部服务认证 ---

INTERNAL_API_KEY = os.getenv('INTERNAL_SERVICE_API_KEY', 'a-secure-default-key-for-dev')

def internal_api_key_required(view_func):
    """
    一个装饰器，用于验证内部服务之间的API请求。
    """
    from django.http import JsonResponse
    from hmac import compare_digest
    from functools import wraps

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        api_key = request.headers.get('X-Internal-API-Key')
        if not api_key or not compare_digest(api_key, INTERNAL_API_KEY):
            return JsonResponse({'error': 'Unauthorized: Invalid or missing API Key.'}, status=401)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# --- 内部视图 ---

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(internal_api_key_required, name='dispatch')
class InternalLoginAPIView(APIView):
    """
    为内部服务（如AI服务）提供一个免密登录的端点，
    通过验证内部API Key来确保安全。
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        
        if not username:
            return Response({"error": "Username is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(username=username, is_active=True)
        except User.DoesNotExist:
            return Response({"error": "User not found or is inactive."}, status=status.HTTP_404_NOT_FOUND)

        # 如果用户存在，生成Token
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        }) 