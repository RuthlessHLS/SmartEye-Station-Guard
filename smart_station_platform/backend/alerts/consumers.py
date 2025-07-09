# backend/alerts/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer

class AlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 将新的连接加入到名为 'alerts_group' 的组中
        await self.channel_layer.group_add(
            'alerts_group',
            self.channel_name
        )
        await self.accept()
        print(f"WebSocket连接已建立: {self.channel_name}")

    async def disconnect(self, close_code):
        # 当连接关闭时，将其从组中移除
        await self.channel_layer.group_discard(
            'alerts_group',
            self.channel_name
        )
        print(f"WebSocket连接已断开: {self.channel_name}")

    # 从组接收消息
    async def alert_message(self, event):
        alert_data = event['message']  # 使用'message'而不是'data'
        # 你的前端代码需要一个 'type' 字段来识别消息类型
        message_to_send = {
            'type': 'alert',  # 告诉前端这是一条告警消息
            'data': alert_data
        }
        await self.send(text_data=json.dumps(message_to_send))
        print(f"已向 {self.channel_name} 发送告警: {alert_data.get('id', 'unknown')}")