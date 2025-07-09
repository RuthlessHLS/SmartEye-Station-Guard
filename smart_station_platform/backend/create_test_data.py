#!/usr/bin/env python3
"""
创建测试数据的脚本
"""

import os
import sys
import django
from datetime import datetime, timedelta

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_station.test_settings')
django.setup()

from django.contrib.auth.models import User
from camera_management.models import Camera
from alerts.models import Alert

def create_test_data():
    """创建测试数据"""
    print("🚀 开始创建测试数据...")
    
    # 1. 创建测试用户
    if not User.objects.filter(username='testuser').exists():
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='测试',
            last_name='用户'
        )
        print(f"✅ 创建测试用户: {user.username}")
    else:
        user = User.objects.get(username='testuser')
        print(f"✅ 使用现有用户: {user.username}")
    
    # 2. 创建测试摄像头
    cameras_data = [
        {
            'name': 'test_camera_001',
            'location_desc': '主入口监控点',
            'is_active': True,
            'rtsp_url': 'rtsp://192.168.1.100:554/stream1'
        },
        {
            'name': 'entrance_camera',
            'location_desc': '大厅入口监控点',
            'is_active': True,
            'rtsp_url': 'rtsp://192.168.1.101:554/stream1'
        }
    ]
    
    for camera_data in cameras_data:
        camera, created = Camera.objects.get_or_create(
            name=camera_data['name'],
            defaults=camera_data
        )
        if created:
            print(f"✅ 创建摄像头: {camera.name}")
        else:
            print(f"✅ 使用现有摄像头: {camera.name}")
    
    # 3. 创建测试告警
    alerts_data = [
        {
            'camera': Camera.objects.get(name='test_camera_001'),
            'event_type': 'stranger_intrusion',
            'timestamp': datetime.now() - timedelta(hours=2),
            'location': {'zone': 'entrance', 'coordinates': [100, 200]},
            'confidence': 0.95,
            'image_snapshot_url': 'http://example.com/test_image1.jpg',
            'video_clip_url': 'http://example.com/test_video1.mp4',
            'status': 'pending'
        },
        {
            'camera': Camera.objects.get(name='entrance_camera'),
            'event_type': 'fire_smoke',
            'timestamp': datetime.now() - timedelta(hours=1),
            'location': {'zone': 'hall', 'coordinates': [200, 300]},
            'confidence': 0.87,
            'image_snapshot_url': 'http://example.com/test_image2.jpg',
            'video_clip_url': 'http://example.com/test_video2.mp4',
            'status': 'in_progress',
            'handler': user,
            'processing_notes': '正在核实火警情况'
        },
        {
            'camera': Camera.objects.get(name='test_camera_001'),
            'event_type': 'person_fall',
            'timestamp': datetime.now() - timedelta(minutes=30),
            'location': {'zone': 'entrance', 'coordinates': [150, 250]},
            'confidence': 0.92,
            'image_snapshot_url': 'http://example.com/test_image3.jpg',
            'status': 'resolved',
            'handler': user,
            'processing_notes': '已确认为误报，行李箱掉落'
        }
    ]
    
    for i, alert_data in enumerate(alerts_data):
        alert, created = Alert.objects.get_or_create(
            camera=alert_data['camera'],
            event_type=alert_data['event_type'],
            timestamp=alert_data['timestamp'],
            defaults=alert_data
        )
        if created:
            print(f"✅ 创建告警 {i+1}: {alert.event_type}")
        else:
            print(f"✅ 使用现有告警 {i+1}: {alert.event_type}")
    
    # 4. 统计信息
    total_cameras = Camera.objects.count()
    total_alerts = Alert.objects.count()
    pending_alerts = Alert.objects.filter(status='pending').count()
    
    print(f"\n📊 测试数据统计:")
    print(f"   - 摄像头数量: {total_cameras}")
    print(f"   - 告警总数: {total_alerts}")
    print(f"   - 待处理告警: {pending_alerts}")
    print(f"   - 测试用户: {user.username}")
    
    print(f"\n🎉 测试数据创建完成！")
    
if __name__ == '__main__':
    create_test_data() 