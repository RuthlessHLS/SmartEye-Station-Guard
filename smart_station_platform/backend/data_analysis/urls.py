# G:\Web\smart_station_platform\backend\camera_management\urls.py (或 ai_reports/urls.py, data_analysis/urls.py)

from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('trajectory/<str:vehicle_id>/', views.TrajectoryView.as_view(), name='trajectory'),
]