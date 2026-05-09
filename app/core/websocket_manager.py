from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
from app.core.logger import logger


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str = "default"):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        logger.info(f"WebSocket连接已建立: channel={channel}, total={len(self.active_connections[channel])}")

    def disconnect(self, websocket: WebSocket, channel: str = "default"):
        if channel in self.active_connections and websocket in self.active_connections[channel]:
            self.active_connections[channel].remove(websocket)
            logger.info(f"WebSocket连接已断开: channel={channel}, remaining={len(self.active_connections[channel])}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送个人消息失败: {str(e)}")

    async def broadcast(self, message: dict, channel: str = "default"):
        if channel not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"广播消息失败: {str(e)}")
                disconnected.append(connection)
        
        for connection in disconnected:
            self.disconnect(connection, channel)

    def get_connection_count(self, channel: str = "default") -> int:
        if channel not in self.active_connections:
            return 0
        return len(self.active_connections[channel])


manager = ConnectionManager()
