from datetime import datetime
from sqlalchemy import Integer, Text, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    # flood | earthquake | fire | storm | other
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    # low | medium | high | critical
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    # new | verified | prioritized | allocated | resolved
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 0.0 – 1.0 assigned by verification agent
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON string of original feed payload
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<Incident id={self.id} title={self.title!r} "
            f"severity={self.severity} status={self.status}>"
  )
