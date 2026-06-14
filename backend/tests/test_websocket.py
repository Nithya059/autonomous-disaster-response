import json
import pytest
from fastapi.testclient import TestClient


def test_websocket_connects(client: TestClient):
    """Client can connect to /ws/stream and receives system_status ack."""
    with client.websocket_connect("/ws/stream?client_id=test-client") as ws:
        data = ws.receive_text()
        msg = json.loads(data)
        assert msg["type"] == "system_status"
        assert "test-client" in msg["message"]
        assert "run_id" in msg
        assert "timestamp" in msg


def test_websocket_message_schema(client: TestClient):
    """Connection ack message conforms to WsMessage schema."""
    with client.websocket_connect("/ws/stream") as ws:
        data = ws.receive_text()
        msg = json.loads(data)

        # Required fields per frozen WsMessage schema (File 18)
        assert "type" in msg
        assert "severity" in msg
        assert "message" in msg
        assert "run_id" in msg
        assert "timestamp" in msg

        # Optional fields present but may be null
        assert "agent" in msg
        assert "step" in msg
        assert "payload" in msg


def test_websocket_pong_response(client: TestClient):
    """Client can send pong without error after receiving ping."""
    with client.websocket_connect("/ws/stream") as ws:
        # Consume the connection ack
        ws.receive_text()

        # Send pong — server should not crash
        ws.send_text("pong")
        # No response expected — test passes if no exception raised


def test_websocket_auto_client_id(client: TestClient):
    """Connection without client_id query param still succeeds."""
    with client.websocket_connect("/ws/stream") as ws:
        data = ws.receive_text()
        msg = json.loads(data)
        assert msg["type"] == "system_status"
        assert "Connected" in msg["message"]


def test_health_endpoint(client: TestClient):
    """GET /health returns 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "ws_connections" in body
