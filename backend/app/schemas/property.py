"""Property schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import PropertyType
from app.schemas.media import MediaRead
from app.schemas.user import UserSummary


class PropertyBase(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str | None = Field(None, max_length=10_000)
    property_type: PropertyType

    bedrooms: int | None = Field(None, ge=0, le=50)
    bathrooms: int | None = Field(None, ge=0, le=50)
    toilets: int | None = Field(None, ge=0, le=50)
    area_sqm: float | None = Field(None, gt=0, le=100_000)
    year_built: int | None = Field(None, ge=1800, le=2100)
    is_furnished: bool = False

    address: str = Field(min_length=3, max_length=500)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=120)
    country: str = Field("Nigeria", min_length=1, max_length=120)
    postal_code: str | None = Field(None, max_length=20)

    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def coords_paired(self) -> "PropertyBase":
        # lat and lng must come together, or not at all
        if (self.latitude is None) ^ (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class PropertyCreate(PropertyBase):
    pass


class PropertyUpdate(BaseModel):
    """PATCH — every field optional; apply with exclude_unset=True."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=3, max_length=255)
    description: str | None = Field(None, max_length=10_000)
    property_type: PropertyType | None = None

    bedrooms: int | None = Field(None, ge=0, le=50)
    bathrooms: int | None = Field(None, ge=0, le=50)
    toilets: int | None = Field(None, ge=0, le=50)
    area_sqm: float | None = Field(None, gt=0, le=100_000)
    year_built: int | None = Field(None, ge=1800, le=2100)
    is_furnished: bool | None = None

    address: str | None = Field(None, min_length=3, max_length=500)
    city: str | None = Field(None, min_length=1, max_length=120)
    state: str | None = Field(None, min_length=1, max_length=120)
    country: str | None = Field(None, min_length=1, max_length=120)
    postal_code: str | None = Field(None, max_length=20)

    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)


class PropertySummary(BaseModel):
    """Lightweight property for embedding inside listings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    property_type: PropertyType
    bedrooms: int | None = None
    bathrooms: int | None = None
    address: str
    city: str
    state: str
    country: str
    latitude: float | None = None
    longitude: float | None = None


class PropertyRead(PropertyBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    owner: UserSummary | None = None
    media: list[MediaRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime