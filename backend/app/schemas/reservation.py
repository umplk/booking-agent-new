from datetime import datetime, date, time
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class ReservationCreate(BaseModel):
    seat_id: int
    room_id: int
    reservation_date: date
    start_time: time
    end_time: time
    status: str = Field(default="confirmed", pattern="^(pending|confirmed)$")


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    seat_id: int
    room_id: int
    reservation_date: date
    start_time: time
    end_time: time
    status: str
    created_at: datetime
    updated_at: datetime
    seat_number: Optional[str] = None
    room_name: Optional[str] = None


class SeatAvailability(BaseModel):
    seat_id: int
    seat_number: str
    is_available: bool
    booked_slots: List[dict] = []


class AvailabilityResponse(BaseModel):
    room_id: int
    date: date
    open_time: time
    close_time: time
    seats: List[SeatAvailability]
