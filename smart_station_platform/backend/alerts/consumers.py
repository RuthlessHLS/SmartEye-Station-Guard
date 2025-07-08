# G:\Web\smart_station_platform\backend\alerts\consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer

class AlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 所有告警都发送到这个组
        self.group_name = 'alerts_group'

        # 将当前通道加入组
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept() # 接受 WebSocket 连接

    async def disconnect(self, close_code):
        # 将当前通道从组中移除
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # 接收WebSocket消息 (前端发来的，目前可能不需要处理)
    async def receive(self, text_data):
        # 暂时不处理前端发来的消息，主要用于后端主动推送
        pass

    # 接收来自Channels组的消息 (后端其他地方通过channel_layer.group_send发送)
    async def send_alert_message(self, event):
        message = event['message']
        # 发送消息给WebSocket客户端
        await self.send(text_data=json.dumps({
            'type': 'alert', # 消息类型
            'data': message  # 实际告警数据
        }))