# G:\Web\smart_station_platform\backend\smart_station\celery.py

import os
from celery import Celery

# 设置 Django 默认的 settings 模块，以便 Celery 能够加载 Django 配置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_station.settings')

# 创建 Celery 应用程序实例
app = Celery('smart_station')

# 从 Django settings 加载 Celery 配置，所有以 'CELERY_' 开头的设置都会被识别
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现 Django 应用中的任务 (在各自的 tasks.py 文件中定义)
app.autodiscover_tasks()

# 示例任务 (可选，用于调试)
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')