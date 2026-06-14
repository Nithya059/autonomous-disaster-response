from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from typing import Generator
from app.config import get_settings


settings = get_settings()


# ---------------------------------------------------------------------------
# SQLAlchemy engine
# connect_args check_same_thread=False is required for SQLite when used
# with FastAPI's multi-threaded request handling.
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.is_development,  # Log SQL in dev mode only
)


# Enable WAL mode for SQLite — improves concurrent read performance
# when the scheduler and HTTP requests access the DB simultaneously.
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ---------------------------------------------------------------------------
# Declarative base — all ORM models inherit from this
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency — yields a DB session and ensures cleanup
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """
    Yields a SQLAlchemy session for use as a FastAPI dependency.
    Usage:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Utility — called during app startup to create all tables
# ---------------------------------------------------------------------------
def create_all_tables() -> None:
    """
    Create all tables defined in ORM models.
    Import all model modules before calling this so Base.metadata
    is populated.
    """
    # Models must be imported before this call so SQLAlchemy
    # registers them against Base.metadata.
    from app.models import incident, resource, agent_log  # noqa: F401
    Base.metadata.create_all(bind=engine)
