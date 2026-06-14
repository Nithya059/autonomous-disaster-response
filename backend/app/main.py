from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import configure_logging, get_logger
from app.database import create_all_tables

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Runs startup logic before yield, shutdown logic after.
    """
    # --- Startup ---
    logger.info("Starting Disaster Response API (env=%s)", settings.app_env)

    # Create DB tables if they don't exist (idempotent)
    create_all_tables()
    logger.info("Database tables verified/created")

    # Seed database with mock data if empty
    await _seed_if_empty()

    # Start WebSocket heartbeat loop
    from app.services.websocket_manager import manager
    heartbeat_task = asyncio.create_task(manager.heartbeat_loop())
    logger.info("WebSocket heartbeat task started")

    # Start APScheduler
    from app.tasks.scheduler import start_scheduler
    start_scheduler()

    yield

    # --- Shutdown ---
    logger.info("Shutting down Disaster Response API")

    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass

    from app.tasks.scheduler import stop_scheduler
    stop_scheduler()

    logger.info("Shutdown complete")


async def _seed_if_empty() -> None:
    """
    Seed the database with mock incidents and resources if both tables are empty.
    Ensures the app has data to display on first boot without running the CLI seeder.
    """
    from app.database import SessionLocal
    from app.models.incident import Incident
    from app.models.resource import Resource
    from app.services.mock_data import get_mock_incidents, get_mock_resources
    import json

    db = SessionLocal()
    try:
        incident_count = db.query(Incident).count()
        resource_count = db.query(Resource).count()

        if incident_count == 0:
            logger.info("Seeding incidents from mock data")
            for data in get_mock_incidents():
                db.add(Incident(
                    title=data["title"],
                    type=data["type"],
                    severity=data["severity"],
                    lat=data["lat"],
                    lng=data["lng"],
                    status="new",
                    confidence=0.0,
                    source=data.get("source"),
                    raw_data=json.dumps(data),
                ))
            db.commit()
            logger.info("Seeded %d incidents", len(get_mock_incidents()))

        if resource_count == 0:
            logger.info("Seeding resources from mock data")
            for data in get_mock_resources():
                db.add(Resource(
                    name=data["name"],
                    type=data["type"],
                    status="available",
                    lat=data["lat"],
                    lng=data["lng"],
                    capacity=data["capacity"],
                ))
            db.commit()
            logger.info("Seeded %d resources", len(get_mock_resources()))

    except Exception as exc:
        db.rollback()
        logger.error("Seeding failed: %s", exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Autonomous Disaster Response & Resource Coordinator",
    description="Multi-agent system for real-time disaster response coordination",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware — must be added before routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
from app.routers import incidents, resources, agents, websocket  # noqa: E402

app.include_router(incidents.router)
app.include_router(resources.router)
app.include_router(agents.router)
app.include_router(websocket.router)


@app.get("/health", tags=["system"])
def health_check():
    """Liveness probe — returns 200 when the API is running."""
    from app.services.websocket_manager import manager
    return {
        "status": "ok",
        "env": settings.app_env,
        "ws_connections": manager.active_count,
  }
