from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class ScenarioCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    time_step_minutes: int = Field(30, ge=5, le=240)
    min_duration_minutes: int = Field(30, ge=5)
    max_duration_minutes: int = Field(240, le=1440)
    max_advance_days: int = Field(30, ge=0, le=365)
    min_advance_minutes: int = Field(0, ge=0, le=10080)
    max_minutes_per_day: Optional[int] = Field(None, ge=1, le=1440)
    allow_same_day: bool = True
    max_active_per_user: int = Field(5, ge=1, le=100)
    cancel_before_minutes: Optional[int] = Field(None, ge=0)
    is_active: bool = True


class ScenarioUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    time_step_minutes: Optional[int] = Field(None, ge=5, le=240)
    min_duration_minutes: Optional[int] = Field(None, ge=5)
    max_duration_minutes: Optional[int] = Field(None, le=1440)
    max_advance_days: Optional[int] = Field(None, ge=0, le=365)
    min_advance_minutes: Optional[int] = Field(None, ge=0, le=10080)
    max_minutes_per_day: Optional[int] = Field(None, ge=1, le=1440)
    allow_same_day: Optional[bool] = None
    max_active_per_user: Optional[int] = Field(None, ge=1, le=100)
    cancel_before_minutes: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    time_step_minutes: int
    min_duration_minutes: int
    max_duration_minutes: int
    max_advance_days: int
    min_advance_minutes: int
    max_minutes_per_day: Optional[int] = None
    allow_same_day: bool
    max_active_per_user: int
    cancel_before_minutes: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime