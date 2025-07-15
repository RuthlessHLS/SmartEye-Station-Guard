# 数据大屏模块

## 概述

数据大屏模块提供了交通大数据可视化的完整后端解决方案，包括数据模型、API接口、管理后台和测试工具。

## 功能特性

- 🗺️ **热力图展示**: 实时显示交通流量热力图
- 🚗 **轨迹回放**: 支持车辆轨迹历史回放
- 📊 **数据可视化**: 多种图表展示交通趋势、距离分布等
- 🌤️ **天气关联**: 天气与交通流量的关联分析
- ⚡ **实时数据**: 支持实时数据更新和监控
- ⚙️ **配置管理**: 灵活的数据大屏配置管理

## 快速开始

### 1. 数据库迁移

```bash
# 进入后端目录
cd smart_station_platform/backend

# 执行数据库迁移
python manage.py makemigrations data_analysis
python manage.py migrate
```

### 2. 生成测试数据

```bash
# 生成7天的测试数据
python manage.py generate_test_data --days 7

# 清除现有数据并重新生成
python manage.py generate_test_data --days 7 --clear
```

### 3. 启动服务器

```bash
# 启动Django开发服务器
python manage.py runserver
```

### 4. 测试API

```bash
# 运行API测试脚本
python test_data_screen_api.py
```

## 数据模型

### TrafficData (交通数据)
存储交通流量和位置信息
- `timestamp`: 时间戳
- `location_lat/lng`: 位置坐标
- `intensity`: 热力图强度
- `traffic_count`: 客流量
- `avg_speed`: 平均速度

### VehicleTrajectory (车辆轨迹)
存储车辆移动轨迹
- `vehicle_id`: 车辆标识
- `timestamp`: 时间戳
- `location_lat/lng`: 位置坐标
- `speed`: 速度
- `direction`: 方向

### WeatherData (天气数据)
存储天气信息
- `timestamp`: 时间戳
- `weather_type`: 天气类型
- `temperature`: 温度
- `humidity`: 湿度
- `wind_speed`: 风速

### TrafficTrend (交通趋势)
存储时间段交通趋势
- `date`: 日期
- `time_period`: 时间段
- `traffic_count`: 客流量

### DistanceDistribution (距离分布)
存储出行距离分布
- `date`: 日期
- `distance_range`: 距离范围
- `count`: 数量

### DataScreenConfig (数据大屏配置)
存储大屏显示配置
- `name`: 配置名称
- `config_data`: 配置数据(JSON)
- `is_active`: 是否激活

## API接口

### 主要接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/data-analysis/dashboard/` | GET | 获取数据大屏综合数据 |
| `/api/data-analysis/trajectory/{id}/` | GET | 获取车辆轨迹数据 |
| `/api/data-analysis/traffic-data/` | GET/POST | 交通数据管理 |
| `/api/data-analysis/weather-data/` | GET/POST | 天气数据管理 |
| `/api/data-analysis/config/` | GET/POST | 大屏配置管理 |
| `/api/data-analysis/realtime/` | GET | 获取实时数据 |

### 使用示例

```javascript
// 获取数据大屏数据
const response = await fetch('/api/data-analysis/dashboard/', {
  headers: {
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json'
  }
});

const data = await response.json();
console.log('热力图数据:', data.heatmap);
console.log('交通趋势:', data.traffic_trend);
```

## 管理命令

### 生成测试数据

```bash
# 生成指定天数的测试数据
python manage.py generate_test_data --days 7

# 清除现有数据并重新生成
python manage.py generate_test_data --days 7 --clear

# 查看帮助
python manage.py generate_test_data --help
```

### 数据清理

```bash
# 清理指定日期之前的数据
python manage.py shell
```

```python
from data_analysis.models import *
from datetime import datetime, timedelta

# 清理30天前的数据
cutoff_date = datetime.now() - timedelta(days=30)
TrafficData.objects.filter(timestamp__lt=cutoff_date).delete()
VehicleTrajectory.objects.filter(timestamp__lt=cutoff_date).delete()
```

## 前端集成

### Vue.js 集成示例

```javascript
// api/index.js
import axios from 'axios';

const api = axios.create({
  baseURL: '/api/data-analysis/',
  headers: {
    'Authorization': `Token ${localStorage.getItem('token')}`
  }
});

export const dataScreenAPI = {
  // 获取数据大屏数据
  getDashboardData(date = null) {
    const params = date ? { date } : {};
    return api.get('dashboard/', { params });
  },
  
  // 获取车辆轨迹
  getTrajectory(vehicleId, startTime = null, endTime = null) {
    const params = {};
    if (startTime) params.start_time = startTime;
    if (endTime) params.end_time = endTime;
    return api.get(`trajectory/${vehicleId}/`, { params });
  },
  
  // 获取实时数据
  getRealtimeData() {
    return api.get('realtime/');
  }
};
```

### 在Vue组件中使用

```vue
<template>
  <div class="data-screen">
    <div id="mapbox-container"></div>
    <div id="trafficTrendChart"></div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { dataScreenAPI } from '@/api';

const mapData = ref({});

onMounted(async () => {
  try {
    const response = await dataScreenAPI.getDashboardData();
    mapData.value = response.data;
    initCharts();
  } catch (error) {
    console.error('获取数据失败:', error);
  }
});
</script>
```

## 配置说明

### 数据大屏配置

通过管理后台或API可以配置以下参数：

```json
{
  "map_center": [116.3972, 39.9096],
  "map_zoom": 10,
  "refresh_interval": 30000,
  "chart_colors": ["#67e0e3", "#37a2da", "#fd666d", "#9fe6b8"]
}
```

### 环境变量

在 `settings.py` 中可以配置：

```python
# 数据大屏配置
DATA_SCREEN_CONFIG = {
    'DEFAULT_MAP_CENTER': [116.3972, 39.9096],
    'DEFAULT_MAP_ZOOM': 10,
    'DEFAULT_REFRESH_INTERVAL': 30000,
    'MAX_DATA_POINTS': 1000,
}
```

## 性能优化

### 数据库优化

1. **索引优化**
```sql
-- 为常用查询字段添加索引
CREATE INDEX idx_traffic_data_timestamp ON traffic_data(timestamp);
CREATE INDEX idx_traffic_data_location ON traffic_data(location_lat, location_lng);
CREATE INDEX idx_vehicle_trajectory_vehicle_time ON vehicle_trajectory(vehicle_id, timestamp);
```

2. **数据分区**
```python
# 按日期分区存储历史数据
class TrafficDataPartition(models.Model):
    date = models.DateField()
    data = models.JSONField()
    
    class Meta:
        unique_together = ['date']
```

### 缓存策略

```python
from django.core.cache import cache

def get_dashboard_data(date):
    cache_key = f'dashboard_data_{date}'
    data = cache.get(cache_key)
    
    if not data:
        data = generate_dashboard_data(date)
        cache.set(cache_key, data, 300)  # 缓存5分钟
    
    return data
```

## 监控和维护

### 数据监控

```python
# 监控数据质量
def check_data_quality():
    # 检查数据完整性
    missing_data = TrafficData.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=1)
    ).count()
    
    if missing_data < 100:
        send_alert('数据量异常偏低')
```

### 日志记录

```python
import logging

logger = logging.getLogger('data_screen')

def log_api_request(request, response):
    logger.info(f'API请求: {request.path} - 状态码: {response.status_code}')
```

## 故障排除

### 常见问题

1. **API返回401错误**
   - 检查Token是否正确
   - 确认用户已登录

2. **数据加载缓慢**
   - 检查数据库索引
   - 考虑使用缓存
   - 优化查询语句

3. **地图不显示**
   - 检查Mapbox Token配置
   - 确认网络连接正常

### 调试模式

```python
# 在settings.py中启用调试
DEBUG = True

# 查看SQL查询
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## 扩展开发

### 添加新的数据源

1. 创建新的数据模型
2. 实现数据采集逻辑
3. 添加API接口
4. 更新前端展示

### 自定义图表

```javascript
// 添加新的图表类型
function createCustomChart(container, data) {
    const chart = echarts.init(container);
    const option = {
        // 自定义配置
    };
    chart.setOption(option);
}
```

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证。

## 联系方式

如有问题或建议，请通过以下方式联系：

- 邮箱: support@example.com
- 项目地址: https://github.com/your-repo/smart-station-platform 