from datetime import datetime
from sqlalchemy import Integer, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    # medical | rescue | logistics | firefighting | shelter
    status: Mapped[str] = mapped_column(Text, nullable=False, default="available")
    # available | dispatched | unavailable
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    assigned_incident_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Lazy relationship — not eagerly loaded to keep query performance predictable
    assigned_incident = relationship(
        "Incident",
        foreign_keys=[assigned_incident_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Resource id={self.id} name={self.name!r} "
            f"type={self.type} status={self.status}>"
  )
