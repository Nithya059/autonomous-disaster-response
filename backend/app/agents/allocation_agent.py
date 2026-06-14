import json
from datetime import datetime, timezone

from app.agents.state import GraphState
from app.models.incident import Incident
from app.models.resource import Resource
from app.schemas.websocket import WsMessage
from app.logging_config import get_logger
from app.services.geo_service import haversine, nearest_resources

logger = get_logger(__name__)

AGENT_NAME = "allocation"

# Resource type affinity — which resource types best serve each incident type
RESOURCE_AFFINITY = {
    "flood":      ["rescue", "logistics", "shelter"],
    "earthquake": ["rescue", "medical", "logistics"],
    "fire":       ["firefighting", "medical", "rescue"],
    "storm":      ["shelter", "logistics", "rescue"],
    "other":      ["logistics", "rescue", "medical"],
}

MAX_DISPATCH_DISTANCE_KM = 500.0


async def allocation_agent(state: GraphState) -> GraphState:
    """
    LangGraph node: Resource Allocation Agent.

    Responsibilities:
      1. Load all available resources from the database.
      2. For each prioritized incident (highest priority first), find the
         nearest compatible available resource using Haversine distance.
      3. Greedily assign resources — once dispatched, a resource is removed
         from the available pool for this run.
      4. Persist assignment to database (Resource.assigned_incident_id,
         Resource.status = "dispatched", Incident.status = "allocated").
      5. Populate state["allocations"] for the communication agent.
    """
    run_id = state["run_id"]
    db = state["db_session"]
    trace: list[dict] = state["agent_trace"]
    prioritized = state["prioritized"]

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

    _emit("start", f"Allocation agent started. Processing {len(prioritized)} prioritized incidents.")

    if not prioritized:
        _emit("skip", "No prioritized incidents to allocate.", severity="warning")
        return {**state, "allocations": [], "agent_trace": trace}

    # Load all currently available resources
    available_resources = (
        db.query(Resource)
        .filter(Resource.status == "available")
        .all()
    )

    _emit(
        "resources_loaded",
        f"Found {len(available_resources)} available resources.",
        payload={"available_count": len(available_resources)},
    )

    if not available_resources:
        _emit("no_resources", "No available resources to dispatch.", severity="warning")
        return {**state, "allocations": [], "agent_trace": trace}

    # Build mutable pool — keyed by resource id
    resource_pool = {r.id: r for r in available_resources}
    allocations = []

    for incident in prioritized:
        inc_id = incident.get("id")
        inc_type = incident.get("type", "other")
        inc_lat = incident.get("lat")
        inc_lng = incident.get("lng")
        inc_title = incident.get("title", f"Incident #{inc_id}")

        preferred_types = RESOURCE_AFFINITY.get(inc_type, ["logistics", "rescue"])

        _emit(
            "allocating",
            f"Finding resources for '{inc_title}' (type={inc_type})",
            payload={"incident_id": inc_id, "preferred_types": preferred_types},
        )

        # Find nearest available resource matching preferred types
        remaining = list(resource_pool.values())
        if not remaining:
            _emit("pool_empty", "Resource pool exhausted.", severity="warning")
            break

        best = nearest_resources(
            inc_lat,
            inc_lng,
            remaining,
            preferred_types=preferred_types,
            max_distance_km=MAX_DISPATCH_DISTANCE_KM,
            top_n=1,
        )

        if not best:
            _emit(
                "no_match",
                f"No compatible resource within {MAX_DISPATCH_DISTANCE_KM}km for '{inc_title}'",
                severity="warning",
                payload={"incident_id": inc_id},
            )
            continue

        resource, distance_km = best[0]

        # Remove from pool — greedy single-assignment per resource per run
        del resource_pool[resource.id]

        allocation = {
            "incident_id": inc_id,
            "incident_title": inc_title,
            "resource_id": resource.id,
            "resource_name": resource.name,
            "resource_type": resource.type,
            "distance_km": round(distance_km, 2),
        }
        allocations.append(allocation)

        _emit(
            "allocated",
            f"Dispatched '{resource.name}' ({resource.type}) → '{inc_title}' "
            f"[{distance_km:.1f}km]",
            severity="success",
            payload=allocation,
        )

        # Persist to DB
        try:
            db_resource = db.query(Resource).filter(Resource.id == resource.id).first()
            db_incident = db.query(Incident).filter(Incident.id == inc_id).first()

            if db_resource:
                db_resource.status = "dispatched"
                db_resource.assigned_incident_id = inc_id
            if db_incident:
                db_incident.status = "allocated"

            db.flush()
        except Exception as exc:
            logger.warning("[%s] Failed to persist allocation: %s", AGENT_NAME, exc)
            _emit("db_warning", f"Allocation persist failed: {exc}", severity="warning")

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        _emit("db_error", f"Failed to commit allocations: {exc}", severity="error")

    _emit(
        "complete",
        f"Allocation complete. {len(allocations)} resources dispatched.",
        severity="success",
        payload={"allocation_count": len(allocations)},
    )

    return {**state, "allocations": allocations, "agent_trace": trace}
