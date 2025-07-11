"""
危险区域检测模块
实现多边形区域定义、点在多边形内判断、距离计算等几何算法
以及危险区域入侵检测和停留时间追踪功能
"""

import math
import time
import json
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class Point:
    """点坐标"""
    x: float
    y: float
    
    def distance_to(self, other: 'Point') -> float:
        """计算到另一个点的距离"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

@dataclass
class BoundingBox:
    """边界框"""
    x1: float
    y1: float
    x2: float
    y2: float
    
    @property
    def center(self) -> Point:
        """获取中心点"""
        return Point((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)
    
    @property
    def bottom_center(self) -> Point:
        """获取底部中心点（通常用于人员足部位置）"""
        return Point((self.x1 + self.x2) / 2, self.y2)

@dataclass
class DangerZone:
    """危险区域定义"""
    zone_id: str
    name: str
    coordinates: List[List[float]]  # [[x1, y1], [x2, y2], ...]
    min_distance_threshold: float = 0.0  # 距离边缘最小距离阈值(像素)
    time_in_area_threshold: int = 0      # 区域内停留时间阈值(秒)
    is_active: bool = True
    
    @property
    def polygon_points(self) -> List[Point]:
        """获取多边形顶点列表"""
        return [Point(coord[0], coord[1]) for coord in self.coordinates]

@dataclass
class PersonTracker:
    """人员追踪信息"""
    tracking_id: str
    first_detected_time: float = field(default_factory=time.time)
    last_seen_time: float = field(default_factory=time.time)
    zone_entry_time: Optional[float] = None
    current_position: Optional[Point] = None
    inside_zone: bool = False
    distance_to_zone: float = float('inf')
    alert_triggered: bool = False

class GeometryUtils:
    """几何计算工具类"""
    
    @staticmethod
    def point_in_polygon(point: Point, polygon: List[Point]) -> bool:
        """
        判断点是否在多边形内（射线法）
        """
        if len(polygon) < 3:
            return False
            
        x, y = point.x, point.y
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0].x, polygon[0].y
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n].x, polygon[i % n].y
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
            
        return inside
    
    @staticmethod
    def point_to_polygon_distance(point: Point, polygon: List[Point]) -> float:
        """
        计算点到多边形边界的最短距离
        """
        if len(polygon) < 3:
            return float('inf')
            
        min_distance = float('inf')
        
        # 检查是否在多边形内
        if GeometryUtils.point_in_polygon(point, polygon):
            return 0.0
            
        # 计算到每条边的距离
        n = len(polygon)
        for i in range(n):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % n]
            distance = GeometryUtils.point_to_line_distance(point, p1, p2)
            min_distance = min(min_distance, distance)
            
        return min_distance
    
    @staticmethod
    def point_to_line_distance(point: Point, line_start: Point, line_end: Point) -> float:
        """
        计算点到线段的最短距离
        """
        # 线段长度的平方
        line_length_sq = (line_end.x - line_start.x) ** 2 + (line_end.y - line_start.y) ** 2
        
        if line_length_sq == 0:
            # 线段是一个点
            return point.distance_to(line_start)
        
        # 计算投影参数
        t = max(0, min(1, ((point.x - line_start.x) * (line_end.x - line_start.x) + 
                          (point.y - line_start.y) * (line_end.y - line_start.y)) / line_length_sq))
        
        # 投影点
        projection = Point(
            line_start.x + t * (line_end.x - line_start.x),
            line_start.y + t * (line_end.y - line_start.y)
        )
        
        return point.distance_to(projection)

class DangerZoneDetector:
    """危险区域检测器"""
    
    def __init__(self):
        self.zones: Dict[str, DangerZone] = {}
        self.person_trackers: Dict[str, PersonTracker] = {}
        self.camera_zones: Dict[str, List[str]] = defaultdict(list)  # camera_id -> zone_ids
        
    def add_danger_zone(self, camera_id: str, zone: DangerZone):
        """添加危险区域"""
        self.zones[zone.zone_id] = zone
        if zone.zone_id not in self.camera_zones[camera_id]:
            self.camera_zones[camera_id].append(zone.zone_id)
        logger.info(f"添加危险区域: {zone.name} (ID: {zone.zone_id}) 到摄像头 {camera_id}")
    
    def remove_danger_zone(self, camera_id: str, zone_id: str):
        """移除危险区域"""
        if zone_id in self.zones:
            del self.zones[zone_id]
        if zone_id in self.camera_zones[camera_id]:
            self.camera_zones[camera_id].remove(zone_id)
        logger.info(f"移除危险区域: {zone_id} 从摄像头 {camera_id}")
    
    def update_camera_zones(self, camera_id: str, zones_data: List[Dict]):
        """更新摄像头的危险区域配置"""
        # 清除该摄像头的旧区域
        old_zone_ids = self.camera_zones[camera_id].copy()
        for zone_id in old_zone_ids:
            self.remove_danger_zone(camera_id, zone_id)
        
        # 添加新区域
        for zone_data in zones_data:
            zone = DangerZone(
                zone_id=f"{camera_id}_{zone_data['name']}",
                name=zone_data['name'],
                coordinates=zone_data['coordinates'],
                min_distance_threshold=zone_data.get('min_distance_threshold', 0.0),
                time_in_area_threshold=zone_data.get('time_in_area_threshold', 0),
                is_active=zone_data.get('is_active', True)
            )
            self.add_danger_zone(camera_id, zone)
    
    def detect_intrusions(self, camera_id: str, detections: List[Dict]) -> List[Dict]:
        """
        检测危险区域入侵
        
        Args:
            camera_id: 摄像头ID
            detections: 检测结果列表，每个包含bbox和tracking_id
            
        Returns:
            告警列表
        """
        alerts = []
        current_time = time.time()
        
        # 获取该摄像头的危险区域
        zone_ids = self.camera_zones.get(camera_id, [])
        print(f"🔍 [危险区域检测] 摄像头 {camera_id} 有 {len(zone_ids)} 个危险区域")
        if not zone_ids:
            print(f"⚠️ [危险区域检测] 摄像头 {camera_id} 没有配置危险区域")
            return alerts
        
        # 处理每个检测到的人员
        person_count = 0
        for detection in detections:
            if detection.get('type') != 'object' or detection.get('class_name') != 'person':
                continue
                
            tracking_id = detection.get('tracking_id')
            if not tracking_id:
                print(f"⚠️ [危险区域检测] 发现人员但无tracking_id: {detection}")
                continue
                
            person_count += 1
            bbox = BoundingBox(*detection['bbox'])
            person_position = bbox.bottom_center  # 使用脚部位置更准确
            print(f"👤 [危险区域检测] 处理人员 {tracking_id}: 位置=({person_position.x:.1f}, {person_position.y:.1f})")
            
            # 更新或创建人员追踪器
            if tracking_id not in self.person_trackers:
                self.person_trackers[tracking_id] = PersonTracker(tracking_id=tracking_id)
            
            tracker = self.person_trackers[tracking_id]
            tracker.last_seen_time = current_time
            tracker.current_position = person_position
            
            # 检查每个危险区域
            for zone_id in zone_ids:
                zone = self.zones.get(zone_id)
                if not zone or not zone.is_active:
                    continue
                
                # 检查是否在区域内
                is_inside = GeometryUtils.point_in_polygon(person_position, zone.polygon_points)
                distance_to_zone = GeometryUtils.point_to_polygon_distance(person_position, zone.polygon_points)
                print(f"   📐 区域 {zone.name}: 在区域内={is_inside}, 距离={distance_to_zone:.1f}px")
                
                tracker.distance_to_zone = min(tracker.distance_to_zone, distance_to_zone)
                
                # 区域入侵检测
                if is_inside and not tracker.inside_zone:
                    # 进入危险区域
                    tracker.inside_zone = True
                    tracker.zone_entry_time = current_time
                    
                    alerts.append({
                        'type': 'danger_zone_entry',
                        'message': f'人员 {tracking_id} 进入危险区域 {zone.name}',
                        'tracking_id': tracking_id,
                        'zone_id': zone_id,
                        'zone_name': zone.name,
                        'position': [person_position.x, person_position.y],
                        'timestamp': current_time
                    })
                    
                elif not is_inside and tracker.inside_zone:
                    # 离开危险区域
                    tracker.inside_zone = False
                    tracker.zone_entry_time = None
                    tracker.alert_triggered = False
                
                # 停留时间检测
                if (tracker.inside_zone and 
                    tracker.zone_entry_time and 
                    zone.time_in_area_threshold > 0 and
                    not tracker.alert_triggered):
                    
                    time_in_zone = current_time - tracker.zone_entry_time
                    if time_in_zone >= zone.time_in_area_threshold:
                        tracker.alert_triggered = True
                        
                        alerts.append({
                            'type': 'danger_zone_dwell',
                            'message': f'人员 {tracking_id} 在危险区域 {zone.name} 停留超过 {zone.time_in_area_threshold} 秒',
                            'tracking_id': tracking_id,
                            'zone_id': zone_id,
                            'zone_name': zone.name,
                            'dwell_time': time_in_zone,
                            'position': [person_position.x, person_position.y],
                            'timestamp': current_time
                        })
                
                # 距离阈值检测
                if (zone.min_distance_threshold > 0 and 
                    distance_to_zone <= zone.min_distance_threshold and
                    not is_inside):
                    
                    alerts.append({
                        'type': 'danger_zone_proximity',
                        'message': f'人员 {tracking_id} 接近危险区域 {zone.name} (距离: {distance_to_zone:.1f}像素)',
                        'tracking_id': tracking_id,
                        'zone_id': zone_id,
                        'zone_name': zone.name,
                        'distance': distance_to_zone,
                        'position': [person_position.x, person_position.y],
                        'timestamp': current_time
                    })
        
        # 清理长时间未见的追踪器
        self._cleanup_old_trackers(current_time)
        
        print(f"🎯 [危险区域检测] 处理完成: {person_count}个人员, {len(alerts)}个告警")
        return alerts
    
    def _cleanup_old_trackers(self, current_time: float, timeout: float = 30.0):
        """清理长时间未见的人员追踪器"""
        to_remove = []
        for tracking_id, tracker in self.person_trackers.items():
            if current_time - tracker.last_seen_time > timeout:
                to_remove.append(tracking_id)
        
        for tracking_id in to_remove:
            del self.person_trackers[tracking_id]
    
    def get_zone_status(self, camera_id: str) -> Dict:
        """获取危险区域状态信息"""
        zone_ids = self.camera_zones.get(camera_id, [])
        status = {
            'camera_id': camera_id,
            'zones': [],
            'active_persons': []
        }
        
        for zone_id in zone_ids:
            zone = self.zones.get(zone_id)
            if zone:
                zone_info = {
                    'zone_id': zone_id,
                    'name': zone.name,
                    'is_active': zone.is_active,
                    'coordinates': zone.coordinates,
                    'persons_inside': []
                }
                
                # 查找在此区域内的人员
                for tracker in self.person_trackers.values():
                    if tracker.inside_zone and tracker.current_position:
                        if GeometryUtils.point_in_polygon(tracker.current_position, zone.polygon_points):
                            zone_info['persons_inside'].append({
                                'tracking_id': tracker.tracking_id,
                                'position': [tracker.current_position.x, tracker.current_position.y],
                                'time_in_zone': time.time() - tracker.zone_entry_time if tracker.zone_entry_time else 0
                            })
                
                status['zones'].append(zone_info)
        
        # 活跃人员信息
        for tracker in self.person_trackers.values():
            if tracker.current_position:
                status['active_persons'].append({
                    'tracking_id': tracker.tracking_id,
                    'position': [tracker.current_position.x, tracker.current_position.y],
                    'inside_zone': tracker.inside_zone,
                    'distance_to_zone': tracker.distance_to_zone
                })
        
        return status

# 全局检测器实例
danger_zone_detector = DangerZoneDetector() 