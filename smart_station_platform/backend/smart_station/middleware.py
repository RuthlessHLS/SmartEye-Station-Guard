# backend/smart_station/middleware.py

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser, User
from rest_framework_simplejwt.tokens import AccessToken
from urllib.parse import parse_qs
import os
from django.http import JsonResponse
from django.conf import settings
from django.urls import resolve

@database_sync_to_async
def get_user(token_key):
    try:
        access_token = AccessToken(token_key)
        user_id = access_token['user_id']
        return User.objects.get(id=user_id)
    except Exception:
        return AnonymousUser()

class TokenAuthMiddleware:
    """
    JWT Token a身份认证中间件，用于WebSocket
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            scope['user'] = await get_user(token)
        else:
            scope['user'] = AnonymousUser()

        return await self.app(scope, receive, send)

class InternalAPIMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.internal_api_key = os.getenv('INTERNAL_SERVICE_API_KEY', 'a-secure-default-key-for-dev')
        
        # 定义需要内部API密钥认证的URL路径前缀
        self.internal_paths = [
            '/api/alerts/ai-results/',
            '/api/alerts/websocket/broadcast/'
        ]

    def __call__(self, request):
        resolved_path = resolve(request.path_info).route
        
        # 检查请求路径是否需要内部API密钥认证
        is_internal_path = any(request.path.startswith(path) for path in self.internal_paths)

        if is_internal_path:
            # 从请求头中获取API密钥
            provided_key = request.headers.get('X-Internal-API-Key')

            if not provided_key or provided_key != self.internal_api_key:
                return JsonResponse({'error': 'Unauthorized: Invalid or missing internal API key.'}, status=401)
            
            # 密钥验证通过，为视图函数添加一个标记，表示是受信任的内部请求
            # 这样视图函数就可以选择性地跳过常规的用户认证
            request.is_internal_call = True
        else:
            request.is_internal_call = False

        response = self.get_response(request)
        return response