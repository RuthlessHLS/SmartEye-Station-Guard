# test_settings.py - 用于测试的Django设置

from .settings import *

# 使用SQLite数据库进行测试
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',
    }
}

# 使用内存Channel Layer（不需要Redis）
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# 允许所有主机（测试用）
ALLOWED_HOSTS = ['*']

# 简化的中间件（用于测试）
CORS_ALLOW_ALL_ORIGINS = True

# 简化JWT设置
SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'] = timedelta(hours=1)  # 延长到1小时方便测试

print("🚀 使用测试设置 - SQLite数据库 + 内存Channel Layer") 