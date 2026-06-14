import json
from datetime import datetime, timezone

from app.agents.state import GraphState
from app.models.incident import Incident
from app.schemas.websocket import WsMessage
from app.logging_config import get_logger

logger = get_logger(__name__)

AGENT_NAME = "prioritization"

# Scoring weights — must sum to 1.0
SEVERITY_WEIGHT = 0.45
CONFIDENCE_WEIGHT = 0.30
RECENCY_WEIGHT = 0.25

SEVERITY_SCORES = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.45,
    "low": 0.20,
}

STATUS_PRIORITY = {
    "new": 1.0,
    "verified": 0.9,
    "prioritized": 0.5,
    "allocated": 0.2,
    "resolved": 0.0,
}


def _recency_score(created_at_str: str) -> float:
    """
    Score recency: incidents created within the last hour score 1.0,
    decaying linearly to 0.0 at 24 hours.
    """
    try:
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_hours = (now - created_at).total_seconds() / 3600
        return max(0.0, 1.0 - (age_hours / 24.0))
    except Exception:
        return 0.5


def _compute_priority_score(incident: dict) -> float:
    """
    Compute a composite priority score in range 0.0–1.0.
    Higher score = higher dispatch priority.
    """
    severity_score = SEVERITY_SCORES.get(incident.get("severity", "low"), 0.2)
    confidence_score = float(incident.get("confidence", 0.5))
    recency_score = _recency_score(incident.get("created_at", datetime.now(timezone.utc).isoformat()))

    # Deprioritize already-allocated or resolved incidents
    status_multiplier = STATUS_PRIORITY.get(incident.get("status", "new"), 0.5)

    raw_score = (
        (severity_score * SEVERITY_WEIGHT)
        + (confidence_score * CONFIDENCE_WEIGHT)
        + (recency_score * RECENCY_WEIGHT)
    )

    return round(raw_score * status_multiplier, 4)


async def prioritization_agent(state: GraphState) -> GraphState:
    """
    LangGraph node: Prioritization Agent.

    Responsibilities:
      1. Score each verified incident using severity, confidence, and recency.
      2. Sort incidents by priority score descending.
      3. Persist updated status to database.
      4. Populate state["prioritized"] for the allocation agent.
    """
    run_id = state["run_id"]
    db = state["db_session"]
    trace: list[dict] = state["agent_trace"]
    verified = state["verified"]

    from app.services.websocket_manager import manager

    def _emit(step: str, message: str, severity="info", payload=None):
        msg = WsMessage.agent_event(
            agent=AGENT_NAME,
            step=step,
            message=message,
            run_id=run_id,
            severity=severity,
            payload=payload,
        )
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.broadcast(msg.to_json()))
        except RuntimeError:
            pass

        trace.append({
            "agent_name": AGENT_NAME,
            "step": step,
            "message": message,
            "severity": severity,
            "payload_json": json.dumps(payload) if payload else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
        })
        logger.info("[%s] %s — %s", AGENT_NAME, step, message)

    _emit("start", f"Prioritization agent started. Scoring {len(verified)} incidents.")

    if not verified:
        _emit("skip", "No verified incidents to prioritize.", severity="warning")
        return {**state, "prioritized": [], "agent_trace": trace}

    scored = []
    for incident in verified:
        score = _compute_priority_score(incident)
        scored.append({**incident, "priority_score": score})
        _emit(
            "scored",
            f"'{incident.get('title')}' priority_score={score:.4f}",
            payload={
                "incident_id": incident.get("id"),
                "priority_score": score,
                "severity": incident.get("severity"),
                "confidence": incident.get("confidence"),
            },
        )

    # Sort descending by priority score
    prioritized = sorted(scored, key=lambda x: x["priority_score"], reverse=True)

    _emit(
        "sorted",
        f"Incidents ranked. Top: '{prioritized[0].get('title')}' "
        f"(score={prioritized[0].get('priority_score'):.4f})",
        payload={"top_incident_id": prioritized[0].get("id")},
    )

    # Persist status update to DB
    for incident in prioritized:
        inc_id = incident.get("id")
        if inc_id and incident.get("status") == "verified":
            try:
                db_inc = db.query(Incident).filter(Incident.id == inc_id).first()
                if db_inc:
                    db_inc.status = "prioritized"
                    db.flush()
            except Exception as exc:
                logger.warning(
                    "[%s] Failed to update incident %s status: %s", AGENT_NAME, inc_id, exc
                )

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        _emit("db_error", f"Failed to persist prioritization: {exc}", severity="error")

    _emit(
        "complete",
        f"Prioritization complete. {len(prioritized)} incidents ranked.",
        severity="success",
        payload={"prioritized_count": len(prioritized)},
    )

    return {**state, "prioritized": prioritized, "agent_trace": trace}
