import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("pulseboard.websocket")
router = APIRouter(prefix="/ws", tags=["websocket"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        logger.info(f"Broadcasting message: {message} to {len(self.active_connections)} clients")
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error sending message to client, removing: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

@router.websocket("")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Broadcast updated user count after a new connection
    await manager.broadcast({"type": "user_count", "count": len(manager.active_connections)})
    try:
        while True:
            # Maintain connection, reply to ping messages to avoid timeouts
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # Broadcast updated user count after a disconnection
        await manager.broadcast({"type": "user_count", "count": len(manager.active_connections)})
    except Exception as e:
        logger.warning(f"WebSocket disconnected with error: {e}")
        manager.disconnect(websocket)
        # Broadcast updated user count after a disconnection
        await manager.broadcast({"type": "user_count", "count": len(manager.active_connections)})
