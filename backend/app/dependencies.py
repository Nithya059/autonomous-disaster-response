from typing import Generator, Annotated
from fastapi import Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import Settings, get_settings


# ---------------------------------------------------------------------------
# Re-export get_db so routers import from one place
# ---------------------------------------------------------------------------
DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


# ---------------------------------------------------------------------------
# Pagination parameters — reusable across list endpoints
# ---------------------------------------------------------------------------
class PaginationParams:
    def __init__(
        self,
        skip: int = Query(default=0, ge=0, description="Number of records to skip"),
        limit: int = Query(default=100, ge=1, le=500, description="Max records to return"),
    ):
        self.skip = skip
        self.limit = limit


Pagination = Annotated[PaginationParams, Depends(PaginationParams)]
