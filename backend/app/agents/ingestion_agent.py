import json
import logging
from datetime import datetime, timezone

from app.agents.state import GraphState
from app.models.incident import Incident
from app.schemas.websocket import WsMessage
from app.services.data_ingestion import fetch_incidents
from app.logging_config import get_logger

logger = get_logger(__name__)

AGENT_NAME = "ingestion"


async def ingestion_agent(state: GraphState) -> GraphState:
    """
    LangGraph node: Ingestion Agent.

    Responsibilities:
      1. Fetch raw incident data from external APIs (or mock fallback).
      2. Normalize each record into IncidentCreate-compatible dicts.
      3. Upsert incidents into the database (insert new, skip duplicates).
      4. Populate state["raw_incidents"] for the verification agent.
      5. Emit WebSocket events and append to state["agent_trace"].
    """
    run_id = state["run_id"]
    db = state["db_session"]
    trace: list[dict] = state["agent_trace"]

    # Lazy import to avoid circular dependency at module load time
    from app.services.websocket_manager import manager

    def _emit(step: str, message: str, severity="info", payload=None):
        """Emit a WsMessage and append to agent_trace."""
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

    _emit("start", "Ingestion agent started")

    # ------------------------------------------------------------------
    # Step 1: Fetch raw incidents from external sources / mock fallback
    # ------------------------------------------------------------------
    _emit("fetch_external_sources", "Fetching incidents from external sources")
    try:
        raw_records = await fetch_incidents()
        _emit(
            "fetch_complete",
            f"Fetched {len(raw_records)} raw records",
            payload={"count": len(raw_records)},
        )
    except Exception as exc:
        _emit("fetch_error", f"Fetch failed: {exc}", severity="error")
        raw_records = []

    # ------------------------------------------------------------------
    # Step 2: Normalize and upsert into DB
    # ------------------------------------------------------------------
    _emit("normalize_and_upsert", "Normalizing records and upserting to database")

    upserted = []
    skipped = 0

    for record in raw_records:
        try:
            external_id = record.get("external_id")

            # Deduplication: if external_id exists, check for existing row
            existing = None
            if external_id:
                existing = (
                    db.query(Incident)
                    .filter(Incident.source == record.get("source"))
                    .filter(Incident.raw_data.contains(external_id))
                    .first()
                )

            if existing:
                skipped += 1
                continue

            incident = Incident(
                title=record["title"],
                type=record["type"],
                severity=record["severity"],
                lat=record["lat"],
                lng=record["lng"],
                status="new",
                confidence=0.0,
                source=record.get("source"),
                raw_data=json.dumps(record),
            )
            db.add(incident)
            db.flush()  # get auto-generated id without committing

            upserted.append({
                "id": incident.id,
                "title": incident.title,
                "type": incident.type,
                "severity": incident.severity,
                "lat": incident.lat,
                "lng": incident.lng,
                "status": incident.status,
                "confidence": incident.confidence,
                "source": incident.source,
                "raw_data": incident.raw_data,
                "created_at": incident.created_at.isoformat()
                if incident.created_at else datetime.now(timezone.utc).isoformat(),
            })

        except Exception as exc:
            logger.warning("[%s] Failed to upsert record: %s — %s", AGENT_NAME, record, exc)
            _emit("upsert_warning", f"Skipped malformed record: {exc}", severity="warning")

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        _emit("db_error", f"Database commit failed: {exc}", severity="error")
