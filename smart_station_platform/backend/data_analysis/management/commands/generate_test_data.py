from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
import random
import math

from data_analysis.models import (
    TrafficData, VehicleTrajectory, WeatherData, 
    TrafficTrend, DistanceDistribution
)

class Command(BaseCommand):
    help = '生成数据大屏的测试数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='生成多少天的数据 (默认: 7天)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='清除现有数据'
        )

    def handle(self, *args, **options):
        days = options['days']
        clear = options['clear']
        
        if clear:
            self.stdout.write('清除现有数据...')
            TrafficData.objects.all().delete()
            VehicleTrajectory.objects.all().delete()
            WeatherData.objects.all().delete()
            TrafficTrend.objects.all().delete()
            DistanceDistribution.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('数据清除完成'))
        
        self.stdout.write(f'开始生成 {days} 天的测试数据...')
        
        # 生成交通数据
        self.generate_traffic_data(days)
        
        # 生成车辆轨迹数据
        self.generate_vehicle_trajectory(days)
        
        # 生成天气数据
        self.generate_weather_data(days)
        
        # 生成交通趋势数据
        self.generate_traffic_trend(days)
        
        # 生成距离分布数据
        self.generate_distance_distribution(days)
        
        self.stdout.write(self.style.SUCCESS('测试数据生成完成！'))

    def generate_traffic_data(self, days):
        """生成交通数据"""
        self.stdout.write('生成交通数据...')
        
        # 北京主要区域坐标
        beijing_areas = [
            (116.4074, 39.9042),  # 天安门
            (116.3913, 39.9110),  # 西单
            (116.4172, 39.9200),  # 王府井
            (116.4040, 39.9080),  # 东单
            (116.4100, 39.9200),  # 国贸
            (116.3972, 39.9096),  # 西直门
            (116.4000, 39.9100),  # 复兴门
            (116.4050, 39.9120),  # 建国门
        ]
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        for date in [start_date + timedelta(days=i) for i in range(days)]:
            for hour in range(24):
                for minute in range(0, 60, 15):  # 每15分钟一条数据
                    timestamp = datetime.combine(date, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
                    timestamp = timezone.make_aware(timestamp)
                    
                    # 根据时间段调整客流量
                    if 7 <= hour <= 9 or 17 <= hour <= 19:  # 早晚高峰
                        base_traffic = random.randint(800, 1500)
                        base_speed = random.uniform(20, 40)
                    elif 10 <= hour <= 16:  # 白天
                        base_traffic = random.randint(400, 800)
                        base_speed = random.uniform(30, 60)
                    else:  # 夜间
                        base_traffic = random.randint(50, 200)
                        base_speed = random.uniform(40, 80)
                    
                    # 为每个区域生成数据
                    for lat, lng in beijing_areas:
                        # 添加随机偏移
                        offset_lat = lat + random.uniform(-0.01, 0.01)
                        offset_lng = lng + random.uniform(-0.01, 0.01)
                        
                        TrafficData.objects.create(
                            timestamp=timestamp,
                            location_lat=offset_lat,
                            location_lng=offset_lng,
                            intensity=random.uniform(0.3, 1.0),
                            traffic_count=base_traffic + random.randint(-100, 100),
                            avg_speed=base_speed + random.uniform(-10, 10)
                        )

    def generate_vehicle_trajectory(self, days):
        """生成车辆轨迹数据"""
        self.stdout.write('生成车辆轨迹数据...')
        
        vehicle_ids = [f'VEH_{i:03d}' for i in range(1, 21)]  # 20辆车
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        for vehicle_id in vehicle_ids:
            # 随机起始位置
            start_lat = 39.9 + random.uniform(-0.1, 0.1)
            start_lng = 116.4 + random.uniform(-0.1, 0.1)
            
            current_lat, current_lng = start_lat, start_lng
            
            for date in [start_date + timedelta(days=i) for i in range(days)]:
                # 每天生成一条轨迹
                start_time = datetime.combine(date, datetime.min.time()) + timedelta(hours=random.randint(6, 18))
                start_time = timezone.make_aware(start_time)
                
                # 生成轨迹点
                for i in range(random.randint(20, 50)):  # 20-50个轨迹点
                    timestamp = start_time + timedelta(minutes=i * 2)  # 每2分钟一个点
                    
                    # 随机移动
                    current_lat += random.uniform(-0.005, 0.005)
                    current_lng += random.uniform(-0.005, 0.005)
                    
                    # 确保在北京范围内
                    current_lat = max(39.7, min(40.1, current_lat))
                    current_lng = max(116.2, min(116.8, current_lng))
                    
                    speed = random.uniform(20, 80)
                    direction = random.uniform(0, 360)
                    
                    VehicleTrajectory.objects.create(
                        vehicle_id=vehicle_id,
                        timestamp=timestamp,
                        location_lat=current_lat,
                        location_lng=current_lng,
                        speed=speed,
                        direction=direction
                    )

    def generate_weather_data(self, days):
        """生成天气数据"""
        self.stdout.write('生成天气数据...')
        
        weather_types = ['晴', '多云', '阴', '小雨', '中雨', '大雨', '雪']
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        for date in [start_date + timedelta(days=i) for i in range(days)]:
            # 每天生成3次天气数据
            for hour in [6, 12, 18]:
                timestamp = datetime.combine(date, datetime.min.time()) + timedelta(hours=hour)
                timestamp = timezone.make_aware(timestamp)
                
                weather_type = random.choice(weather_types)
                
                # 根据天气类型设置温度范围
                if weather_type in ['雪']:
                    temperature = random.uniform(-10, 5)
                elif weather_type in ['小雨', '中雨', '大雨']:
                    temperature = random.uniform(10, 25)
                else:
                    temperature = random.uniform(15, 35)
                
                humidity = random.uniform(30, 90)
                wind_speed = random.uniform(0, 20)
                
                WeatherData.objects.create(
                    timestamp=timestamp,
                    weather_type=weather_type,
                    temperature=temperature,
                    humidity=humidity,
                    wind_speed=wind_speed
                )

    def generate_traffic_trend(self, days):
        """生成交通趋势数据"""
        self.stdout.write('生成交通趋势数据...')
        
        time_periods = ['00:00', '06:00', '12:00', '18:00', '23:00']
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        for date in [start_date + timedelta(days=i) for i in range(days)]:
            for period in time_periods:
                if period == '06:00':
                    traffic_count = random.randint(400, 800)  # 早高峰
                elif period == '12:00':
                    traffic_count = random.randint(800, 1200)  # 中午
                elif period == '18:00':
                    traffic_count = random.randint(600, 1000)  # 晚高峰
                elif period == '23:00':
                    traffic_count = random.randint(100, 300)  # 深夜
                else:
                    traffic_count = random.randint(50, 200)  # 凌晨
                
                TrafficTrend.objects.create(
                    date=date,
                    time_period=period,
                    traffic_count=traffic_count
                )

    def generate_distance_distribution(self, days):
        """生成距离分布数据"""
        self.stdout.write('生成距离分布数据...')
        
        distance_ranges = ['0-5km', '5-10km', '10-20km', '>20km']
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        for date in [start_date + timedelta(days=i) for i in range(days)]:
            for distance_range in distance_ranges:
                if distance_range == '0-5km':
                    count = random.randint(200, 400)
                elif distance_range == '5-10km':
                    count = random.randint(300, 600)
                elif distance_range == '10-20km':
                    count = random.randint(200, 500)
                else:  # >20km
                    count = random.randint(50, 200)
                
                DistanceDistribution.objects.create(
                    date=date,
                    distance_range=distance_range,
                    count=count
                ) 