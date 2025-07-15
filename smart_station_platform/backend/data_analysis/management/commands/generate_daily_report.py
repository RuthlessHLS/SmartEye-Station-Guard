import json
from django.core.management.base import BaseCommand
from data_analysis.models import DailyReport
from data_analysis.ai_report_utils import generate_ai_report
from alerts.models import Alert
from datetime import date
import re

class Command(BaseCommand):
    help = '生成结构化AI监控日报'

    def handle(self, *args, **options):
        today = date.today()
        alerts = Alert.objects.filter(timestamp__date=today)
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

        # 关键事件（可根据实际业务挑选，这里留空）
        key_events = []

        # AI摘要
        prompt = (
            "请根据以下监控数据，严格只输出结构化JSON摘要，字段包括：overview（整体概览，字符串），type_summary（异常类型分布，数组，每项含type和desc），"
            "key_points（重点关注，数组），suggestions（建议，数组），所有内容用简洁正式中文。不要输出任何解释、markdown、注释，只要JSON。\n"
            f"数据：告警数{total_alerts}，异常类型：{','.join([d['name'] for d in type_dist])}"
        )
        summary_text = generate_ai_report(prompt)
        # 打印AI原始输出，便于调试
        print("AI原始输出：", summary_text)
        # 尝试直接解析JSON，否则用正则提取
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
        print("解析后：", summary)

        # 组装结构化日报
        report_data = {
            "date": str(today),
            "summary": summary,
            "totalAlerts": total_alerts,
            "resolvedAlerts": resolved_alerts,
            "pendingAlerts": pending_alerts,
            "alertTypeDistribution": type_dist,
            "alertTrend": trend,
            "keyEvents": key_events
        }

        DailyReport.objects.update_or_create(
            date=today,
            defaults={'content': json.dumps(report_data, ensure_ascii=False)}
        )
        self.stdout.write(self.style.SUCCESS("结构化日报生成成功！"))
 