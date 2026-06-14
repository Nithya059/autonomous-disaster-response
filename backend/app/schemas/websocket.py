from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_serializer
import json


# ---------------------------------------------------------------------------
# Canonical WebSocket message envelope — frozen contract.
# Both backend (websocket_manager.py) and frontend (useWebSocket.js)
# must conform to this exact shape. Never alter field names or types
# without a corresponding frontend update.
# ---------------------------------------------------------------------------

AgentName = Literal[
    "ingestion",
    "verification",
    "prioritization",
    "allocation",
    "communication",
]

MessageType = Literal[
    "agent_event",
    "incident_update",
    "resource_update",
    "alert_sent",
    "ping",
    "system_status",
]

SeverityLevel = Literal["info", "warning", "error", "success"]


class WsMessage(BaseModel):
    type: MessageType
    agent: Optional[AgentName] = None
    step: Optional[str] = None
    severity: SeverityLevel = "info"
    message: str
    payload: Optional[dict] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    run_id: str

    def to_json(self) -> str:
        """Serialize to JSON string for WebSocket transmission."""
        return self.model_dump_json()

    @classmethod
    def ping(cls, run_id: str = "system") -> "WsMessage":
        """Factory: create a ping keepalive message."""
        return cls(
            type="ping",
            agent=None,
            step=None,
            severity="info",
            message="ping",
            payload=None,
            run_id=run_id,
        )

    @classmethod
    def system_status(cls, message: str, payload: Optional[dict] = None) -> "WsMessage":
        """Factory: create a system status broadcast."""
        return cls(
            type="system_status",
            agent=None,
            step="system",
            severity="info",
            message=message,
            payload=payload,
            run_id="system",
        )

    @classmethod
    def agent_event(
        cls,
        agent: AgentName,
        step: str,
        message: str,
        run_id: str,
        severity: SeverityLevel = "info",
        payload: Optional[dict] = None,
    ) -> "WsMessage":
        """Factory: create an agent execution event message."""
        return cls(
            type="agent_event",
            agent=agent,
            step=step,
            severity=severity,
            message=message,
            payload=payload,
            run_id=run_id,
        )

    @classmethod
    def incident_update(
        cls,
        run_id: str,
        payload: dict,
        message: str = "Incident updated",
    ) -> "WsMessage":
        """Factory: create an incident state update broadcast."""
        return cls(
            type="incident_update",
            agent=None,
            step=None,
            severity="info",
            message=message,
            payload=payload,
            run_id=run_id,
        )

    @classmethod
    def resource_update(
        cls,
        run_id: str,
        payload: dict,
        message: str = "Resource updated",
    ) -> "WsMessage":
        """Factory: create a resource state update broadcast."""
        return cls(
            type="resource_update",
            agent=None,
            step=None,
            severity="info",
            message=message,
            payload=payload,
            run_id=run_id,
        )

    @classmethod
    def alert_sent(
        cls,
        run_id: str,
        payload: dict,
        message: str,
    ) -> "WsMessage":
        """Factory: create an outbound alert notification."""
        return cls(
            type="alert_sent",
            agent="communication",
            step="send_alert",
            severity="success",
            message=message,
            payload=payload,
            run_id=run_id,
)
