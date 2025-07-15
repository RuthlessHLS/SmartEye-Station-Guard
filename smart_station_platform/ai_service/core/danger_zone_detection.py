# 文件: ai_service/core/danger_zone_detection.py
# 描述: 危险区域检测模块 - 实现多边形区域定义、点在多边形内判断、距离计算等几何算法，
#       以及危险区域入侵检测和停留时间追踪功能。

import math
import time
import json # 用于日志或未来配置存储
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict # 用于 camera_zones 字典
import logging

logger = logging.getLogger(__name__)

@dataclass
class Point:
    """表示一个二维点坐标。"""
    x: float
    y: float
    
    def distance_to(self, other: 'Point') -> float:
        """计算到另一个点的欧氏距离。"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

@dataclass
class BoundingBox:
    """表示一个边界框，包含左上角和右下角坐标。"""
    x1: float
    y1: float
    x2: float
    y2: float
    
    @property
    def center(self) -> Point:
        """获取边界框的中心点。"""
        return Point((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)
    
    @property
    def bottom_center(self) -> Point:
        """获取边界框的底部中心点（通常用于人员的足部位置，更适合区域判断）。"""
        return Point((self.x1 + self.x2) / 2, self.y2)

@dataclass
class DangerZone:
    """
    危险区域的定义。
    
    Attributes:
        zone_id: 区域的唯一标识符。
        name: 区域的友好名称。
        coordinates: 定义多边形区域的顶点列表 [[x1, y1], [x2, y2], ...]
                     (至少3个点以形成有效多边形)。
        min_distance_threshold: 距离区域边缘的最小距离阈值 (像素)。当人员接近但未进入区域时，
                                如果距离小于此阈值，可触发告警。默认为0，表示不检查距离。
        time_in_area_threshold: 在区域内停留的最小时间阈值 (秒)。当人员在区域内停留超过此时间，
                                可触发告警。默认为0，表示不检查停留时间。
        is_active: 区域是否启用。
    """
    zone_id: str
    name: str
    coordinates: List[List[float]]
    min_distance_threshold: float = 0.0
    time_in_area_threshold: int = 0
    is_active: bool = True
    
    @property
    def polygon_points(self) -> List[Point]:
        """将区域坐标转换为 Point 对象列表。"""
        return [Point(coord[0], coord[1]) for coord in self.coordinates]

@dataclass
class PersonTracker:
    """
    跟踪人员在危险区域检测模块中的状态。
    
    Attributes:
        tracking_id: 由上游目标追踪器提供的唯一追踪ID。
        first_detected_time: 首次检测到该人员的时间戳。
        last_seen_time: 最后一次检测到该人员的时间戳。
        zone_entry_time: 进入某个危险区域的时间戳 (如果当前在区域内)。
        current_position: 当前人员的 Point 坐标。
        inside_zone: 一个字典，{zone_id: bool}，表示当前是否在某个区域内。
        distance_to_zone: 一个字典，{zone_id: float}，表示到每个区域的最新距离。
        alert_triggered: 一个字典，{zone_id: Dict}，记录每个区域内已触发的告警类型和时间，防止重复告警。
    """
    tracking_id: str
    first_detected_time: float = field(default_factory=time.time)
    last_seen_time: float = field(default_factory=time.time)
    zone_entry_time: Dict[str, float] = field(default_factory=dict) # {zone_id: entry_time}
    current_position: Optional[Point] = None
    inside_zone: Dict[str, bool] = field(default_factory=dict) # {zone_id: bool}
    distance_to_zone: Dict[str, float] = field(default_factory=lambda: defaultdict(lambda: float('inf'))) # {zone_id: distance}
    alert_triggered: Dict[str, Dict[str, float]] = field(default_factory=dict) # {zone_id: {alert_type: last_trigger_time}}

class GeometryUtils:
    """提供几何计算的静态方法。"""
    
    @staticmethod
    def point_in_polygon(point: Point, polygon: List[Point]) -> bool:
        """
        判断点是否在多边形内（射线法）。
        Args:
            point: 要判断的点。
            polygon: 多边形的顶点列表。
        Returns:
            bool: 如果点在多边形内返回 True，否则返回 False。
        """
        if len(polygon) < 3:
            logger.warning("多边形至少需要3个顶点。")
            return False
            
        x, y = point.x, point.y
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0].x, polygon[0].y
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n].x, polygon[i % n].y
            
            # 判断射线是否与边相交
            if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
            p1x, p1y = p2x, p2y
            
        return inside
    
    @staticmethod
    def point_to_polygon_distance(point: Point, polygon: List[Point]) -> float:
        """
        计算点到多边形边界的最短距离。
        如果点在多边形内部，返回 0.0。
        Args:
            point: 要计算距离的点。
            polygon: 多边形的顶点列表。
        Returns:
            float: 点到多边形的最短距离。
        """
        if len(polygon) < 3:
            logger.warning("多边形至少需要3个顶点，无法计算距离。")
            return float('inf')
            
        # 如果点在多边形内部，距离为0
        if GeometryUtils.point_in_polygon(point, polygon):
            return 0.0
            
        min_distance = float('inf')
        n = len(polygon)
        
        # 计算点到每条边的距离
        for i in range(n):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % n]
            distance = GeometryUtils.point_to_line_distance(point, p1, p2)
            min_distance = min(min_distance, distance)
            
        return min_distance
    
    @staticmethod
    def point_to_line_distance(point: Point, line_start: Point, line_end: Point) -> float:
        """
        计算点到线段的最短距离。
        Args:
            point: 要计算距离的点。
            line_start: 线段的起点。
            line_end: 线段的终点。
        Returns:
            float: 点到线段的最短距离。
        """
        line_length_sq = (line_end.x - line_start.x) ** 2 + (line_end.y - line_start.y) ** 2
        
        if line_length_sq == 0: # 线段是一个点
            return point.distance_to(line_start)
        
        # 计算投影参数 t (0 <= t <= 1 表示投影在线段内)
        t = max(0, min(1, ((point.x - line_start.x) * (line_end.x - line_start.x) + 
                          (point.y - line_start.y) * (line_end.y - line_start.y)) / line_length_sq))
        
        # 投影点
        projection = Point(
            line_start.x + t * (line_end.x - line_start.x),
            line_start.y + t * (line_end.y - line_start.y)
        )
        
        return point.distance_to(projection)

class DangerZoneDetector:
    """
    危险区域检测器，管理和检测人员在预定义危险区域内的行为。
    """
    
    def __init__(self):
        # 所有定义的危险区域，以 zone_id 为键
        self.zones: Dict[str, DangerZone] = {} 
        # 跟踪每个摄像头对应的危险区域ID列表
        self.camera_zones: Dict[str, List[str]] = defaultdict(list) 
        # 跟踪每个人员的当前状态和历史信息
        self.person_trackers: Dict[str, PersonTracker] = {}
        logger.info("危险区域检测器初始化完成。")
        
    def add_danger_zone(self, camera_id: str, zone: DangerZone):
        """
        添加一个新的危险区域。
        Args:
            camera_id: 区域所属的摄像头ID。
            zone: DangerZone 对象。
        """
        if not zone.zone_id:
            logger.error("添加危险区域失败：zone_id 不能为空。")
            return
        if zone.zone_id in self.zones:
            logger.warning(f"危险区域 {zone.zone_id} 已存在，将更新其配置。")
        self.zones[zone.zone_id] = zone
        if zone.zone_id not in self.camera_zones[camera_id]:
            self.camera_zones[camera_id].append(zone.zone_id)
        logger.info(f"添加/更新危险区域: '{zone.name}' (ID: {zone.zone_id}) 到摄像头 {camera_id}")
    
    def remove_danger_zone(self, camera_id: str, zone_id: str):
        """
        移除指定的危险区域。
        Args:
            camera_id: 区域所属的摄像头ID。
            zone_id: 要移除的区域ID。
        """
        if zone_id in self.zones:
            del self.zones[zone_id]
            logger.info(f"成功移除危险区域定义: {zone_id}")
        else:
            logger.warning(f"尝试移除不存在的危险区域定义: {zone_id}")

        if camera_id in self.camera_zones and zone_id in self.camera_zones[camera_id]:
            self.camera_zones[camera_id].remove(zone_id)
            logger.info(f"已将危险区域 {zone_id} 从摄像头 {camera_id} 的关联列表中移除。")
        else:
            logger.warning(f"危险区域 {zone_id} 未与摄像头 {camera_id} 关联。")
    
    def update_camera_zones(self, camera_id: str, zones_data: List[Dict]):
        """
        根据提供的字典数据更新摄像头的危险区域配置。
        此方法会清除该摄像头原有的所有区域配置，并添加新的区域。
        Args:
            camera_id: 摄像头ID。
            zones_data: 包含危险区域配置字典的列表。
        """
        logger.info(f"开始更新摄像头 {camera_id} 的危险区域配置。")
        # 清除该摄像头的旧区域
        old_zone_ids = self.camera_zones[camera_id].copy()
        for zone_id in old_zone_ids:
            if zone_id in self.zones: # 确保只删除属于该摄像头的共享zone_id
                self.remove_danger_zone(camera_id, zone_id) # 调用移除方法以正确清理

        # 添加新区域
        for idx, zone_data in enumerate(zones_data):
            zone_id = zone_data.get('zone_id', f"{camera_id}_zone_{idx+1}") # 确保有唯一ID
            if not zone_data.get('coordinates') or len(zone_data['coordinates']) < 3:
                logger.warning(f"跳过无效的危险区域配置 (缺少或不足3个坐标点): {zone_data.get('name', zone_id)}")
                continue

            zone = DangerZone(
                zone_id=zone_id,
                name=zone_data.get('name', f"区域 {idx+1}"),
                coordinates=zone_data['coordinates'],
                min_distance_threshold=float(zone_data.get('min_distance_threshold', 0.0)),
                time_in_area_threshold=int(zone_data.get('time_in_area_threshold', 0)),
                is_active=bool(zone_data.get('is_active', True))
            )
            self.add_danger_zone(camera_id, zone)
        logger.info(f"摄像头 {camera_id} 的危险区域配置更新完成。总共配置 {len(self.camera_zones[camera_id])} 个区域。")
    
    def detect_intrusions(self, camera_id: str, detections: List[Dict]) -> List[Dict]:
        """
        检测危险区域入侵。
        Args:
            camera_id: 摄像头ID。
            detections: 检测结果列表，每个元素应包含 'tracking_id', 'bbox' 和 'class_name'。
                        例如：[{'tracking_id': 'FB_1', 'bbox': [x1,y1,x2,y2], 'class_name': 'person'}]
        Returns:
            告警列表。
        """
        alerts = []
        current_time = time.time()
        
        # 获取该摄像头的危险区域
        zone_ids = self.camera_zones.get(camera_id, [])
        if not zone_ids:
            logger.debug(f"摄像头 {camera_id} 没有配置危险区域，跳过入侵检测。")
            self._cleanup_old_trackers(current_time) # 即使没有区域，也清理过期人员
            return alerts
        
        # 筛选出本次检测到的人员，并更新其追踪器状态
        current_person_tracking_ids = set()
        for detection in detections:
            if detection.get('class_name') != 'person': # 只关心人员
                continue
            
            tracking_id = detection.get('tracking_id')
            if not tracking_id:
                logger.debug(f"跳过无追踪ID的人员检测: {detection}")
                continue
                
            current_person_tracking_ids.add(tracking_id)
            bbox = BoundingBox(*detection['bbox'])
            person_position = bbox.bottom_center # 使用脚部位置更准确

            if tracking_id not in self.person_trackers:
                self.person_trackers[tracking_id] = PersonTracker(tracking_id=tracking_id)
                logger.debug(f"创建新的人员追踪器: {tracking_id}")
            
            tracker = self.person_trackers[tracking_id]
            tracker.last_seen_time = current_time
            tracker.current_position = person_position
            
            # 对每个活跃区域进行检测
            for zone_id in zone_ids:
                zone = self.zones.get(zone_id)
                if not zone or not zone.is_active:
                    continue # 跳过无效或不活跃区域
                
                polygon_points = zone.polygon_points
                
                # 检查是否在区域内
                is_inside = GeometryUtils.point_in_polygon(person_position, polygon_points)
                distance_to_zone = GeometryUtils.point_to_polygon_distance(person_position, polygon_points)
                
                tracker.distance_to_zone[zone_id] = distance_to_zone
                
                # 区域入侵检测 (进入/离开)
                was_inside = tracker.inside_zone.get(zone_id, False)
                if is_inside and not was_inside:
                    # 进入危险区域
                    tracker.inside_zone[zone_id] = True
                    tracker.zone_entry_time[zone_id] = current_time
                    alerts.append({
                        'type': 'danger_zone_entry',
                        'message': f'人员 {tracking_id} 进入危险区域 "{zone.name}"',
                        'tracking_id': tracking_id,
                        'zone_id': zone_id,
                        'zone_name': zone.name,
                        'position': [person_position.x, person_position.y],
                        'timestamp': current_time
                    })
                    logger.info(f"🚨 [危险区域] 人员 {tracking_id} 进入区域 '{zone.name}' (ID: {zone_id})")
                    # 重置该区域的告警触发状态，以便重新计时和触发
                    tracker.alert_triggered[zone_id] = {} 
                    
                elif not is_inside and was_inside:
                    # 离开危险区域
                    tracker.inside_zone[zone_id] = False
                    tracker.zone_entry_time.pop(zone_id, None) # 移除进入时间
                    logger.info(f"✅ [危险区域] 人员 {tracking_id} 离开区域 '{zone.name}' (ID: {zone_id})")
                    # 离开时重置该区域的所有告警触发状态
                    tracker.alert_triggered[zone_id] = {}
                
                # 停留时间检测
                if (tracker.inside_zone.get(zone_id, False) and 
                    zone.time_in_area_threshold > 0):
                    
                    entry_time = tracker.zone_entry_time.get(zone_id)
                    if entry_time:
                        time_in_zone = current_time - entry_time
                        if (time_in_zone >= zone.time_in_area_threshold and
                            not tracker.alert_triggered[zone_id].get('dwell_alert', False)): # 防止重复触发
                            
                            alerts.append({
                                'type': 'danger_zone_dwell',
                                'message': f'人员 {tracking_id} 在危险区域 "{zone.name}" 停留超过 {zone.time_in_area_threshold} 秒',
                                'tracking_id': tracking_id,
                                'zone_id': zone_id,
                                'zone_name': zone.name,
                                'dwell_time': time_in_zone,
                                'position': [person_position.x, person_position.y],
                                'timestamp': current_time
                            })
                            tracker.alert_triggered[zone_id]['dwell_alert'] = current_time # 标记已触发
                            logger.info(f"⏳ [危险区域] 人员 {tracking_id} 停留告警 (区域: '{zone.name}', 停留: {time_in_zone:.1f}s)")
                
                # 距离阈值检测 (只在区域外触发)
                if (zone.min_distance_threshold > 0 and 
                    distance_to_zone <= zone.min_distance_threshold and
                    not tracker.inside_zone.get(zone_id, False) and # 确保在区域外
                    not tracker.alert_triggered[zone_id].get('proximity_alert', False)): # 防止重复触发
                    
                    alerts.append({
                        'type': 'danger_zone_proximity',
                        'message': f'人员 {tracking_id} 接近危险区域 "{zone.name}" (距离: {distance_to_zone:.1f}像素)',
                        'tracking_id': tracking_id,
                        'zone_id': zone_id,
                        'zone_name': zone.name,
                        'distance': distance_to_zone,
                        'position': [person_position.x, person_position.y],
                        'timestamp': current_time
                    })
                    tracker.alert_triggered[zone_id]['proximity_alert'] = current_time # 标记已触发
                    logger.info(f"⚠️ [危险区域] 人员 {tracking_id} 接近告警 (区域: '{zone.name}', 距离: {distance_to_zone:.1f}px)")
        
        # 清理长时间未见的追踪器
        self._cleanup_old_trackers(current_time)
        
        return alerts
    
    def _cleanup_old_trackers(self, current_time: float, timeout_s: float = 30.0):
        """
        清理长时间未见的人员追踪器状态，防止内存泄漏。
        Args:
            current_time (float): 当前时间戳。
            timeout_s (float): 对象从缓存中移除前的最大不活跃时间（秒）。
        """
        to_remove = []
        for tracking_id, tracker in list(self.person_trackers.items()): # 遍历副本，允许删除
            if current_time - tracker.last_seen_time > timeout_s:
                to_remove.append(tracking_id)
        
        for tracking_id in to_remove:
            del self.person_trackers[tracking_id]
            logger.debug(f"清理过期人员追踪器状态: {tracking_id}")
    
    def get_zone_status(self, camera_id: str) -> Dict[str, Any]:
        """
        获取指定摄像头危险区域的当前状态信息。
        Args:
            camera_id: 摄像头ID。
        Returns:
            Dict: 包含区域配置、区域内人员及活跃人员信息的字典。
        """
        zone_ids = self.camera_zones.get(camera_id, [])
        status = {
            'camera_id': camera_id,
            'zones': [],
            'active_persons': []
        }
        
        # 汇总区域配置和区域内人员
        for zone_id in zone_ids:
            zone = self.zones.get(zone_id)
            if zone:
                zone_info = {
                    'zone_id': zone_id,
                    'name': zone.name,
                    'is_active': zone.is_active,
                    'coordinates': zone.coordinates,
                    'min_distance_threshold': zone.min_distance_threshold,
                    'time_in_area_threshold': zone.time_in_area_threshold,
                    'persons_inside': []
                }
                
                # 查找在此区域内的人员
                for tracker in self.person_trackers.values():
                    if tracker.inside_zone.get(zone_id, False) and tracker.current_position:
                        time_in_zone = time.time() - tracker.zone_entry_time.get(zone_id, time.time())
                        zone_info['persons_inside'].append({
                            'tracking_id': tracker.tracking_id,
                            'position': [tracker.current_position.x, tracker.current_position.y],
                            'time_in_zone': round(time_in_zone, 2),
                            'last_seen_s_ago': round(time.time() - tracker.last_seen_time, 2)
                        })
                
                status['zones'].append(zone_info)
        
        # 汇总活跃人员信息
        for tracker in self.person_trackers.values():
            if tracker.current_position:
                status['active_persons'].append({
                    'tracking_id': tracker.tracking_id,
                    'position': [round(tracker.current_position.x, 2), round(tracker.current_position.y, 2)],
                    'inside_zones': [zid for zid, inside in tracker.inside_zone.items() if inside],
                    'distance_to_zones': {zid: round(dist, 2) for zid, dist in tracker.distance_to_zone.items()},
                    'last_seen_s_ago': round(time.time() - tracker.last_seen_time, 2),
                    'first_detected_s_ago': round(time.time() - tracker.first_detected_time, 2)
                })
        
        logger.debug(f"获取摄像头 {camera_id} 危险区域状态成功。")
        return status

# 全局检测器实例
danger_zone_detector = DangerZoneDetector()