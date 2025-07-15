from django.contrib import admin
from .models import (
    TrafficData, VehicleTrajectory, WeatherData, 
    TrafficTrend, DistanceDistribution, DataScreenConfig
)

@admin.register(TrafficData)
class TrafficDataAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'location_lat', 'location_lng', 'intensity', 'traffic_count', 'avg_speed']
    list_filter = ['timestamp', 'intensity']
    search_fields = ['location_lat', 'location_lng']
    ordering = ['-timestamp']
    date_hierarchy = 'timestamp'

@admin.register(VehicleTrajectory)
class VehicleTrajectoryAdmin(admin.ModelAdmin):
    list_display = ['vehicle_id', 'timestamp', 'location_lat', 'location_lng', 'speed', 'direction']
    list_filter = ['vehicle_id', 'timestamp', 'speed']
    search_fields = ['vehicle_id']
    ordering = ['vehicle_id', '-timestamp']
    date_hierarchy = 'timestamp'

@admin.register(WeatherData)
class WeatherDataAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'weather_type', 'temperature', 'humidity', 'wind_speed']
    list_filter = ['weather_type', 'timestamp']
    search_fields = ['weather_type']
    ordering = ['-timestamp']
    date_hierarchy = 'timestamp'

@admin.register(TrafficTrend)
class TrafficTrendAdmin(admin.ModelAdmin):
    list_display = ['date', 'time_period', 'traffic_count']
    list_filter = ['date', 'time_period']
    search_fields = ['time_period']
    ordering = ['-date', 'time_period']
    date_hierarchy = 'date'

@admin.register(DistanceDistribution)
class DistanceDistributionAdmin(admin.ModelAdmin):
    list_display = ['date', 'distance_range', 'count']
    list_filter = ['date', 'distance_range']
    search_fields = ['distance_range']
    ordering = ['-date', 'distance_range']
    date_hierarchy = 'date'

@admin.register(DataScreenConfig)
class DataScreenConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
