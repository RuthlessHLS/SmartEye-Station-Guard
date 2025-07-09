#!/usr/bin/env python3
"""
调试AI接口问题
"""

import os
import django
from datetime import datetime
from django.utils import timezone

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_station.test_settings')
django.setup()

from alerts.serializers import AIResultReceiveSerializer
from camera_management.models import Camera

def test_ai_serializer():
    """测试AI结果序列化器"""
    print("🔍 调试AI接口问题")
    print("=" * 40)
    
    # 1. 检查Camera是否存在
    cameras = Camera.objects.all()
    print(f"📷 数据库中的摄像头数量: {cameras.count()}")
    for camera in cameras:
        print(f"   - {camera.name}: {camera.location_desc}")
    
    # 2. 测试序列化器
    test_data = {
        "camera_id": "test_camera_001",
        "event_type": "stranger_intrusion",
        "timestamp": timezone.now().isoformat(),
        "location": {"zone": "entrance", "coordinates": [100, 200]},
        "confidence": 0.95,
        "image_snapshot_url": "http://example.com/test_debug.jpg"
    }
    
    print(f"\n📝 测试数据:")
    print(f"   - camera_id: {test_data['camera_id']}")
    print(f"   - event_type: {test_data['event_type']}")
    print(f"   - timestamp: {test_data['timestamp']}")
    
    try:
        serializer = AIResultReceiveSerializer(data=test_data)
        if serializer.is_valid():
            print("✅ 序列化器验证通过")
            
            # 尝试保存
            try:
                alert = serializer.save()
                print(f"✅ 告警保存成功，ID: {alert.id}")
                print(f"   - 事件类型: {alert.event_type}")
                print(f"   - 摄像头: {alert.camera.name if alert.camera else '无'}")
                print(f"   - 时间: {alert.timestamp}")
                print(f"   - 状态: {alert.status}")
            except Exception as e:
                print(f"❌ 保存失败: {e}")
                print(f"错误类型: {type(e).__name__}")
                import traceback
                traceback.print_exc()
        else:
            print("❌ 序列化器验证失败")
            print(f"错误: {serializer.errors}")
            
    except Exception as e:
        print(f"❌ 序列化器异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_ai_serializer() 