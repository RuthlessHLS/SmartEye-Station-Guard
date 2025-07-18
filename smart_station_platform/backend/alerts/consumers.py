# backend/alerts/consumers.py

import json
import logging
from datetime import datetime
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

# 获取应用日志记录器
logger = logging.getLogger('alerts')

# 添加自定义JSON编码器处理datetime对象
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class AlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # camera_id may be optional; default to 'all' when not provided
        self.camera_id = self.scope['url_route']['kwargs'].get('camera_id', 'all')
        self.group_name = f"camera_{self.camera_id}"

        # 将客户端加入摄像头对应的组
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"WebSocket客户端已连接到摄像头组: {self.camera_id}")
        await self.send(json.dumps({
            'type': 'subscription_confirmed',
            'camera_id': self.camera_id,
            'group': self.group_name
        }, cls=DateTimeEncoder))  # 使用自定义编码器

    async def disconnect(self, close_code):
        # 当客户端断开连接时，将其从组中移除
        logger.info(f"WebSocket客户端已从摄像头组断开: {self.camera_id}, 关闭代码: {close_code}")
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # 接收客户端发送的消息
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', 'unknown')

            # 处理不同类型的消息，但忽略心跳消息的日志
            if message_type == 'ping':
                await self.send(json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                }, cls=DateTimeEncoder))
            elif message_type == 'subscribe':
                new_camera_id = text_data_json.get('camera_id')
                if new_camera_id and new_camera_id != self.camera_id:
                    # 如果客户端请求订阅新的摄像头，先从旧组中移除
                    logger.info(f"客户端请求更改订阅: {self.camera_id} -> {new_camera_id}")
                    await self.channel_layer.group_discard(
                        self.group_name,
                        self.channel_name
                    )
                    # 更新摄像头ID和组名
                    self.camera_id = new_camera_id
                    self.group_name = f"camera_{self.camera_id}"
                    # 添加到新组
                    await self.channel_layer.group_add(
                        self.group_name,
                        self.channel_name
                    )
                    # 发送确认消息
                    await self.send(json.dumps({
                        'type': 'subscription_confirmed',
                        'camera_id': self.camera_id,
                        'group': self.group_name
                    }, cls=DateTimeEncoder))
            else:
                # 记录非标准消息类型
                logger.debug(f"收到客户端消息: 类型={message_type}")
        except json.JSONDecodeError:
            logger.error(f"接收到无效的JSON消息: {text_data[:100]}...")
        except Exception as e:
            logger.error(f"处理WebSocket消息时出错: {str(e)}")

    # 以下是可以通过channel_layer触发的处理程序

    async def detection_result(self, event):
        # 将检测结果广播给客户端
        try:
            # 提取数据部分
            data = event.get('data', {})
            # 发送给客户端，但不记录日志以减少干扰
            await self.send(json.dumps({
                'type': 'detection_result',
                'data': data
            }, cls=DateTimeEncoder))
        except Exception as e:
            logger.error(f"发送检测结果时出错: {str(e)}")

    async def new_alert(self, event):
        # 将告警广播给客户端
        try:
            alert_data = event.get('data', {})
            logger.info(f"[BROADCAST] Sending new alert to WebSocket client: {alert_data.get('event_type', 'unknown')}")
            await self.send(json.dumps({
                'type': 'new_alert',
                'data': alert_data
            }, cls=DateTimeEncoder))
        except Exception as e:
            logger.error(f"[ERROR] Failed to send alert: {str(e)}")

    async def stream_initialized(self, event):
        # 将视频流初始化消息广播给客户端
        try:
            stream_data = event.get('data', {})
            logger.info(f"发送流初始化消息: camera_id={stream_data.get('camera_id')}")
            await self.send(json.dumps({
                'type': 'stream_initialized',
                'data': stream_data
            }, cls=DateTimeEncoder))
        except Exception as e:
            logger.error(f"发送流初始化消息时出错: {str(e)}")

    async def broadcast_message(self, event):
        # 通用广播处理程序
        try:
            message = event.get('message', {})
            # 仅记录非心跳消息和重要消息类型的日志
            message_type = message.get('type', '')
            if message_type not in ['ping', 'pong'] and message_type != 'detection_result':
                logger.info(f"广播消息: 类型={message_type}")
            # 使用自定义编码器处理datetime
            await self.send(json.dumps(message, cls=DateTimeEncoder))
        except Exception as e:
            logger.error(f"广播消息时出错: {str(e)}")

    async def throttled_alert(self, event):
        """处理被节流的告警消息"""
        try:
            alert_data = event.get('data', {})
            logger.info(f"[THROTTLED] Sending throttled alert: {event.get('message', 'Alert was throttled')}")
            await self.send(json.dumps({
                'type': 'throttled_alert',
                'data': alert_data,
                'message': event.get('message', '告警被节流')
            }, cls=DateTimeEncoder))
        except Exception as e:
            logger.error(f"[ERROR] Failed to send throttled alert: {str(e)}")

    async def alert_update(self, event):
        """Handle alert update events (status changes, edits)"""
        try:
            alert_data = event.get('data', {}) or event.get('message', {})
            # Log only important info
            logger.info(f"[UPDATE] Sending alert update to WebSocket client: {alert_data.get('id', 'unknown')}")
            await self.send(json.dumps({
                'type': 'alert_update',
                'data': alert_data
            }, cls=DateTimeEncoder))
        except Exception as e:
            logger.error(f"[ERROR] Failed to send alert update: {str(e)}")