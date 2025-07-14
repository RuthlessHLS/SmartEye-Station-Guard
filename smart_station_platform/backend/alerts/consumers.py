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
        print(f"WebSocket连接已断开: {self.channel_name} (关闭代码: {close_code})")

    # 接收新告警消息
    async def alert_message(self, event):
        alert_data = event['message']
        # 发送新告警通知到前端
        message_to_send = {
            'type': 'new_alert',  # 告诉前端这是新告警消息
            'data': alert_data
        }
        await self.send(text_data=json.dumps(message_to_send))
        print(f"已向 {self.channel_name} 发送新告警: {alert_data.get('id', 'unknown')}")

    # 接收告警更新消息
    async def alert_update_message(self, event):
        update_data = event['message']
        # 发送告警更新通知到前端
        message_to_send = {
            'type': 'alert_update',  # 告诉前端这是告警更新消息
            'action': update_data.get('action', 'update'),  # handle 或 update
            'data': update_data.get('alert', {})
        }
        await self.send(text_data=json.dumps(message_to_send))
        print(f"已向 {self.channel_name} 发送告警更新: {update_data.get('alert', {}).get('id', 'unknown')} - {update_data.get('action', 'update')}")

    async def broadcast_message(self, event):
        """
        处理从后端视图（例如 WebSocketBroadcastView）发来的通用广播消息。
        """
        message_data = event['message']
        # 将收到的完整消息直接发送到前端
        await self.send(text_data=json.dumps(message_data))
        # 可选：在后端日志中打印一条确认信息
        message_type = message_data.get("type", "unknown")
        print(f"已向 {self.channel_name} 广播实时消息: {message_type}")

    # 接收来自WebSocket的消息（前端发送的）
    async def receive(self, text_data):
        # 【修复】处理前端可能发送的纯文本 "ping"
        if text_data == "ping":
            await self.send(text_data=json.dumps({'type': 'pong'}))
            return

        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', '')
            
            if message_type == 'ping':
                # 响应心跳检测
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': text_data_json.get('timestamp', '')
                }))
            elif message_type == 'subscribe':
                # 处理订阅请求（如果需要）
                await self.send(text_data=json.dumps({
                    'type': 'subscription_confirmed',
                    'message': '已成功订阅告警通知'
                }))
            else:
                print(f"收到未知消息类型: {message_type}")
                
        except json.JSONDecodeError:
            print(f"收到无效的JSON数据: {text_data}")
        except Exception as e:
            print(f"处理WebSocket消息时发生错误: {e}")