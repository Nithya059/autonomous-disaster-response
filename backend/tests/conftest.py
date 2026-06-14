import pytest
import json
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base, get_db
from app.main import app
from app.models.incident import Incident
from app.models.resource import Resource
from app.services.mock_data import get_mock_incidents, get_mock_resources

# ---------------------------------------------------------------------------
# In-memory SQLite database for tests — isolated per test session
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """Create all tables once for the entire test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Provide a transactional test DB session that rolls back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """
    Provide a FastAPI TestClient with the test DB injected.
    Overrides the get_db dependency for the duration of the test.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_db(db: Session) -> Session:
    """Seed the test DB with mock incidents and resources, return session."""
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
    return db


@pytest.fixture
def mock_incident_data() -> dict:
    """Return a single valid IncidentCreate payload dict."""
    return {
        "title": "Test flooding in Metro Manila",
        "type": "flood",
        "severity": "high",
        "lat": 14.5995,
        "lng": 120.9842,
        "source": "test",
    }


@pytest.fixture
def mock_resource_data() -> dict:
    """Return a single valid ResourceCreate payload dict."""
    return {
        "name": "Test Medical Team Alpha",
        "type": "medical",
        "lat": 14.6091,
        "lng": 121.0223,
        "capacity": 20,
    }
