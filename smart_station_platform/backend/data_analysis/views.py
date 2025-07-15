from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import random
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import DailyReport


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
