# 告警管理模块 API 总结

## 概述
告警管理模块实现了完整的告警生命周期管理，包括AI告警接收、告警列表查询、告警处理和实时WebSocket推送功能。

## API 接口

### 1. AI告警结果接收
- **URL**: `POST /api/alerts/ai-results/`
- **功能**: 接收AI服务发送的分析结果，保存为告警记录
- **权限**: 无需认证（内部API）
- **请求体**:
```json
{
    "camera_id": "camera_001",
    "event_type": "stranger_intrusion",
    "timestamp": "2024-01-01T12:00:00Z",
    "location": {"x": 100, "y": 200},
    "confidence": 0.95,
    "image_snapshot_url": "http://example.com/image.jpg",
    "video_clip_url": "http://example.com/video.mp4"
}
```
- **WebSocket推送**: 成功保存后自动推送到前端

### 2. 告警列表查询
- **URL**: `GET /api/alerts/list/`
- **功能**: 获取告警列表，支持筛选、排序、分页、搜索
- **权限**: 需要认证
- **查询参数**:
  - `page`: 页码
  - `page_size`: 每页数量（最大100）
  - `event_type`: 事件类型筛选
  - `status`: 状态筛选
  - `camera`: 摄像头ID筛选
  - `confidence__gte`: 置信度下限
  - `confidence__lte`: 置信度上限
  - `start_time`: 开始时间
  - `end_time`: 结束时间
  - `search`: 搜索关键词
  - `ordering`: 排序字段

### 3. 告警详情
- **URL**: `GET /api/alerts/{id}/`
- **功能**: 获取指定告警的详细信息
- **权限**: 需要认证

### 4. 告警处理
- **URL**: `PUT/PATCH /api/alerts/{id}/handle/`
- **功能**: 处理告警，更新状态和添加处理备注
- **权限**: 需要认证
- **请求体**:
```json
{
    "status": "in_progress",
    "processing_notes": "正在处理中..."
}
```
- **自动操作**: 自动设置处理人为当前用户
- **WebSocket推送**: 更新成功后推送通知

### 5. 告警信息更新
- **URL**: `PUT/PATCH /api/alerts/{id}/update/`
- **功能**: 更新告警的基本信息
- **权限**: 需要认证
- **请求体**:
```json
{
    "event_type": "fire_smoke",
    "location": {"x": 150, "y": 250},
    "confidence": 0.98,
    "image_snapshot_url": "http://example.com/new_image.jpg"
}
```
- **WebSocket推送**: 更新成功后推送通知

### 6. 告警统计
- **URL**: `GET /api/alerts/stats/`
- **功能**: 获取告警统计信息
- **权限**: 需要认证
- **响应**:
```json
{
    "total_alerts": 100,
    "pending_alerts": 25,
    "in_progress_alerts": 15,
    "resolved_alerts": 60,
    "recent_alerts": 10,
    "event_type_stats": {
        "stranger_intrusion": {"count": 30, "display_name": "陌生人入侵"},
        "fire_smoke": {"count": 20, "display_name": "明火烟雾"}
    }
}
```

## 数据模型

### Alert模型字段
- `id`: 主键
- `camera`: 关联摄像头（外键）
- `event_type`: 事件类型（选择字段）
- `timestamp`: 告警时间
- `location`: 位置信息（JSON字段）
- `confidence`: 置信度
- `image_snapshot_url`: 截图URL
- `video_clip_url`: 视频片段URL
- `status`: 状态（选择字段）
- `handler`: 处理人（外键）
- `processing_notes`: 处理备注
- `created_at`: 创建时间
- `updated_at`: 更新时间

### 事件类型选项
- `stranger_intrusion`: 陌生人入侵
- `person_fall`: 人员跌倒
- `fire_smoke`: 明火烟雾
- `stranger_face_detected`: 陌生人脸检测
- `spoofing_attack`: 活体欺骗攻击
- `abnormal_sound_scream`: 异常声音：尖叫
- `abnormal_sound_fight`: 异常声音：打架
- `abnormal_sound_glass_break`: 异常声音：玻璃破碎
- `other`: 其他异常

### 状态选项
- `pending`: 待处理
- `in_progress`: 处理中
- `resolved`: 已解决
- `ignored`: 已忽略

## WebSocket实时推送

### 连接地址
`ws://localhost:8000/ws/alerts/`

### 消息类型

#### 新告警通知
```json
{
    "type": "new_alert",
    "data": {
        "id": 123,
        "event_type": "stranger_intrusion",
        "timestamp": "2024-01-01T12:00:00Z",
        ...
    }
}
```

#### 告警更新通知
```json
{
    "type": "alert_update",
    "action": "handle",
    "data": {
        "id": 123,
        "status": "in_progress",
        ...
    }
}
```

#### 客户端消息
- 心跳检测: `{"type": "ping", "timestamp": "..."}`
- 订阅确认: `{"type": "subscribe"}`

## 使用示例

### 1. 获取告警列表（带筛选）
```bash
GET /api/alerts/list/?status=pending&event_type=stranger_intrusion&page=1&page_size=20
```

### 2. 处理告警
```bash
PUT /api/alerts/123/handle/
Content-Type: application/json

{
    "status": "resolved",
    "processing_notes": "已确认为误报，摄像头角度问题导致"
}
```

### 3. AI服务发送告警
```bash
POST /api/alerts/ai-results/
Content-Type: application/json

{
    "camera_id": "entrance_camera",
    "event_type": "stranger_intrusion",
    "location": {"zone": "entrance", "coordinates": [100, 200]},
    "confidence": 0.95,
    "image_snapshot_url": "http://storage.example.com/alerts/20240101_120000.jpg"
}
```

## 权限说明
- AI告警接收接口：无需认证（供内部AI服务调用）
- 其他所有接口：需要JWT认证
- 告警处理：自动记录处理人信息
- WebSocket连接：无需特殊权限验证

## 技术特性
- 支持分页、筛选、排序、搜索
- 实时WebSocket推送
- 自动设置处理人
- 完整的数据验证
- 事务安全的数据操作
- 性能优化的查询（select_related） 