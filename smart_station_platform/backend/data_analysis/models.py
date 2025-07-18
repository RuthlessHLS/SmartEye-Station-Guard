from django.db import models

# Create your models here.

class DailyReport(models.Model):
    date = models.DateField(auto_now_add=True, unique=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"日报 {self.date}"
