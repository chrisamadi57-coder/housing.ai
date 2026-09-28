"""User schemas — auth, registration, profile."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=32)
    avatar_url: str | None = Field(None, max_length=1000)
    bio: str | None = Field(None, max_length=1000)


# ---------------------------------------------------------------------------
# Create / Login
# ---------------------------------------------------------------------------
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    # Optional — defaults to "user" server-side. Only admins should be able
    # to set anything else, and the route enforces that.
    role: UserRole | None = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain a letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain a digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


# ---------------------------------------------------------------------------
# Update (PATCH) — every field optional, apply with exclude_unset
# ---------------------------------------------------------------------------
class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=32)
    avatar_url: str | None = Field(None, max_length=1000)
    bio: str | None = Field(None, max_length=1000)
    # password change is a separate endpoint; keep it out of this schema
    # so a PATCH can never accidentally change credentials


class UserPasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
class UserSummary(BaseModel):
    """Trimmed user for embedding inside listings/properties."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    avatar_url: str | None = None
    role: UserRole


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Auth responses
# ---------------------------------------------------------------------------
class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expiry


class TokenPayload(BaseModel):
    """Decoded JWT contents. Useful for typed deps."""

    sub: UUID
    type: str  # "access" | "refresh"
    exp: int
    iat: int


class RefreshRequest(BaseModel):
    refresh_token: str