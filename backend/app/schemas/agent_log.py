from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AgentLogRead(BaseModel):
    id: int
    agent_name: str
    step: str
    message: str
    severity: str
    # info | warning | error | success
    payload_json: Optional[str] = None
    timestamp: datetime
    run_id: str

    model_config = {"from_attributes": True}


class AgentLogFilter(BaseModel):
    """Query parameters for filtering agent logs."""
    agent_name: Optional[str] = Field(default=None)
    run_id: Optional[str] = Field(default=None)
    severity: Optional[str] = Field(default=None)
    limit: int = Field(default=100, ge=1, le=500)
