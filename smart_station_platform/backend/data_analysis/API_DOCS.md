# 数据大屏API文档

## 概述

数据大屏API提供了交通大数据可视化的后端接口，支持热力图、轨迹回放、交通趋势、天气关联等多种数据展示功能。

## 基础信息

- **基础URL**: `/api/data-analysis/`
- **认证方式**: Token认证 (需要在请求头中包含 `Authorization: Token <your_token>`)
- **数据格式**: JSON

## API端点

### 1. 数据大屏主接口

#### GET `/api/data-analysis/dashboard/`

获取数据大屏的综合数据，包括热力图、交通趋势、距离分布、天气关联和平均速度。

**查询参数:**
- `date` (可选): 查询日期，格式为 `YYYY-MM-DD`，默认为当天

**响应示例:**
```json
{
  "heatmap": [
    {
      "coordinates": [116.4074, 39.9042],
      "intensity": 0.8
    }
  ],
  "traffic_trend": [
    {
      "time": "00:00",
      "count": 100
    }
  ],
  "distance_distribution": [
    {
      "name": "0-5km",
      "value": 300
    }
  ],
  "weather_traffic": [
    {
      "weather": "晴",
      "traffic": 1000,
      "temperature": 25
    }
  ],
  "avg_speed": 45.5,
  "last_updated": "2024-01-01T12:00:00Z"
}
```

### 2. 车辆轨迹回放接口

#### GET `/api/data-analysis/trajectory/{vehicle_id}/`

获取指定车辆的轨迹数据，用于轨迹回放功能。

**路径参数:**
- `vehicle_id`: 车辆ID

**查询参数:**
- `start_time` (可选): 开始时间，格式为 `YYYY-MM-DDTHH:MM:SS`
- `end_time` (可选): 结束时间，格式为 `YYYY-MM-DDTHH:MM:SS`

**响应示例:**
```json
{
  "trajectory": [
    [116.3972, 39.9096, 40],
    [116.4000, 39.9100, 50]
  ],
  "vehicle_info": {
    "vehicle_id": "VEH_001",
    "total_points": 25,
    "avg_speed": 45.2,
    "start_time": "2024-01-01T08:00:00Z",
    "end_time": "2024-01-01T10:00:00Z"
  }
}
```

### 3. 交通数据管理接口

#### GET `/api/data-analysis/traffic-data/`

获取交通数据列表。

**查询参数:**
- `start_date` (可选): 开始日期，格式为 `YYYY-MM-DD`
- `end_date` (可选): 结束日期，格式为 `YYYY-MM-DD`
- `limit` (可选): 返回数据条数，默认为100

**响应示例:**
```json
{
  "data": [
    {
      "id": 1,
      "timestamp": "2024-01-01T12:00:00Z",
      "location_lat": 39.9042,
      "location_lng": 116.4074,
      "intensity": 0.8,
      "traffic_count": 1200,
      "avg_speed": 45.5
    }
  ],
  "total": 1000,
  "limit": 100
}
```

#### POST `/api/data-analysis/traffic-data/`

创建新的交通数据。

**请求体:**
```json
{
  "location_lat": 39.9042,
  "location_lng": 116.4074,
  "intensity": 0.8,
  "traffic_count": 1200,
  "avg_speed": 45.5
}
```

### 4. 天气数据管理接口

#### GET `/api/data-analysis/weather-data/`

获取天气数据。

**查询参数:**
- `days` (可选): 查询天数，默认为7天

**响应示例:**
```json
{
  "data": [
    {
      "id": 1,
      "timestamp": "2024-01-01T12:00:00Z",
      "weather_type": "晴",
      "temperature": 25.0,
      "humidity": 60.0,
      "wind_speed": 5.0
    }
  ],
  "total": 21,
  "date_range": {
    "start_date": "2023-12-25",
    "end_date": "2024-01-01"
  }
}
```

#### POST `/api/data-analysis/weather-data/`

创建新的天气数据。

**请求体:**
```json
{
  "weather_type": "晴",
  "temperature": 25.0,
  "humidity": 60.0,
  "wind_speed": 5.0
}
```

### 5. 数据大屏配置接口

#### GET `/api/data-analysis/config/`

获取数据大屏配置。

**响应示例:**
```json
{
  "id": 1,
  "name": "默认配置",
  "config_data": {
    "map_center": [116.3972, 39.9096],
    "map_zoom": 10,
    "refresh_interval": 30000,
    "chart_colors": ["#67e0e3", "#37a2da", "#fd666d", "#9fe6b8"]
  },
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### POST `/api/data-analysis/config/`

保存数据大屏配置。

**请求体:**
```json
{
  "name": "自定义配置",
  "config_data": {
    "map_center": [116.3972, 39.9096],
    "map_zoom": 12,
    "refresh_interval": 60000,
    "chart_colors": ["#ff6b6b", "#4ecdc4", "#45b7d1", "#96ceb4"]
  },
  "is_active": true
}
```

### 6. 实时数据接口

#### GET `/api/data-analysis/realtime/`

获取实时数据，包括最近1小时的交通数据、天气数据和平均速度。

**响应示例:**
```json
{
  "realtime_traffic": [
    {
      "id": 1,
      "timestamp": "2024-01-01T11:30:00Z",
      "location_lat": 39.9042,
      "location_lng": 116.4074,
      "intensity": 0.8,
      "traffic_count": 1200,
      "avg_speed": 45.5
    }
  ],
  "realtime_weather": {
    "id": 1,
    "timestamp": "2024-01-01T12:00:00Z",
    "weather_type": "晴",
    "temperature": 25.0,
    "humidity": 60.0,
    "wind_speed": 5.0
  },
  "current_avg_speed": 45.5,
  "last_updated": "2024-01-01T12:00:00Z"
}
```

## 数据模型

### TrafficData (交通数据)
- `timestamp`: 时间戳
- `location_lat`: 纬度
- `location_lng`: 经度
- `intensity`: 强度 (0-1)
- `traffic_count`: 客流量
- `avg_speed`: 平均速度

### VehicleTrajectory (车辆轨迹)
- `vehicle_id`: 车辆ID
- `timestamp`: 时间戳
- `location_lat`: 纬度
- `location_lng`: 经度
- `speed`: 速度
- `direction`: 方向

### WeatherData (天气数据)
- `timestamp`: 时间戳
- `weather_type`: 天气类型
- `temperature`: 温度
- `humidity`: 湿度
- `wind_speed`: 风速

### TrafficTrend (交通趋势)
- `date`: 日期
- `time_period`: 时间段
- `traffic_count`: 客流量

### DistanceDistribution (距离分布)
- `date`: 日期
- `distance_range`: 距离范围
- `count`: 数量

### DataScreenConfig (数据大屏配置)
- `name`: 配置名称
- `config_data`: 配置数据 (JSON)
- `is_active`: 是否激活
- `created_at`: 创建时间
- `updated_at`: 更新时间

## 错误处理

所有API在发生错误时会返回相应的HTTP状态码和错误信息：

```json
{
  "error": "错误描述信息"
}
```

常见状态码：
- `400`: 请求参数错误
- `401`: 未认证
- `403`: 权限不足
- `404`: 资源不存在
- `500`: 服务器内部错误

## 使用示例

### JavaScript/前端示例

```javascript
// 获取数据大屏数据
async function getDashboardData(date = null) {
  const url = date 
    ? `/api/data-analysis/dashboard/?date=${date}`
    : '/api/data-analysis/dashboard/';
  
  const response = await fetch(url, {
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  if (!response.ok) {
    throw new Error('获取数据失败');
  }
  
  return await response.json();
}

// 获取车辆轨迹
async function getVehicleTrajectory(vehicleId, startTime = null, endTime = null) {
  let url = `/api/data-analysis/trajectory/${vehicleId}/`;
  const params = new URLSearchParams();
  
  if (startTime) params.append('start_time', startTime);
  if (endTime) params.append('end_time', endTime);
  
  if (params.toString()) {
    url += `?${params.toString()}`;
  }
  
  const response = await fetch(url, {
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  return await response.json();
}

// 创建交通数据
async function createTrafficData(data) {
  const response = await fetch('/api/data-analysis/traffic-data/', {
    method: 'POST',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  });
  
  return await response.json();
}
```

### Python示例

```python
import requests

# 配置
BASE_URL = 'http://localhost:8000/api/data-analysis'
TOKEN = 'your_token_here'
HEADERS = {
    'Authorization': f'Token {TOKEN}',
    'Content-Type': 'application/json'
}

# 获取数据大屏数据
def get_dashboard_data(date=None):
    url = f'{BASE_URL}/dashboard/'
    params = {'date': date} if date else {}
    
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()

# 获取车辆轨迹
def get_vehicle_trajectory(vehicle_id, start_time=None, end_time=None):
    url = f'{BASE_URL}/trajectory/{vehicle_id}/'
    params = {}
    
    if start_time:
        params['start_time'] = start_time
    if end_time:
        params['end_time'] = end_time
    
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()

# 创建交通数据
def create_traffic_data(data):
    url = f'{BASE_URL}/traffic-data/'
    response = requests.post(url, headers=HEADERS, json=data)
    response.raise_for_status()
    return response.json()
```

## 测试数据生成

使用Django管理命令生成测试数据：

```bash
# 生成7天的测试数据
python manage.py generate_test_data --days 7

# 清除现有数据并重新生成
python manage.py generate_test_data --days 7 --clear
```

## 注意事项

1. 所有API都需要认证，请确保在请求头中包含有效的Token
2. 时间格式统一使用ISO 8601格式
3. 坐标使用WGS84坐标系
4. 大量数据查询时建议使用分页和日期范围限制
5. 实时数据接口返回最近1小时的数据，适合用于实时监控 