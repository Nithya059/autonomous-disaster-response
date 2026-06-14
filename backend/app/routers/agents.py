import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.dependencies import DbSession
from app.models.agent_log import AgentLog
from app.schemas.agent_log import AgentLogRead
from app.agents.state import GraphState
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

# In-memory run status tracker — keyed by run_id
_run_status: dict[str, str] = {}


async def _execute_graph(run_id: str, db_session) -> None:
    """
    Execute the full LangGraph pipeline as a background task.
    Updates _run_status on start and completion.
    """
    from app.agents.graph import compiled_graph

    _run_status[run_id] = "running"

    initial_state: GraphState = {
        "run_id": run_id,
        "raw_incidents": [],
        "verified": [],
        "prioritized": [],
        "allocations": [],
        "alerts": [],
        "agent_trace": [],
        "db_session": db_session,
    }

    try:
        await compiled_graph.ainvoke(initial_state)
        _run_status[run_id] = "completed"
        logger.info("Graph run %s completed successfully", run_id)
    except Exception as exc:
        _run_status[run_id] = f"error: {exc}"
        logger.error("Graph run %s failed: %s", run_id, exc)
    finally:
        db_session.close()


@router.post("/run", status_code=202)
async def trigger_run(background_tasks: BackgroundTasks, db: DbSession):
    """
    Manually trigger a full LangGraph pipeline run.
    Returns immediately with run_id; pipeline executes in background.
    """
    run_id = str(uuid.uuid4())
    logger.info("Manual agent run triggered: %s", run_id)

    # Pass db session to background — do NOT use the request-scoped session
    # after the response returns, so we create a fresh session for the task.
    from app.database import SessionLocal
    task_db = SessionLocal()

    background_tasks.add_task(_execute_graph, run_id, task_db)

    return {"run_id": run_id, "status": "started"}


@router.get("/status")
def get_agent_status():
    """
    Return the status of all known pipeline runs.
    Also returns the count of active WebSocket connections.
    """
    from app.services.websocket_manager import manager

    return {
        "runs": _run_status,
        "active_websocket_connections": manager.active_count,
    }


@router.get("/logs", response_model=List[AgentLogRead])
def get_agent_logs(
    db: DbSession,
    agent_name: Optional[str] = Query(default=None),
    run_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    Return persisted agent log entries with optional filtering.
    Ordered by timestamp descending (most recent first).
    """
    query = db.query(AgentLog)

    if agent_name:
        query = query.filter(AgentLog.agent_name == agent_name)
    if run_id:
        query = query.filter(AgentLog.run_id == run_id)
    if severity:
        query = query.filter(AgentLog.severity == severity)

    return (
        query.order_by(AgentLog.timestamp.desc())
        .limit(limit)
        .all()
)
