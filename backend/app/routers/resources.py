from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.dependencies import DbSession, Pagination
from app.models.resource import Resource
from app.schemas.resource import ResourceCreate, ResourceRead, ResourceUpdate
from app.schemas.websocket import WsMessage
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("", response_model=List[ResourceRead])
def list_resources(
    db: DbSession,
    pagination: Pagination,
    status: Optional[str] = Query(default=None),
    resource_type: Optional[str] = Query(default=None, alias="type"),
):
    """
    Return all resources with optional filtering by status or type.
    """
    query = db.query(Resource)

    if status:
        query = query.filter(Resource.status == status)
    if resource_type:
        query = query.filter(Resource.type == resource_type)

    return (
        query.order_by(Resource.id)
        .offset(pagination.skip)
        .limit(pagination.limit)
        .all()
    )


@router.post("", response_model=ResourceRead, status_code=201)
async def create_resource(body: ResourceCreate, db: DbSession):
    """
    Manually register a new resource.
    Broadcasts a resource_update WebSocket event after creation.
    """
    from app.services.websocket_manager import manager
    import uuid

    resource = Resource(
        name=body.name,
        type=body.type,
        status="available",
        lat=body.lat,
        lng=body.lng,
        capacity=body.capacity,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)

    logger.info("Created resource id=%d name=%r", resource.id, resource.name)

    msg = WsMessage.resource_update(
        run_id=str(uuid.uuid4()),
        payload=ResourceRead.model_validate(resource).model_dump(mode="json"),
        message=f"New resource registered: {resource.name}",
    )
    await manager.broadcast(msg.to_json())

    return resource


@router.patch("/{resource_id}", response_model=ResourceRead)
async def update_resource(resource_id: int, body: ResourceUpdate, db: DbSession):
    """
    Partially update a resource.
    Broadcasts a resource_update WebSocket event after update.
    """
    from app.services.websocket_manager import manager
    import uuid

    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail=f"Resource {resource_id} not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(resource, field, value)

    db.commit()
    db.refresh(resource)

    logger.info("Updated resource id=%d fields=%s", resource_id, list(update_data.keys()))

    msg = WsMessage.resource_update(
        run_id=str(uuid.uuid4()),
        payload=ResourceRead.model_validate(resource).model_dump(mode="json"),
        message=f"Resource updated: {resource.name}",
    )
    await manager.broadcast(msg.to_json())

    return resource
