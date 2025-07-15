# G:\Web\smart_station_platform\backend\camera_management\urls.py (或 ai_reports/urls.py, data_analysis/urls.py)

from django.urls import path
from . import views

urlpatterns = [
    # 数据大屏主接口
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # 轨迹回放接口
    path('trajectory/<str:vehicle_id>/', views.TrajectoryView.as_view(), name='trajectory'),
    
    # 交通数据管理接口
    path('traffic-data/', views.TrafficDataView.as_view(), name='traffic_data'),
    
    # 天气数据管理接口
    path('weather-data/', views.WeatherDataView.as_view(), name='weather_data'),
    
    # 数据大屏配置接口
    path('config/', views.DataScreenConfigView.as_view(), name='data_screen_config'),
    
    # 实时数据接口
    path('realtime/', views.RealTimeDataView.as_view(), name='realtime_data'),
]