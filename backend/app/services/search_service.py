"""Search service — natural language → parsed filters → query → results."""

from __future__ import annotations

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.search_parser import parse_search_query
from app.models.enums import ListingStatus
from app.models.listing import Listing
from app.models.property import Property
from app.schemas.listing import ListingSummary
from app.schemas.search import (
    ParsedSearchFilters,
    SearchResponse,
    SuggestionsResponse,
)


class SearchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Query building
    # ------------------------------------------------------------------ #
    def _build_stmt(self, f: ParsedSearchFilters):
        stmt = (
            select(Listing)
            .join(Property, Property.id == Listing.property_id)
            .options(selectinload(Listing.property))
            .where(Listing.status == ListingStatus.ACTIVE)
        )

        # Free-text — hits title and description.
        if f.q:
            like = f"%{f.q}%"
            stmt = stmt.where(
                or_(Property.title.ilike(like), Property.description.ilike(like))
            )
        if f.keywords:
            clauses = []
            for kw in f.keywords:
                like = f"%{kw}%"
                clauses.append(Property.title.ilike(like))
                clauses.append(Property.description.ilike(like))
            stmt = stmt.where(or_(*clauses))

        # Location
        if f.city:
            stmt = stmt.where(Property.city.ilike(f"%{f.city}%"))
        if f.state:
            stmt = stmt.where(Property.state.ilike(f"%{f.state}%"))
        if f.country:
            stmt = stmt.where(Property.country.ilike(f"%{f.country}%"))

        # Geo radius (PostGIS). Uses the GIST index on Property.location.
        if f.lat is not None and f.lng is not None and f.radius_km is not None:
            stmt = stmt.where(
                func.ST_DWithin(
                    Property.location,
                    func.ST_SetSRID(func.ST_MakePoint(f.lng, f.lat), 4326).cast(
                        Property.location.type
                    ),
                    f.radius_km * 1000,
                )
            )

        # Taxonomy
        if f.property_type:
            stmt = stmt.where(Property.property_type == f.property_type)
        if f.purpose:
            stmt = stmt.where(Listing.purpose == f.purpose)

        # Price
        if f.min_price is not None:
            stmt = stmt.where(Listing.price >= f.min_price)
        if f.max_price is not None:
            stmt = stmt.where(Listing.price <= f.max_price)

        # Attributes
        if f.bedrooms_min is not None:
            stmt = stmt.where(Property.bedrooms >= f.bedrooms_min)
        if f.bedrooms_max is not None:
            stmt = stmt.where(Property.bedrooms <= f.bedrooms_max)
        if f.bathrooms_min is not None:
            stmt = stmt.where(Property.bathrooms >= f.bathrooms_min)
        if f.area_sqm_min is not None:
            stmt = stmt.where(Property.area_sqm >= f.area_sqm_min)
        if f.is_furnished is not None:
            stmt = stmt.where(Property.is_furnished == f.is_furnished)

        return stmt

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def search(self, *, raw_query: str, page: int, size: int) -> SearchResponse:
        filters: ParsedSearchFilters = await parse_search_query(raw_query)
        # Preserve the original query text if the parser didn't set one.
        if filters.q is None:
            filters.q = raw_query

        stmt = self._build_stmt(filters)

        total = await self.db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0

        rows = (
            await self.db.scalars(
                stmt.order_by(Listing.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()

        # Normalize to ListingSummary (drops media/owner — lighter payload).
        results = [ListingSummary.model_validate(r) for r in rows]

        return SearchResponse(
            filters=filters,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size if total else 0,
            results=results,
        )

    async def suggestions(self, q: str, *, limit: int) -> SuggestionsResponse:
        """Very small — city + state autocomplete. Extend as needed."""
        like = f"%{q}%"
        stmt = (
            select(Property.city)
            .where(Property.city.ilike(like))
            .distinct()
            .limit(limit)
        )
        cities = [row for row in (await self.db.scalars(stmt)).all()]

        state_stmt = (
            select(Property.state)
            .where(Property.state.ilike(like))
            .distinct()
            .limit(limit)
        )
        states = [row for row in (await self.db.scalars(state_stmt)).all()]

        merged = list({*cities, *states})[:limit]
        return SuggestionsResponse(suggestions=merged)