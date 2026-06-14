from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


VALID_TYPES = {"medical", "rescue", "logistics", "firefighting", "shelter"}
VALID_STATUSES = {"available", "dispatched", "unavailable"}


class ResourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., description="medical | rescue | logistics | firefighting | shelter")
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    capacity: int = Field(default=1, ge=1, le=1000)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(f"type must be one of {VALID_TYPES}")
        return v


class ResourceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    type: Optional[str] = None
    status: Optional[str] = None
    lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    capacity: Optional[int] = Field(default=None, ge=1, le=1000)
    assigned_incident_id: Optional[int] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_TYPES:
            raise ValueError(f"type must be one of {VALID_TYPES}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class ResourceRead(BaseModel):
    id: int
    name: str
    type: str
    status: str
    lat: float
    lng: float
    capacity: int
    assigned_incident_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}
