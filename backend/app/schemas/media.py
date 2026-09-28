"""Media schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.enums import MediaType


class MediaBase(BaseModel):
    media_type: MediaType = MediaType.IMAGE
    order_index: int = Field(0, ge=0)
    is_cover: bool = False


class MediaCreate(MediaBase):
    """Used when registering an already-uploaded file against a property.

    The actual file bytes are handled by a separate upload endpoint that
    returns the URL; this schema just links the result to the property.
    """

    url: HttpUrl
    thumbnail_url: HttpUrl | None = None
    storage_key: str | None = Field(None, max_length=500)
    mime_type: str | None = Field(None, max_length=100)
    size_bytes: int | None = Field(None, ge=0)


class MediaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_index: int | None = Field(None, ge=0)
    is_cover: bool | None = None
    thumbnail_url: HttpUrl | None = None


class MediaRead(MediaBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    url: str
    thumbnail_url: str | None = None
    storage_key: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None

    processed: bool
    processing_error: str | None = None

    ai_labels: dict[str, Any] | None = None
    ai_quality_score: float | None = None
    ai_caption: str | None = None

    created_at: datetime
    updated_at: datetime


class MediaReorderRequest(BaseModel):
    """Bulk reorder — a list of media ids in the desired order."""

    media_ids: list[UUID] = Field(..., min_length=1)