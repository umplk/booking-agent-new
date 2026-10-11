from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class SeatCreate(BaseModel):
    seat_number: str = Field(..., max_length=20)
    is_available: bool = True
    window: bool = False
    power: bool = False
    quiet: bool = False
    is_group: bool = False
    corner: bool = False


class SeatBatchCreate(BaseModel):
    seats: List[SeatCreate]


class SeatUpdate(BaseModel):
    is_available: Optional[bool] = None
    seat_number: Optional[str] = Field(None, max_length=20)
    window: Optional[bool] = None
    power: Optional[bool] = None
    quiet: Optional[bool] = None
    is_group: Optional[bool] = None
    corner: Optional[bool] = None


class SeatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    seat_number: str
    is_available: bool
    window: bool = False
    power: bool = False
    quiet: bool = False
    is_group: bool = False
    corner: bool = False
    created_at: datetime
