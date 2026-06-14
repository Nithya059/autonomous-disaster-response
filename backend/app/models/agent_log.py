from datetime import datetime
from sqlalchemy import Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    # ingestion | verification | prioritization | allocation | communication
    step: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, default="info")
    # info | warning | error | success
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON string — arbitrary agent output snapshot, nullable
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    run_id: Mapped[str] = mapped_column(Text, nullable=False)
    # UUID string grouping all log entries for one full graph execution

    def __repr__(self) -> str:
        return (
            f"<AgentLog id={self.id} agent={self.agent_name} "
            f"step={self.step} run_id={self.run_id!r}>"
        )
