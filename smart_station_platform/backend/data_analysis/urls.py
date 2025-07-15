from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('trajectory/<str:vehicle_id>/', views.TrajectoryView.as_view(), name='trajectory'),
   path('reports/daily/<str:date_str>/', views.DailyReportView.as_view()),
]
