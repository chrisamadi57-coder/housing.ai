"""Listing schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ListingPurpose, ListingStatus
from app.schemas.property import PropertyRead, PropertySummary
from app.schemas.user import UserSummary


class ListingBase(BaseModel):
    purpose: ListingPurpose
    price: Decimal = Field(..., ge=0, max_digits=14, decimal_places=2)
    currency: str = Field("NGN", min_length=3, max_length=3)
    price_period: str | None = Field(None, pattern="^(month|year|week|day)$")
    is_negotiable: bool = False
    service_charge: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    deposit_months: int | None = Field(None, ge=0, le=36)
    available_from: date | None = None

    @model_validator(mode="after")
    def period_matches_purpose(self) -> "ListingBase":
        if self.purpose == ListingPurpose.SALE and self.price_period is not None:
            raise ValueError("Sale listings must not have a price_period")
        if self.purpose in (ListingPurpose.RENT, ListingPurpose.SHORTLET) and self.price_period is None:
            # sensible defaults
            object.__setattr__(
                self,
                "price_period",
                "month" if self.purpose == ListingPurpose.RENT else "day",
            )
        return self


class ListingCreate(ListingBase):
    property_id: UUID
    status: ListingStatus = ListingStatus.DRAFT


class ListingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: ListingPurpose | None = None
    status: ListingStatus | None = None
    price: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(None, min_length=3, max_length=3)
    price_period: str | None = Field(None, pattern="^(month|year|week|day)$")
    is_negotiable: bool | None = None
    service_charge: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    deposit_months: int | None = Field(None, ge=0, le=36)
    available_from: date | None = None


class ListingSummary(BaseModel):
    """Flat listing for search results — no nested media, no owner object."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purpose: ListingPurpose
    status: ListingStatus
    price: Decimal
    currency: str
    price_period: str | None = None
    is_negotiable: bool
    available_from: date | None = None
    views_count: int
    favorites_count: int

    property: PropertySummary


class ListingRead(ListingBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    owner_id: UUID

    status: ListingStatus
    views_count: int
    favorites_count: int

    property: PropertyRead
    owner: UserSummary | None = None

    created_at: datetime
    updated_at: datetime