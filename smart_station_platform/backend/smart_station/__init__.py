# 导入 Celery 应用程序实例
from .celery import app as celery_app

# 定义 __all__，这样当你从外部导入 smart_station 包时，可以直接访问 celery_app
__all__ = ('celery_app',)