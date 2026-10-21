from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    time_step_minutes = Column(Integer, default=30, nullable=False)
    min_duration_minutes = Column(Integer, default=30, nullable=False)
    max_duration_minutes = Column(Integer, default=240, nullable=False)
    max_advance_days = Column(Integer, default=30, nullable=False)
    min_advance_minutes = Column(Integer, default=0, nullable=False)
    max_minutes_per_day = Column(Integer, nullable=True)
    allow_same_day = Column(Boolean, default=True, nullable=False)
    max_active_per_user = Column(Integer, default=5, nullable=False)
    cancel_before_minutes = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    resources = relationship("Resource", back_populates="scenario", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="scenario", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Scenario(id={self.id}, name={self.name})>"