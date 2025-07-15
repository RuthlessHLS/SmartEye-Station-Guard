from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json

class TrafficData(models.Model):
    """交通数据模型"""
    timestamp = models.DateTimeField('时间戳', default=timezone.now)
    location_lat = models.FloatField('纬度')
    location_lng = models.FloatField('经度')
    intensity = models.FloatField('强度', default=1.0)
    traffic_count = models.IntegerField('客流量', default=0)
    avg_speed = models.FloatField('平均速度', default=0.0)
    
    class Meta:
        db_table = 'traffic_data'
        verbose_name = '交通数据'
        verbose_name_plural = '交通数据'
        ordering = ['-timestamp']

class VehicleTrajectory(models.Model):
    """车辆轨迹数据模型"""
    vehicle_id = models.CharField('车辆ID', max_length=50)
    timestamp = models.DateTimeField('时间戳', default=timezone.now)
    location_lat = models.FloatField('纬度')
    location_lng = models.FloatField('经度')
    speed = models.FloatField('速度', default=0.0)
    direction = models.FloatField('方向', default=0.0)
    
    class Meta:
        db_table = 'vehicle_trajectory'
        verbose_name = '车辆轨迹'
        verbose_name_plural = '车辆轨迹'
        ordering = ['vehicle_id', 'timestamp']

class WeatherData(models.Model):
    """天气数据模型"""
    timestamp = models.DateTimeField('时间戳', default=timezone.now)
    weather_type = models.CharField('天气类型', max_length=20)  # 晴、阴、雨、雪等
    temperature = models.FloatField('温度')
    humidity = models.FloatField('湿度', default=0.0)
    wind_speed = models.FloatField('风速', default=0.0)
    
    class Meta:
        db_table = 'weather_data'
        verbose_name = '天气数据'
        verbose_name_plural = '天气数据'
        ordering = ['-timestamp']

class TrafficTrend(models.Model):
    """交通趋势数据模型"""
    time_period = models.CharField('时间段', max_length=10)  # 00:00, 06:00等
    traffic_count = models.IntegerField('客流量', default=0)
    date = models.DateField('日期', default=timezone.now().date)
    
    class Meta:
        db_table = 'traffic_trend'
        verbose_name = '交通趋势'
        verbose_name_plural = '交通趋势'
        ordering = ['date', 'time_period']

class DistanceDistribution(models.Model):
    """出行距离分布模型"""
    distance_range = models.CharField('距离范围', max_length=20)  # 0-5km, 5-10km等
    count = models.IntegerField('数量', default=0)
    date = models.DateField('日期', default=timezone.now().date)
    
    class Meta:
        db_table = 'distance_distribution'
        verbose_name = '距离分布'
        verbose_name_plural = '距离分布'
        ordering = ['date', 'distance_range']

class DataScreenConfig(models.Model):
    """数据大屏配置模型"""
    name = models.CharField('配置名称', max_length=100)
    config_data = models.JSONField('配置数据', default=dict)
    is_active = models.BooleanField('是否激活', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        db_table = 'data_screen_config'
        verbose_name = '数据大屏配置'
        verbose_name_plural = '数据大屏配置'