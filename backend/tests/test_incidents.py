import pytest
from fastapi.testclient import TestClient


def test_list_incidents_empty(client: TestClient):
    """GET /incidents returns empty list when DB is empty."""
    response = client.get("/incidents")
    assert response.status_code == 200
    assert response.json() == []


def test_list_incidents_seeded(client: TestClient, seeded_db):
    """GET /incidents returns seeded incidents."""
    response = client.get("/incidents")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 8
    assert all("id" in inc for inc in data)
    assert all("severity" in inc for inc in data)


def test_create_incident(client: TestClient, mock_incident_data: dict):
    """POST /incidents creates and returns a new incident."""
    response = client.post("/incidents", json=mock_incident_data)
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == mock_incident_data["title"]
    assert body["type"] == "flood"
    assert body["severity"] == "high"
    assert body["status"] == "new"
    assert body["confidence"] == 0.0
    assert "id" in body
    assert "created_at" in body


def test_create_incident_invalid_type(client: TestClient, mock_incident_data: dict):
    """POST /incidents with invalid type returns 422."""
    mock_incident_data["type"] = "tornado"
    response = client.post("/incidents", json=mock_incident_data)
    assert response.status_code == 422


def test_create_incident_invalid_severity(client: TestClient, mock_incident_data: dict):
    """POST /incidents with invalid severity returns 422."""
    mock_incident_data["severity"] = "extreme"
    response = client.post("/incidents", json=mock_incident_data)
    assert response.status_code == 422


def test_get_incident_by_id(client: TestClient, mock_incident_data: dict):
    """GET /incidents/{id} returns the correct incident."""
    create_resp = client.post("/incidents", json=mock_incident_data)
    incident_id = create_resp.json()["id"]

    response = client.get(f"/incidents/{incident_id}")
    assert response.status_code == 200
    assert response.json()["id"] == incident_id


def test_get_incident_not_found(client: TestClient):
    """GET /incidents/9999 returns 404."""
    response = client.get("/incidents/9999")
    assert response.status_code == 404


def test_update_incident(client: TestClient, mock_incident_data: dict):
    """PATCH /incidents/{id} updates specified fields only."""
    create_resp = client.post("/incidents", json=mock_incident_data)
    incident_id = create_resp.json()["id"]

    response = client.patch(
        f"/incidents/{incident_id}",
        json={"status": "verified", "confidence": 0.85},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["confidence"] == 0.85
    assert body["title"] == mock_incident_data["title"]  # unchanged


def test_delete_incident(client: TestClient, mock_incident_data: dict):
    """DELETE /incidents/{id} removes the incident."""
    create_resp = client.post("/incidents", json=mock_incident_data)
    incident_id = create_resp.json()["id"]

    response = client.delete(f"/incidents/{incident_id}")
    assert response.status_code == 204

    # Confirm gone
    get_resp = client.get(f"/incidents/{incident_id}")
    assert get_resp.status_code == 404


def test_filter_incidents_by_severity(client: TestClient, seeded_db):
    """GET /incidents?severity=critical returns only critical incidents."""
    response = client.get("/incidents?severity=critical")
    assert response.status_code == 200
    data = response.json()
    assert all(inc["severity"] == "critical" for inc in data)
