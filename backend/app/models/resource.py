from datetime import datetime, time

from sqlalchemy import Column, Integer, String, Time, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=False)
    open_start = Column(Time, default=time(8, 0), nullable=False)
    open_end = Column(Time, default=time(22, 0), nullable=False)
    attributes = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    scenario = relationship("Scenario", back_populates="resources")
    reservations = relationship("Reservation", back_populates="resource", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Resource(id={self.id}, scenario_id={self.scenario_id}, code={self.code})>"