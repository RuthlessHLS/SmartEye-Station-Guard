import os
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_station.settings')
django.setup()

from camera_management.models import Camera

def create_test_camera():
    try:
        # 检查摄像头是否已存在
        camera = Camera.objects.filter(name='test_camera_001').first()
        if camera:
            print(f"测试摄像头已存在: {camera.name}")
            return camera
        
        # 创建测试摄像头
        camera = Camera.objects.create(
            name='test_camera_001',
            rtsp_url='rtsp://example.com/test_camera_001',
            location_desc='测试位置',
            is_active=True
        )
        print(f"成功创建测试摄像头: {camera.name}")
        return camera
    except Exception as e:
        print(f"创建测试摄像头时出错: {str(e)}")
        return None

if __name__ == "__main__":
    create_test_camera() 