# 摄像头管理模块

## 概述

摄像头管理模块是智慧车站智能监控与大数据分析平台的核心组件之一，负责管理摄像头设备和危险区域配置。该模块提供了完整的RESTful API接口，支持摄像头和危险区域的增删改查操作。

## 功能特性

### 摄像头管理
- ✅ 摄像头信息的增删改查
- ✅ 摄像头状态管理（启用/禁用）
- ✅ 支持按名称、位置、状态筛选
- ✅ 获取启用的摄像头列表
- ✅ 摄像头详情包含关联的危险区域

### 危险区域管理
- ✅ 危险区域的增删改查
- ✅ 多边形坐标配置（JSON格式）
- ✅ 告警阈值设置（距离阈值、时间阈值）
- ✅ 区域状态管理（启用/禁用）
- ✅ 支持按摄像头、名称、状态筛选
- ✅ 获取指定摄像头的危险区域
- ✅ 获取启用的危险区域列表

## 数据模型

### Camera（摄像头）
```python
class Camera(models.Model):
    name = models.CharField(max_length=100, unique=True)  # 摄像头名称
    rtsp_url = models.URLField()  # RTSP流地址
    location_desc = models.CharField(max_length=255)  # 位置描述
    is_active = models.BooleanField(default=True)  # 是否启用
    created_at = models.DateTimeField(auto_now_add=True)  # 创建时间
    updated_at = models.DateTimeField(auto_now=True)  # 更新时间
```

### DangerousArea（危险区域）
```python
class DangerousArea(models.Model):
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)  # 关联摄像头
    name = models.CharField(max_length=100)  # 区域名称
    coordinates = JSONField()  # 多边形坐标
    min_distance_threshold = models.FloatField()  # 距离阈值（米）
    time_in_area_threshold = models.IntegerField()  # 时间阈值（秒）
    is_active = models.BooleanField(default=True)  # 是否启用
    created_at = models.DateTimeField(auto_now_add=True)  # 创建时间
    updated_at = models.DateTimeField(auto_now=True)  # 更新时间
```

## API 接口

### 摄像头管理接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/cameras/` | 获取摄像头列表 |
| POST | `/api/cameras/` | 创建摄像头 |
| GET | `/api/cameras/{id}/` | 获取摄像头详情 |
| PUT | `/api/cameras/{id}/` | 更新摄像头 |
| PATCH | `/api/cameras/{id}/` | 部分更新摄像头 |
| DELETE | `/api/cameras/{id}/` | 删除摄像头 |
| POST | `/api/cameras/{id}/toggle_status/` | 切换摄像头状态 |
| GET | `/api/cameras/active_cameras/` | 获取启用的摄像头 |

### 危险区域管理接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/cameras/dangerous-areas/` | 获取危险区域列表 |
| POST | `/api/cameras/dangerous-areas/` | 创建危险区域 |
| GET | `/api/cameras/dangerous-areas/{id}/` | 获取危险区域详情 |
| PUT | `/api/cameras/dangerous-areas/{id}/` | 更新危险区域 |
| PATCH | `/api/cameras/dangerous-areas/{id}/` | 部分更新危险区域 |
| DELETE | `/api/cameras/dangerous-areas/{id}/` | 删除危险区域 |
| POST | `/api/cameras/dangerous-areas/{id}/toggle_status/` | 切换危险区域状态 |
| GET | `/api/cameras/dangerous-areas/by_camera/` | 获取指定摄像头的危险区域 |
| GET | `/api/cameras/dangerous-areas/active_areas/` | 获取启用的危险区域 |

## 使用示例

### 1. 创建摄像头
```bash
curl -X POST http://localhost:8000/api/cameras/ \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "车站入口摄像头",
    "rtsp_url": "rtsp://192.168.1.100:554/stream",
    "location_desc": "车站主入口",
    "is_active": true
  }'
```

### 2. 创建危险区域
```bash
curl -X POST http://localhost:8000/api/cameras/dangerous-areas/ \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "camera": 1,
    "name": "禁止区域1",
    "coordinates": [[100, 100], [200, 100], [200, 200], [100, 200]],
    "min_distance_threshold": 0.5,
    "time_in_area_threshold": 30,
    "is_active": true
  }'
```

### 3. 获取摄像头详情（包含危险区域）
```bash
curl -X GET http://localhost:8000/api/cameras/1/ \
  -H "Authorization: Bearer <your_jwt_token>"
```

### 4. 切换摄像头状态
```bash
curl -X POST http://localhost:8000/api/cameras/1/toggle_status/ \
  -H "Authorization: Bearer <your_jwt_token>"
```

## 查询参数

### 摄像头列表筛选
- `name`: 按名称搜索（模糊匹配）
- `location`: 按位置描述搜索（模糊匹配）
- `is_active`: 按启用状态筛选（true/false）

### 危险区域列表筛选
- `camera_id`: 按摄像头ID筛选
- `name`: 按区域名称搜索（模糊匹配）
- `is_active`: 按启用状态筛选（true/false）

## 坐标格式

危险区域的坐标使用JSON格式存储，格式为二维数组：
```json
[
  [x1, y1],
  [x2, y2],
  [x3, y3],
  [x4, y4]
]
```

- 每个坐标点是一个包含 [x, y] 的数组
- 至少需要3个坐标点才能形成多边形
- 坐标值必须是数字类型

## 权限要求

所有API接口都需要JWT认证，请在请求头中包含：
```
Authorization: Bearer <your_jwt_token>
```

## 错误处理

### 常见错误码
- `400 Bad Request`: 请求数据验证失败
- `401 Unauthorized`: 未提供有效的JWT令牌
- `404 Not Found`: 请求的资源不存在
- `500 Internal Server Error`: 服务器内部错误

### 错误响应格式
```json
{
  "error": "错误描述信息"
}
```

## 测试

运行测试用例：
```bash
cd smart_station_platform/backend
python manage.py test camera_management
```

## 管理界面

该模块提供了Django管理界面支持，可以在 `/admin/` 路径下管理摄像头和危险区域。

## 依赖

- Django 5.2+
- Django REST Framework 3.14+
- Django REST Framework Simple JWT 5.2+

## 文件结构

```
camera_management/
├── __init__.py
├── admin.py          # Django管理界面配置
├── apps.py           # 应用配置
├── models.py         # 数据模型定义
├── serializers.py    # API序列化器
├── urls.py           # URL路由配置
├── views.py          # API视图
├── tests.py          # 测试用例
├── migrations/       # 数据库迁移文件
├── API_DOCS.md       # 详细API文档
└── README.md         # 模块说明文档
```

## 开发说明

### 添加新字段
1. 在 `models.py` 中添加字段
2. 运行 `python manage.py makemigrations`
3. 运行 `python manage.py migrate`
4. 更新 `serializers.py` 中的序列化器
5. 更新测试用例

### 添加新API接口
1. 在 `views.py` 中添加视图方法
2. 在 `urls.py` 中添加URL路由
3. 添加相应的测试用例
4. 更新API文档

## 联系信息

如有问题或建议，请联系开发团队。 