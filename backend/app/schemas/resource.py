from datetime import datetime, time
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class ResourceCreate(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50)
    open_start: time = Field(default_factory=lambda: time(8, 0))
    open_end: time = Field(default_factory=lambda: time(22, 0))
    attributes: Optional[Dict[str, Any]] = None
    is_active: bool = True


class ResourceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    open_start: Optional[time] = None
    open_end: Optional[time] = None
    attributes: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario_id: int
    name: str
    code: str
    open_start: time
    open_end: time
    attributes: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime