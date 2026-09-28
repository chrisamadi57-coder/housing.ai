"""Listing model — an offer of a Property (rent / sale / shortlet)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ListingPurpose, ListingStatus

if TYPE_CHECKING:
    from app.models.property import Property
    from app.models.user import User


class Listing(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "listings"

    # ---- Relations ------------------------------------------------------
    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # ---- Commercial terms ----------------------------------------------
    purpose: Mapped[ListingPurpose] = mapped_column(index=True, nullable=False)
    status: Mapped[ListingStatus] = mapped_column(
        default=ListingStatus.DRAFT,
        server_default=ListingStatus.DRAFT.value,
        index=True,
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), index=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN", server_default="NGN", nullable=False)
    price_period: Mapped[str | None] = mapped_column(String(16))  # "month" | "year" | None
    is_negotiable: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    service_charge: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    deposit_months: Mapped[int | None]

    # ---- Availability ---------------------------------------------------
    available_from: Mapped[date | None] = mapped_column(Date)

    # ---- Engagement metrics --------------------------------------------
    views_count: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    favorites_count: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)

    # ---- Relationships --------------------------------------------------
    property: Mapped["Property"] = relationship(back_populates="listings")
    owner: Mapped["User"] = relationship(back_populates="listings")

    __table_args__ = (
        CheckConstraint("price >= 0", name="price_non_negative"),
        Index("ix_listings_status_purpose", "status", "purpose"),
        Index("ix_listings_status_price", "status", "price"),
        Index("ix_listings_purpose_price", "purpose", "price"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Listing {self.purpose.value} {self.price} {self.currency} "
            f"status={self.status.value}>"
        )