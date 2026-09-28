"""Search schemas — bridges the AI parser output and the query layer."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ListingPurpose, PropertyType
from app.schemas.listing import ListingSummary


class SearchRequest(BaseModel):
    """Raw user query + pagination. This is what hits the endpoint."""

    q: str = Field(..., min_length=1, max_length=500)
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class ParsedSearchFilters(BaseModel):
    """Structured output of the AI search parser.

    This is the contract between ``ai/search_parser.py`` and
    ``services/search_service.py``. Both sides build against this —
    neither side needs to know how the other works.
    """

    model_config = ConfigDict(extra="ignore")

    # text
    q: str | None = None
    keywords: list[str] = Field(default_factory=list)

    # location
    city: str | None = None
    state: str | None = None
    country: str | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    radius_km: float | None = Field(None, gt=0, le=500)

    # taxonomy
    property_type: PropertyType | None = None
    purpose: ListingPurpose | None = None

    # price
    min_price: Decimal | None = Field(None, ge=0)
    max_price: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, min_length=3, max_length=3)

    # attributes
    bedrooms_min: int | None = Field(None, ge=0, le=50)
    bedrooms_max: int | None = Field(None, ge=0, le=50)
    bathrooms_min: int | None = Field(None, ge=0, le=50)
    area_sqm_min: float | None = Field(None, gt=0)
    is_furnished: bool | None = None


class SearchResponse(BaseModel):
    """What the /search endpoint returns."""

    filters: ParsedSearchFilters
    total: int
    page: int
    size: int
    pages: int
    results: list[ListingSummary]


class SuggestionsResponse(BaseModel):
    """Optional — autocomplete for the search box."""

    suggestions: list[str]


class FavoriteToggleResponse(BaseModel):
    """Used by the favorites feature on the frontend."""

    listing_id: UUID
    is_favorite: bool
    favorites_count: int