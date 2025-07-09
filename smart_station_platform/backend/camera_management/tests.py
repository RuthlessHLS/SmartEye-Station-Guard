from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Camera, DangerousArea


class CameraModelTest(TestCase):
    """摄像头模型测试"""
    
    def setUp(self):
        self.camera = Camera.objects.create(
            name="测试摄像头",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            location_desc="测试位置",
            is_active=True
        )
    
    def test_camera_creation(self):
        """测试摄像头创建"""
        self.assertEqual(self.camera.name, "测试摄像头")
        self.assertEqual(self.camera.rtsp_url, "rtsp://192.168.1.100:554/stream")
        self.assertTrue(self.camera.is_active)
    
    def test_camera_str_representation(self):
        """测试摄像头字符串表示"""
        self.assertEqual(str(self.camera), "测试摄像头")


class DangerousAreaModelTest(TestCase):
    """危险区域模型测试"""
    
    def setUp(self):
        self.camera = Camera.objects.create(
            name="测试摄像头",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            location_desc="测试位置"
        )
        self.area = DangerousArea.objects.create(
            camera=self.camera,
            name="测试区域",
            coordinates=[[100, 100], [200, 100], [200, 200], [100, 200]],
            min_distance_threshold=0.5,
            time_in_area_threshold=30,
            is_active=True
        )
    
    def test_dangerous_area_creation(self):
        """测试危险区域创建"""
        self.assertEqual(self.area.name, "测试区域")
        self.assertEqual(self.area.camera, self.camera)
        self.assertEqual(len(self.area.coordinates), 4)
        self.assertEqual(self.area.min_distance_threshold, 0.5)
        self.assertEqual(self.area.time_in_area_threshold, 30)
        self.assertTrue(self.area.is_active)
    
    def test_dangerous_area_str_representation(self):
        """测试危险区域字符串表示"""
        self.assertEqual(str(self.area), "测试摄像头 - 测试区域")


class CameraAPITest(APITestCase):
    """摄像头API测试"""
    
    def setUp(self):
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # 获取JWT令牌
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        
        # 设置认证头
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        # 创建测试摄像头
        self.camera = Camera.objects.create(
            name="API测试摄像头",
            rtsp_url="rtsp://192.168.1.101:554/stream",
            location_desc="API测试位置",
            is_active=True
        )
    
    def test_get_camera_list(self):
        """测试获取摄像头列表"""
        url = reverse('camera-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "API测试摄像头")
    
    def test_get_camera_detail(self):
        """测试获取摄像头详情"""
        url = reverse('camera-detail', args=[self.camera.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "API测试摄像头")
        self.assertIn('dangerous_areas', response.data)
    
    def test_create_camera(self):
        """测试创建摄像头"""
        url = reverse('camera-list')
        data = {
            'name': '新摄像头',
            'rtsp_url': 'rtsp://192.168.1.102:554/stream',
            'location_desc': '新位置',
            'is_active': True
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Camera.objects.count(), 2)
        self.assertEqual(response.data['name'], '新摄像头')
    
    def test_update_camera(self):
        """测试更新摄像头"""
        url = reverse('camera-detail', args=[self.camera.id])
        data = {
            'name': '更新后的摄像头',
            'rtsp_url': 'rtsp://192.168.1.103:554/stream',
            'location_desc': '更新后的位置',
            'is_active': False
        }
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.camera.refresh_from_db()
        self.assertEqual(self.camera.name, '更新后的摄像头')
        self.assertFalse(self.camera.is_active)
    
    def test_delete_camera(self):
        """测试删除摄像头"""
        url = reverse('camera-detail', args=[self.camera.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Camera.objects.count(), 0)
    
    def test_toggle_camera_status(self):
        """测试切换摄像头状态"""
        url = reverse('camera-toggle-status', args=[self.camera.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.camera.refresh_from_db()
        self.assertFalse(self.camera.is_active)
    
    def test_get_active_cameras(self):
        """测试获取启用的摄像头"""
        # 创建另一个禁用的摄像头
        Camera.objects.create(
            name="禁用摄像头",
            rtsp_url="rtsp://192.168.1.104:554/stream",
            location_desc="禁用位置",
            is_active=False
        )
        
        url = reverse('camera-active-cameras')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "API测试摄像头")


class DangerousAreaAPITest(APITestCase):
    """危险区域API测试"""
    
    def setUp(self):
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # 获取JWT令牌
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        
        # 设置认证头
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        # 创建测试摄像头
        self.camera = Camera.objects.create(
            name="API测试摄像头",
            rtsp_url="rtsp://192.168.1.101:554/stream",
            location_desc="API测试位置"
        )
        
        # 创建测试危险区域
        self.area = DangerousArea.objects.create(
            camera=self.camera,
            name="API测试区域",
            coordinates=[[100, 100], [200, 100], [200, 200], [100, 200]],
            min_distance_threshold=0.5,
            time_in_area_threshold=30,
            is_active=True
        )
    
    def test_get_dangerous_area_list(self):
        """测试获取危险区域列表"""
        url = reverse('dangerous-area-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "API测试区域")
    
    def test_get_dangerous_area_detail(self):
        """测试获取危险区域详情"""
        url = reverse('dangerous-area-detail', args=[self.area.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "API测试区域")
        self.assertEqual(response.data['camera_name'], "API测试摄像头")
    
    def test_create_dangerous_area(self):
        """测试创建危险区域"""
        url = reverse('dangerous-area-list')
        data = {
            'camera': self.camera.id,
            'name': '新区域',
            'coordinates': [[150, 150], [250, 150], [250, 250], [150, 250]],
            'min_distance_threshold': 1.0,
            'time_in_area_threshold': 60,
            'is_active': True
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DangerousArea.objects.count(), 2)
        self.assertEqual(response.data['name'], '新区域')
    
    def test_create_duplicate_area_name(self):
        """测试创建重复名称的危险区域"""
        url = reverse('dangerous-area-list')
        data = {
            'camera': self.camera.id,
            'name': 'API测试区域',  # 重复名称
            'coordinates': [[150, 150], [250, 150], [250, 250], [150, 250]],
            'min_distance_threshold': 1.0,
            'time_in_area_threshold': 60,
            'is_active': True
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_update_dangerous_area(self):
        """测试更新危险区域"""
        url = reverse('dangerous-area-detail', args=[self.area.id])
        data = {
            'camera': self.camera.id,
            'name': '更新后的区域',
            'coordinates': [[120, 120], [220, 120], [220, 220], [120, 220]],
            'min_distance_threshold': 0.8,
            'time_in_area_threshold': 45,
            'is_active': False
        }
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.area.refresh_from_db()
        self.assertEqual(self.area.name, '更新后的区域')
        self.assertFalse(self.area.is_active)
    
    def test_delete_dangerous_area(self):
        """测试删除危险区域"""
        url = reverse('dangerous-area-detail', args=[self.area.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(DangerousArea.objects.count(), 0)
    
    def test_toggle_dangerous_area_status(self):
        """测试切换危险区域状态"""
        url = reverse('dangerous-area-toggle-status', args=[self.area.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.area.refresh_from_db()
        self.assertFalse(self.area.is_active)
    
    def test_get_areas_by_camera(self):
        """测试获取指定摄像头的危险区域"""
        url = reverse('dangerous-area-by-camera')
        response = self.client.get(url, {'camera_id': self.camera.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "API测试区域")
    
    def test_get_active_areas(self):
        """测试获取启用的危险区域"""
        # 创建另一个禁用的区域
        DangerousArea.objects.create(
            camera=self.camera,
            name="禁用区域",
            coordinates=[[300, 300], [400, 300], [400, 400], [300, 400]],
            min_distance_threshold=0.5,
            time_in_area_threshold=30,
            is_active=False
        )
        
        url = reverse('dangerous-area-active-areas')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "API测试区域")
