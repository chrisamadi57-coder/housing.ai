"""Verification model — 1:1 trust / fraud record attached to a Property."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import VerificationStatus

if TYPE_CHECKING:
    from app.models.property import Property
    from app.models.user import User


class Verification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "verifications"

    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # ---- Status ---------------------------------------------------------
    status: Mapped[VerificationStatus] = mapped_column(
        default=VerificationStatus.PENDING,
        server_default=VerificationStatus.PENDING.value,
        index=True,
        nullable=False,
    )

    # ---- Location -------------------------------------------------------
    location_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    location_notes: Mapped[str | None] = mapped_column(Text)
    geocoded_address: Mapped[str | None] = mapped_column(String(500))

    # ---- Fraud / risk (written by ai/fraud_detection.py) ----------------
    # 0.0 = safe, 1.0 = certain fraud.
    fraud_score: Mapped[float | None] = mapped_column(Float, index=True)
    fraud_reasons: Mapped[list[str] | None] = mapped_column(JSONB)

    # ---- Documents ------------------------------------------------------
    # e.g. [{"name": "C of O", "url": "https://...", "verified": true}]
    document_urls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)

    # ---- Free-form ------------------------------------------------------
    notes: Mapped[str | None] = mapped_column(Text)

    # ---- Relationships --------------------------------------------------
    property: Mapped["Property"] = relationship(back_populates="verification")
    verified_by: Mapped["User | None"] = relationship(
        back_populates="verified_properties", foreign_keys=[verified_by_id]
    )

    __table_args__ = (
        CheckConstraint(
            "fraud_score IS NULL OR (fraud_score >= 0 AND fraud_score <= 1)",
            name="fraud_score_range",
        ),
        Index("ix_verifications_status_fraud", "status", "fraud_score"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Verification property={self.property_id} status={self.status.value}>"