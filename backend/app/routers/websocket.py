import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket_manager import manager
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/stream")
async def websocket_stream(
    websocket: WebSocket,
    client_id: str = Query(default=None),
):
    """
    WebSocket endpoint — /ws/stream

    Clients connect here to receive real-time events:
      - agent_event: step-by-step agent thought stream
      - incident_update: new or updated incident payload
      - resource_update: new or updated resource payload
      - alert_sent: outbound alert notification
      - ping: heartbeat keepalive
      - system_status: pipeline run summary

    Query param:
      client_id (optional): human-readable identifier for logging.
                            Auto-assigned UUID if omitted.

    Message format: JSON string conforming to WsMessage schema (schemas/websocket.py).
    """
    if not client_id:
        client_id = str(uuid.uuid4())[:8]

    await manager.connect(websocket, client_id)

    # Send immediate connection acknowledgment
    from app.schemas.websocket import WsMessage
    ack = WsMessage.system_status(
        message=f"Connected to Disaster Response stream. Client ID: {client_id}",
        payload={"client_id": client_id},
    )
    await manager.send_personal(websocket, ack.to_json())

    try:
        while True:
            # Keep the connection alive by receiving messages.
            # Clients may send "pong" in response to server "ping".
            data = await websocket.receive_text()
            if data == "pong":
                logger.debug("Pong received from client %s", client_id)
            # All other client → server messages are ignored in MVP.
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        logger.info("Client %s disconnected cleanly", client_id)
    except Exception as exc:
        logger.warning("WebSocket error for client %s: %s", client_id, exc)
        await manager.disconnect(websocket)
