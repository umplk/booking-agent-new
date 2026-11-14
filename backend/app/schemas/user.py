from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


def _validate_password_strength(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
        raise ValueError("密码需同时包含字母和数字")
    return value


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    student_id: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=50)
    role: str = Field("student", pattern="^(student|merchant)$")
    invite_code: Optional[str] = Field(None, max_length=64)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        return _validate_password_strength(value)


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    student_id: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=50)
    password: Optional[str] = Field(None, min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: Optional[str]) -> Optional[str]:
        return _validate_password_strength(value)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    student_id: Optional[str] = None
    name: Optional[str] = None
    role: str
    created_at: datetime
    updated_at: datetime


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
