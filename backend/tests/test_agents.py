import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.agents.state import GraphState
from app.agents.prioritization_agent import (
    prioritization_agent,
    _compute_priority_score,
    _recency_score,
)
from app.agents.verification_agent import _rule_based_confidence
from app.services.geo_service import haversine, nearest_resources


# ---------------------------------------------------------------------------
# geo_service unit tests
# ---------------------------------------------------------------------------

def test_haversine_same_point():
    """Distance from a point to itself is 0."""
    assert haversine(14.5995, 120.9842, 14.5995, 120.9842) == 0.0


def test_haversine_known_distance():
    """Manila to Cebu is approximately 580km."""
    dist = haversine(14.5995, 120.9842, 10.3157, 123.8854)
    assert 550 < dist < 620


def test_nearest_resources_empty():
    """Returns empty list when resource pool is empty."""
    result = nearest_resources(14.5, 120.9, [], preferred_types=["rescue"])
    assert result == []


def test_nearest_resources_max_distance():
    """Excludes resources beyond max_distance_km."""
    mock_resource = MagicMock()
    mock_resource.lat = 35.6762   # Tokyo
    mock_resource.lng = 139.6503
    mock_resource.type = "rescue"

    result = nearest_resources(
        14.5995, 120.9842,  # Manila
        [mock_resource],
        max_distance_km=100.0,
    )
    assert result == []


def test_nearest_resources_preference():
    """Prefers resources matching preferred_types."""
    rescue = MagicMock()
    rescue.lat = 14.61
    rescue.lng = 120.99
    rescue.type = "rescue"

    medical = MagicMock()
    medical.lat = 14.60
    medical.lng = 120.98
    medical.type = "medical"

    # medical is slightly closer but rescue is preferred
    result = nearest_resources(
        14.5995, 120.9842,
        [rescue, medical],
        preferred_types=["rescue", "medical"],
        top_n=2,
    )
    assert len(result) == 2
    # First result should be rescue (preferred type index 0)
    assert result[0][0].type == "rescue"


# ---------------------------------------------------------------------------
# verification_agent unit tests
# ---------------------------------------------------------------------------

def test_rule_based_confidence_gdacs():
    """GDACS source gets highest source credibility."""
    inc = {"source": "gdacs", "severity": "critical", "type": "flood"}
    score = _rule_based_confidence(inc)
    assert score > 0.5


def test_rule_based_confidence_unknown_source():
    """Unknown source gets lower confidence."""
    inc = {"source": "unknown_blog", "severity": "low", "type": "other"}
    score = _rule_based_confidence(inc)
    assert score < 0.5


# ---------------------------------------------------------------------------
# prioritization_agent unit tests
# ---------------------------------------------------------------------------

def test_recency_score_recent():
    """Very recent incident scores close to 1.0."""
    now = datetime.now(timezone.utc).isoformat()
    score = _recency_score(now)
    assert score > 0.95


def test_recency_score_old():
    """Incident older than 24h scores 0.0."""
    old = "2020-01-01T00:00:00+00:00"
    score = _recency_score(old)
    assert score == 0.0


def test_compute_priority_score_critical_high():
    """Critical severity recent incident scores > 0.7."""
    inc = {
        "severity": "critical",
        "confidence": 0.9,
        "status": "verified",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    score = _compute_priority_score(inc)
    assert score > 0.7


def test_compute_priority_score_low_old():
    """Low severity old incident scores < 0.2."""
    inc = {
        "severity": "low",
        "confidence": 0.3,
        "status": "new",
        "created_at": "2020-01-01T00:00:00+00:00",
    }
    score = _compute_priority_score(inc)
    assert score < 0.2


@pytest.mark.asyncio
async def test_prioritization_agent_sorts_by_score(seeded_db):
    """Prioritization agent returns incidents sorted by priority_score descending."""
    verified_incidents = [
        {
            "id": 1,
            "title": "Low severity old",
            "severity": "low",
            "confidence": 0.3,
            "status": "verified",
            "created_at": "2020-01-01T00:00:00+00:00",
            "type": "other",
            "lat": 14.5,
            "lng": 120.9,
        },
        {
            "id": 2,
            "title": "Critical recent",
            "severity": "critical",
            "confidence": 0.9,
            "status": "verified",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "flood",
            "lat": 14.6,
            "lng": 121.0,
        },
    ]

    state: GraphState = {
        "run_id": "test-run-001",
        "raw_incidents": [],
        "verified": verified_incidents,
        "prioritized": [],
        "allocations": [],
        "alerts": [],
        "agent_trace": [],
        "db_session": seeded_db,
    }

    with patch("app.agents.prioritization_agent.manager") as mock_manager:
        mock_manager.broadcast = AsyncMock()
        result = await prioritization_agent(state)

    prioritized = result["prioritized"]
    assert len(prioritized) == 2
    assert prioritized[0]["title"] == "Critical recent"
    assert prioritized[0]["priority_score"] > prioritized[1]["priority_score"]
