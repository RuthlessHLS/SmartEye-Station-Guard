from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import random
from datetime import datetime, timedelta

# Create your views here.

class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 模拟数据，实际应从数据库获取
        data = {
            'heatmap': [
                {'coordinates': [116.4074, 39.9042], 'intensity': 0.8},
                {'coordinates': [116.3913, 39.9110], 'intensity': 0.6},
                {'coordinates': [116.4172, 39.9200], 'intensity': 0.9},
            ],
            'traffic_trend': [
                {'time': '00:00', 'count': 100}, {'time': '06:00', 'count': 500},
                {'time': '12:00', 'count': 1200}, {'time': '18:00', 'count': 900},
                {'time': '23:00', 'count': 200}
            ],
            'distance_distribution': [
                {'name': '0-5km', 'value': 300}, {'name': '5-10km', 'value': 500},
                {'name': '10-20km', 'value': 400}, {'name': '>20km', 'value': 150}
            ],
            'weather_traffic': [
                {'weather': '晴', 'traffic': 1000, 'temperature': 25},
                {'weather': '阴', 'traffic': 800, 'temperature': 20},
                {'weather': '雨', 'traffic': 500, 'temperature': 18},
                {'weather': '雪', 'traffic': 200, 'temperature': -2}
            ],
            'avg_speed': 45.5,
        }
        return Response(data)

class TrajectoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vehicle_id):
        # 模拟轨迹数据，实际应从数据库获取
        trajectory = [
            [116.3972, 39.9096, 40],
            [116.4000, 39.9100, 50],
            [116.4050, 39.9120, 60],
            [116.4100, 39.9150, 30],
        ]
        return Response({'trajectory': trajectory})
