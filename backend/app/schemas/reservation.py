from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class ReservationCreate(BaseModel):
    scenario_id: int
    resource_id: int
    start_time: datetime
    end_time: datetime


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario_id: int
    user_id: int
    resource_id: int
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime
    updated_at: datetime
    scenario_name: Optional[str] = None
    resource_name: Optional[str] = None


class TimeSlot(BaseModel):
    start: str
    end: str


class ResourceAvailability(BaseModel):
    resource_id: int
    code: str
    name: str
    is_active: bool
    free_slots: List[TimeSlot] = []


class ScenarioAvailability(BaseModel):
    scenario_id: int
    date: str
    free_slots_count: int
    resources: List[ResourceAvailability]