from datetime import datetime, time
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class RoomCreate(BaseModel):
    name: str = Field(..., max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    open_time: time = Field(default_factory=lambda: time(8, 0))
    close_time: time = Field(default_factory=lambda: time(22, 0))
    capacity: int = Field(default=0, ge=0)
    is_active: bool = True


class RoomUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    capacity: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: Optional[str] = None
    open_time: time
    close_time: time
    capacity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SeatBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    seat_number: str
    is_available: bool
    window: bool = False
    power: bool = False
    quiet: bool = False
    is_group: bool = False
    corner: bool = False


class RoomDetailResponse(RoomResponse):
    seats: List[SeatBrief] = []
