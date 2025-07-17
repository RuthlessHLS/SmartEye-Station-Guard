from rest_framework import serializers
from .models import (
    TrafficData, VehicleTrajectory, WeatherData, 
    TrafficTrend, DistanceDistribution, DataScreenConfig, DailyReport
)

class TrafficDataSerializer(serializers.ModelSerializer):
    """交通数据序列化器"""
    class Meta:
        model = TrafficData
        fields = '__all__'

class VehicleTrajectorySerializer(serializers.ModelSerializer):
    """车辆轨迹序列化器"""
    class Meta:
        model = VehicleTrajectory
        fields = '__all__'

class WeatherDataSerializer(serializers.ModelSerializer):
    """天气数据序列化器"""
    class Meta:
        model = WeatherData
        fields = '__all__'

class TrafficTrendSerializer(serializers.ModelSerializer):
    """交通趋势序列化器"""
    class Meta:
        model = TrafficTrend
        fields = '__all__'

class DistanceDistributionSerializer(serializers.ModelSerializer):
    """距离分布序列化器"""
    class Meta:
        model = DistanceDistribution
        fields = '__all__'

class DataScreenConfigSerializer(serializers.ModelSerializer):
    """数据大屏配置序列化器"""
    class Meta:
        model = DataScreenConfig
        fields = '__all__'

class DashboardDataSerializer(serializers.Serializer):
    """数据大屏综合数据序列化器"""
    heatmap = serializers.ListField(child=serializers.DictField())
    traffic_trend = serializers.ListField(child=serializers.DictField())
    distance_distribution = serializers.ListField(child=serializers.DictField())
    weather_traffic = serializers.ListField(child=serializers.DictField())
    avg_speed = serializers.FloatField()

class TrajectoryDataSerializer(serializers.Serializer):
    """轨迹数据序列化器"""
    trajectory = serializers.ListField(child=serializers.ListField())
    vehicle_info = serializers.DictField(required=False) 

class RealTimeDataSerializer(serializers.Serializer):
    """实时数据序列化器"""
    vehicle_flow = serializers.IntegerField()
    person_flow = serializers.IntegerField()

class DailyReportSerializer(serializers.ModelSerializer):
    """AI日报的序列化器"""
    class Meta:
        model = DailyReport
        fields = '__all__' 