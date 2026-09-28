"""Verification schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import VerificationStatus


class VerificationDocument(BaseModel):
    """One entry in the document_urls JSONB list."""

    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=1000)
    verified: bool = False


class VerificationBase(BaseModel):
    status: VerificationStatus = VerificationStatus.PENDING
    location_confirmed: bool = False
    location_notes: str | None = Field(None, max_length=2000)
    geocoded_address: str | None = Field(None, max_length=500)
    document_urls: list[VerificationDocument] | None = None
    notes: str | None = Field(None, max_length=5000)


class VerificationCreate(BaseModel):
    """User-initiated verification request — only these fields are accepted.

    Everything else (fraud_score, status transitions, verified_by) is set
    by the system or an admin.
    """

    property_id: UUID
    document_urls: list[VerificationDocument] = Field(default_factory=list)
    notes: str | None = Field(None, max_length=5000)


class VerificationUpdate(BaseModel):
    """Admin/worker update — most fields writable."""

    model_config = ConfigDict(extra="forbid")

    status: VerificationStatus | None = None
    location_confirmed: bool | None = None
    location_notes: str | None = Field(None, max_length=2000)
    geocoded_address: str | None = Field(None, max_length=500)
    document_urls: list[VerificationDocument] | None = None
    notes: str | None = Field(None, max_length=5000)


class VerificationRead(VerificationBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    verified_by_id: UUID | None = None

    fraud_score: float | None = Field(None, ge=0, le=1)
    fraud_reasons: list[str] | None = None

    created_at: datetime
    updated_at: datetime