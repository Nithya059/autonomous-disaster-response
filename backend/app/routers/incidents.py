from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import DbSession, Pagination
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate, IncidentRead, IncidentUpdate
from app.schemas.websocket import WsMessage
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=List[IncidentRead])
def list_incidents(
    db: DbSession,
    pagination: Pagination,
    severity: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    incident_type: Optional[str] = Query(default=None, alias="type"),
):
    """
    Return all incidents with optional filtering by severity, status, or type.
    Ordered by created_at descending (most recent first).
    """
    query = db.query(Incident)

    if severity:
        query = query.filter(Incident.severity == severity)
    if status:
        query = query.filter(Incident.status == status)
    if incident_type:
        query = query.filter(Incident.type == incident_type)

    return (
        query.order_by(Incident.created_at.desc())
        .offset(pagination.skip)
        .limit(pagination.limit)
        .all()
    )


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: int, db: DbSession):
    """Return a single incident by ID."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return incident


@router.post("", response_model=IncidentRead, status_code=201)
async def create_incident(body: IncidentCreate, db: DbSession):
    """
    Manually create a new incident.
    Broadcasts an incident_update WebSocket event after creation.
    """
    from app.services.websocket_manager import manager
    import uuid

    incident = Incident(
        title=body.title,
        type=body.type,
        severity=body.severity,
        lat=body.lat,
        lng=body.lng,
        status="new",
        confidence=0.0,
        source=body.source,
        raw_data=body.raw_data,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    logger.info("Created incident id=%d title=%r", incident.id, incident.title)

    # Notify all WebSocket clients
    msg = WsMessage.incident_update(
        run_id=str(uuid.uuid4()),
        payload=IncidentRead.model_validate(incident).model_dump(mode="json"),
        message=f"New incident created: {incident.title}",
    )
    await manager.broadcast(msg.to_json())

    return incident


@router.patch("/{incident_id}", response_model=IncidentRead)
async def update_incident(incident_id: int, body: IncidentUpdate, db: DbSession):
    """
    Partially update an incident.
    Broadcasts an incident_update WebSocket event after update.
    """
    from app.services.websocket_manager import manager
    import uuid

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(incident, field, value)

    db.commit()
    db.refresh(incident)

    logger.info("Updated incident id=%d fields=%s", incident_id, list(update_data.keys()))

    msg = WsMessage.incident_update(
        run_id=str(uuid.uuid4()),
        payload=IncidentRead.model_validate(incident).model_dump(mode="json"),
        message=f"Incident updated: {incident.title}",
    )
    await manager.broadcast(msg.to_json())

    return incident


@router.delete("/{incident_id}", status_code=204)
def delete_incident(incident_id: int, db: DbSession):
    """Delete an incident by ID."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    db.delete(incident)
    db.commit()
    logger.info("Deleted incident id=%d", incident_id)
