import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from app.logging_config import get_logger
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class ConnectionManager:
    """
    Manages all active WebSocket connections.

    Responsibilities:
      - Accept and register new connections.
      - Remove disconnected clients gracefully.
      - Broadcast JSON messages to all connected clients.
      - Send typed agent events via WsMessage factory methods.
      - Run a heartbeat ping loop to keep connections alive.
    """

    def __init__(self):
        # Active connections: websocket → client_id mapping
        self._connections: Dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = client_id
        logger.info("WebSocket client connected: %s (total=%d)", client_id, self.active_count)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the registry."""
        async with self._lock:
            client_id = self._connections.pop(websocket, "unknown")
        logger.info("WebSocket client disconnected: %s (total=%d)", client_id, self.active_count)

    async def broadcast(self, message: str) -> None:
        """
        Send a JSON string to all connected clients.
        Dead connections are silently removed.
        """
        if not self._connections:
            return

        dead: list[WebSocket] = []

        async with self._lock:
            connections_snapshot = list(self._connections.keys())

        for websocket in connections_snapshot:
            try:
                await websocket.send_text(message)
            except Exception:
                dead.append(websocket)

        # Clean up dead connections outside the send loop
        for websocket in dead:
            await self.disconnect(websocket)

    async def send_personal(self, websocket: WebSocket, message: str) -> None:
        """Send a message to a single specific client."""
        try:
            await websocket.send_text(message)
        except Exception:
            await self.disconnect(websocket)

    async def heartbeat_loop(self) -> None:
        """
        Periodically broadcast a ping frame to all clients.
        Interval is controlled by WS_HEARTBEAT_INTERVAL env var.
        Run this as a background task in the FastAPI lifespan.
        """
        from app.schemas.websocket import WsMessage
        interval = settings.ws_heartbeat_interval

        logger.info("WebSocket heartbeat loop started (interval=%ds)", interval)
        while True:
            await asyncio.sleep(interval)
            if self._connections:
                ping = WsMessage.ping()
                await self.broadcast(ping.to_json())
                logger.debug("Heartbeat ping sent to %d clients", self.active_count)


# ---------------------------------------------------------------------------
# Module-level singleton — imported by all agent nodes and the WS router.
# Instantiated once; shared across the entire FastAPI process lifetime.
# ---------------------------------------------------------------------------
manager = ConnectionManager()
