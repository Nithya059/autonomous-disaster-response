import uuid
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Module-level scheduler instance
_scheduler = AsyncIOScheduler()


async def _run_pipeline() -> None:
    """
    Execute the full LangGraph pipeline on a schedule.
    Creates a fresh DB session for each run to avoid session reuse.
    """
    from app.agents.graph import compiled_graph
    from app.agents.state import GraphState
    from app.database import SessionLocal

    run_id = str(uuid.uuid4())
    db = SessionLocal()

    logger.info("Scheduled pipeline run started: %s", run_id)

    initial_state: GraphState = {
        "run_id": run_id,
        "raw_incidents": [],
        "verified": [],
        "prioritized": [],
        "allocations": [],
        "alerts": [],
        "agent_trace": [],
        "db_session": db,
    }

    try:
        await compiled_graph.ainvoke(initial_state)
        logger.info("Scheduled pipeline run completed: %s", run_id)
    except Exception as exc:
        logger.error("Scheduled pipeline run failed [%s]: %s", run_id, exc)
    finally:
        db.close()


def start_scheduler() -> None:
    """
    Start the APScheduler AsyncIOScheduler.
    Called once during FastAPI lifespan startup.
    Interval is controlled by SCHEDULER_INTERVAL_SECONDS env var.
    Setting SCHEDULER_INTERVAL_SECONDS=0 disables automatic scheduling.
    """
    interval = settings.scheduler_interval_seconds

    if interval <= 0:
        logger.info("Scheduler disabled (SCHEDULER_INTERVAL_SECONDS=%d)", interval)
        return

    _scheduler.add_job(
        _run_pipeline,
        trigger=IntervalTrigger(seconds=interval),
        id="pipeline_run",
        name="LangGraph disaster response pipeline",
        replace_existing=True,
        misfire_grace_time=30,
    )

    _scheduler.start()
    logger.info("Scheduler started: pipeline runs every %ds", interval)


def stop_scheduler() -> None:
    """
    Gracefully shut down the scheduler.
    Called during FastAPI lifespan shutdown.
    """
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
