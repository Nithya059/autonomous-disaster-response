from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


VALID_TYPES = {"flood", "earthquake", "fire", "storm", "other"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_STATUSES = {"new", "verified", "prioritized", "allocated", "resolved"}


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    type: str = Field(..., description="flood | earthquake | fire | storm | other")
    severity: str = Field(..., description="low | medium | high | critical")
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    source: Optional[str] = Field(default=None, max_length=255)
    raw_data: Optional[str] = Field(default=None, description="JSON string of source payload")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(f"type must be one of {VALID_TYPES}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {VALID_SEVERITIES}")
        return v


class IncidentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    type: Optional[str] = None
    severity: Optional[str] = None
    lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    status: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source: Optional[str] = None
    raw_data: Optional[str] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_TYPES:
            raise ValueError(f"type must be one of {VALID_TYPES}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {VALID_SEVERITIES}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class IncidentRead(BaseModel):
    id: int
    title: str
    type: str
    severity: str
    lat: float
    lng: float
    status: str
    confidence: float
    source: Optional[str]
    raw_data: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
