from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
import random
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import DailyReport

from .models import (
    TrafficData, VehicleTrajectory, WeatherData, 
    TrafficTrend, DistanceDistribution, DataScreenConfig
)
from .serializers import (
    TrafficDataSerializer, VehicleTrajectorySerializer, WeatherDataSerializer,
    TrafficTrendSerializer, DistanceDistributionSerializer, DataScreenConfigSerializer,
    DashboardDataSerializer, TrajectoryDataSerializer
)

class DashboardView(APIView):
    """数据大屏主视图"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # 获取查询参数
            date_str = request.GET.get('date', timezone.now().date().isoformat())
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # 获取热力图数据
            heatmap_data = self._get_heatmap_data(target_date)
            
            # 获取交通趋势数据
            traffic_trend = self._get_traffic_trend(target_date)
            
            # 获取距离分布数据
            distance_distribution = self._get_distance_distribution(target_date)
            
            # 获取天气交通关联数据
            weather_traffic = self._get_weather_traffic_data(target_date)
            
            # 获取平均速度
            avg_speed = self._get_avg_speed(target_date)
            
            data = {
                'heatmap': heatmap_data,
                'traffic_trend': traffic_trend,
                'distance_distribution': distance_distribution,
                'weather_traffic': weather_traffic,
                'avg_speed': avg_speed,
                'last_updated': timezone.now().isoformat(),
            }
            
            serializer = DashboardDataSerializer(data)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': f'获取数据失败: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_heatmap_data(self, target_date):
        """获取热力图数据"""
        # 从数据库获取最近的交通数据
        traffic_data = TrafficData.objects.filter(
            timestamp__date=target_date
        ).values('location_lat', 'location_lng', 'intensity')[:100]
        
        if not traffic_data.exists():
            # 如果没有数据，返回模拟数据
            return [
                {'coordinates': [116.4074, 39.9042], 'intensity': 0.8},
                {'coordinates': [116.3913, 39.9110], 'intensity': 0.6},
                {'coordinates': [116.4172, 39.9200], 'intensity': 0.9},
                {'coordinates': [116.4040, 39.9080], 'intensity': 0.7},
                {'coordinates': [116.4100, 39.9200], 'intensity': 0.5},
            ]
        
        return [
            {
                'coordinates': [item['location_lng'], item['location_lat']], 
                'intensity': item['intensity']
            }
            for item in traffic_data
        ]

    def _get_traffic_trend(self, target_date):
        """获取交通趋势数据"""
        # 从数据库获取交通趋势数据
        trend_data = TrafficTrend.objects.filter(date=target_date).order_by('time_period')
        
        if not trend_data.exists():
            # 如果没有数据，返回模拟数据
            return [
                {'time': '00:00', 'count': 100}, {'time': '06:00', 'count': 500},
                {'time': '12:00', 'count': 1200}, {'time': '18:00', 'count': 900},
                {'time': '23:00', 'count': 200}
            ]
        
        return [
            {'time': item.time_period, 'count': item.traffic_count}
            for item in trend_data
        ]

    def _get_distance_distribution(self, target_date):
        """获取距离分布数据"""
        # 从数据库获取距离分布数据
        dist_data = DistanceDistribution.objects.filter(date=target_date).order_by('distance_range')
        
        if not dist_data.exists():
            # 如果没有数据，返回模拟数据
            return [
                {'name': '0-5km', 'value': 300}, {'name': '5-10km', 'value': 500},
                {'name': '10-20km', 'value': 400}, {'name': '>20km', 'value': 150}
            ]
        
        return [
            {'name': item.distance_range, 'value': item.count}
            for item in dist_data
        ]

    def _get_weather_traffic_data(self, target_date):
        """获取天气交通关联数据"""
        # 从数据库获取天气和交通数据
        weather_data = WeatherData.objects.filter(
            timestamp__date=target_date
        ).values('weather_type').annotate(
            avg_temp=Avg('temperature'),
            traffic_count=Count('id')
        )
        
        if not weather_data.exists():
            # 如果没有数据，返回模拟数据
            return [
                {'weather': '晴', 'traffic': 1000, 'temperature': 25},
                {'weather': '阴', 'traffic': 800, 'temperature': 20},
                {'weather': '雨', 'traffic': 500, 'temperature': 18},
                {'weather': '雪', 'traffic': 200, 'temperature': -2}
            ]
        
        return [
            {
                'weather': item['weather_type'], 
                'traffic': item['traffic_count'], 
                'temperature': round(item['avg_temp'], 1)
            }
            for item in weather_data
        ]

    def _get_avg_speed(self, target_date):
        """获取平均速度"""
        # 从数据库获取平均速度
        avg_speed = TrafficData.objects.filter(
            timestamp__date=target_date
        ).aggregate(avg_speed=Avg('avg_speed'))
        
        return round(avg_speed['avg_speed'] or 45.5, 1)

class TrajectoryView(APIView):
    """车辆轨迹回放视图"""
    permission_classes = [IsAuthenticated]

    def get(self, request, vehicle_id):
        try:
            # 获取查询参数
            start_time = request.GET.get('start_time')
            end_time = request.GET.get('end_time')
            
            # 构建查询条件
            query = Q(vehicle_id=vehicle_id)
            if start_time:
                query &= Q(timestamp__gte=start_time)
            if end_time:
                query &= Q(timestamp__lte=end_time)
            
            # 从数据库获取轨迹数据
            trajectory_data = VehicleTrajectory.objects.filter(query).order_by('timestamp')
            
            if not trajectory_data.exists():
                # 如果没有数据，返回模拟数据
                trajectory = [
                    [116.3972, 39.9096, 40],
                    [116.4000, 39.9100, 50],
                    [116.4050, 39.9120, 60],
                    [116.4100, 39.9150, 30],
                    [116.4150, 39.9180, 45],
                ]
            else:
                trajectory = [
                    [item.location_lng, item.location_lat, item.speed]
                    for item in trajectory_data
                ]
            
            # 获取车辆信息
            vehicle_info = {
                'vehicle_id': vehicle_id,
                'total_points': len(trajectory),
                'avg_speed': sum(point[2] for point in trajectory) / len(trajectory) if trajectory else 0,
                'start_time': trajectory_data.first().timestamp if trajectory_data.exists() else None,
                'end_time': trajectory_data.last().timestamp if trajectory_data.exists() else None,
            }
            
            data = {
                'trajectory': trajectory,
                'vehicle_info': vehicle_info
            }
            
            serializer = TrajectoryDataSerializer(data)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': f'获取轨迹数据失败: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TrafficDataView(APIView):
    """交通数据管理视图"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取交通数据列表"""
        try:
            # 获取查询参数
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            limit = int(request.GET.get('limit', 100))
            
            query = Q()
            if start_date:
                query &= Q(timestamp__date__gte=start_date)
            if end_date:
                query &= Q(timestamp__date__lte=end_date)
            
            traffic_data = TrafficData.objects.filter(query).order_by('-timestamp')[:limit]
            serializer = TrafficDataSerializer(traffic_data, many=True)
            
            return Response({
                'data': serializer.data,
                'total': traffic_data.count(),
                'limit': limit
            })
            
        except Exception as e:
            return Response(
                {'error': f'获取交通数据失败: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """创建交通数据"""
        try:
            serializer = TrafficDataSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f'创建交通数据失败: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class WeatherDataView(APIView):
    """天气数据管理视图"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取天气数据"""
        try:
            # 获取查询参数
            days = int(request.GET.get('days', 7))
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            weather_data = WeatherData.objects.filter(
                timestamp__date__range=[start_date, end_date]
            ).order_by('-timestamp')
            
            serializer = WeatherDataSerializer(weather_data, many=True)
            
            return Response({
                'data': serializer.data,
                'total': weather_data.count(),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            })
            
        except Exception as e:
            return Response(
                {'error': f'获取天气数据失败: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """创建天气数据"""
        try:
            serializer = WeatherDataSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f'创建天气数据失败: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DataScreenConfigView(APIView):
    """数据大屏配置视图"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取数据大屏配置"""
        try:
            config = DataScreenConfig.objects.filter(is_active=True).first()
            if config:
                serializer = DataScreenConfigSerializer(config)
                return Response(serializer.data)
            else:
                # 返回默认配置
                default_config = {
                    'name': '默认配置',
                    'config_data': {
                        'map_center': [116.3972, 39.9096],
                        'map_zoom': 10,
                        'refresh_interval': 30000,  # 30秒
                        'chart_colors': ['#67e0e3', '#37a2da', '#fd666d', '#9fe6b8'],
                    },
                    'is_active': True
                }
                return Response(default_config)
                
        except Exception as e:
            return Response(
                {'error': f'获取配置失败: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """保存数据大屏配置"""
        try:
            serializer = DataScreenConfigSerializer(data=request.data)
            if serializer.is_valid():
                # 如果设置为激活，先取消其他配置的激活状态
                if serializer.validated_data.get('is_active', False):
                    DataScreenConfig.objects.filter(is_active=True).update(is_active=False)
                
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f'保存配置失败: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class RealTimeDataView(APIView):
    """实时数据视图"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取实时数据"""
        try:
            # 获取最近1小时的数据
            one_hour_ago = timezone.now() - timedelta(hours=1)
            
            # 实时交通数据
            realtime_traffic = TrafficData.objects.filter(
                timestamp__gte=one_hour_ago
            ).order_by('-timestamp')[:50]
            
            # 实时天气数据
            realtime_weather = WeatherData.objects.filter(
                timestamp__gte=one_hour_ago
            ).order_by('-timestamp').first()
            
            # 实时平均速度
            avg_speed = TrafficData.objects.filter(
                timestamp__gte=one_hour_ago
            ).aggregate(avg_speed=Avg('avg_speed'))
            
            data = {
                'realtime_traffic': TrafficDataSerializer(realtime_traffic, many=True).data,
                'realtime_weather': WeatherDataSerializer(realtime_weather).data if realtime_weather else None,
                'current_avg_speed': round(avg_speed['avg_speed'] or 0, 1),
                'last_updated': timezone.now().isoformat(),
            }
            
            return Response(data)
            
        except Exception as e:
            return Response(
                {'error': f'获取实时数据失败: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 模拟轨迹数据，实际应从数据库获取
        # trajectory = [
        #     [116.3972, 39.9096, 40],
        #     [116.4000, 39.9100, 50],
        #     [116.4050, 39.9120, 60],
        #     [116.4100, 39.9150, 30],
        # ]
        return Response({'trajectory': trajectory})
        
class DailyReportView(APIView):
    def get(self, request, date_str):
        from alerts.models import Alert
        from datetime import datetime
        import json, re
        from .ai_report_utils import generate_ai_report

        # 解析日期
        try:
            report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return Response({'error': '日期格式错误，应为 YYYY-MM-DD'}, status=400)

        alerts = Alert.objects.filter(timestamp__date=report_date)
        total_alerts = alerts.count()
        resolved_alerts = alerts.filter(status='resolved').count()
        pending_alerts = alerts.filter(status='pending').count()

        # 类型分布
        type_dist = []
        for t in alerts.values_list('event_type', flat=True).distinct():
            type_dist.append({
                "name": t,
                "value": alerts.filter(event_type=t).count()
            })

        # 24小时趋势
        trend = []
        for h in range(24):
            hour_str = f"{h:02d}:00"
            count = alerts.filter(timestamp__hour=h).count()
            trend.append({"hour": hour_str, "count": count})

        # 关键事件打分函数，必须在调用前定义
        def calc_alert_score(alert):
            type_score = {
                'fire_smoke': 10,
                'person_fall': 8,
                'stranger_intrusion': 6,
                'spoofing_attempt': 4,
                'other': 3
            }
            score = type_score.get(alert.event_type, 3)
            if alert.status == 'pending':
                score += 2
            elif alert.status == 'in_progress':
                score += 1
            if hasattr(alert, 'confidence') and alert.confidence and alert.confidence > 0.9:
                score += 2
            if 22 <= alert.timestamp.hour or alert.timestamp.hour < 6:
                score += 1
            return score

        # 关键事件（每种类型只取分数最高的一条，最多3条）
        scored_alerts = [(alert, calc_alert_score(alert)) for alert in alerts]
        sorted_alerts = sorted(scored_alerts, key=lambda x: x[1], reverse=True)
        type_seen = set()
        key_events = []
        for alert, score in sorted_alerts:
            if alert.event_type not in type_seen:
                key_events.append({
                    "id": alert.id,
                    "title": f"{dict(Alert.EVENT_TYPE_CHOICES).get(alert.event_type, alert.event_type)}告警",
                    "time": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "imageUrl": alert.image_snapshot_url or '',
                    "score": score
                })
                type_seen.add(alert.event_type)
            if len(key_events) >= 3:
                break

        # AI摘要
        prompt = (
            "请根据以下监控数据，严格只输出结构化JSON摘要，字段包括：overview（整体概览，字符串），type_summary（异常类型分布，数组，每项含type和desc），"
            "key_points（重点关注，数组），suggestions（建议，数组），所有内容用简洁正式中文。不要输出任何解释、markdown、注释，只要JSON。\n"
            f"数据：告警数{total_alerts}，正常数100，异常类型：{','.join([d['name'] for d in type_dist])}"
        )
        summary_text = generate_ai_report(prompt)
        try:
            summary = json.loads(summary_text)
        except Exception:
            match = re.search(r'({[\s\S]*})', summary_text)
            if match:
                try:
                    summary = json.loads(match.group(1))
                except Exception:
                    summary = {"overview": summary_text}
            else:
                summary = {"overview": summary_text}

        report_data = {
            "date": date_str,
            "summary": summary,
            "totalAlerts": total_alerts,
            "resolvedAlerts": resolved_alerts,
            "pendingAlerts": pending_alerts,
            "alertTypeDistribution": type_dist,
            "alertTrend": trend,
            "keyEvents": key_events
        }
        return Response(report_data)

