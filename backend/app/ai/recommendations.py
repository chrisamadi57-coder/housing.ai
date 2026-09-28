"""Recommendation engine.

Two features:
  - recommend_for_user: personalized feed
  - similar_listings: "More like this" on a listing detail page

Content-based, deterministic, no ML. Uses features users already filter
by: price band, location, property type, bedrooms. Upgrades cleanly to
embeddings + vector search later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Sequence
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import ListingPurpose, ListingStatus, PropertyType
from app.models.listing import Listing
from app.models.property import Property


@dataclass(slots=True)
class RecommendationResult:
    listing_ids: list[UUID]
    scores: dict[str, float] = field(default_factory=dict)
    reason: str | None = None


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _price_band(price: Decimal) -> int:
    """Bucket prices into human-meaningful bands (NGN-oriented)."""
    p = float(price)
    if p < 500_000:
        return 1
    if p < 1_500_000:
        return 2
    if p < 5_000_000:
        return 3
    if p < 20_000_000:
        return 4
    if p < 100_000_000:
        return 5
    return 6


def _listing_features(listing: Listing, prop: Property) -> dict:
    return {
        "purpose": listing.purpose,
        "price_band": _price_band(listing.price),
        "property_type": prop.property_type,
        "bedrooms": prop.bedrooms,
        "city": prop.city.lower() if prop.city else None,
        "state": prop.state.lower() if prop.state else None,
    }


def _similarity(a: dict, b: dict) -> float:
    """Weighted feature agreement in [0, 1]."""
    if a["purpose"] != b["purpose"]:
        return 0.0  # hard filter — never recommend a sale to a renter

    score = 0.0
    total = 0.0

    # Location match — heaviest weight
    total += 0.35
    if a["city"] and b["city"] and a["city"] == b["city"]:
        score += 0.35
    elif a["state"] and b["state"] and a["state"] == b["state"]:
        score += 0.15

    # Property type
    total += 0.20
    if a["property_type"] == b["property_type"]:
        score += 0.20

    # Bedrooms — distance based
    total += 0.20
    if a["bedrooms"] is not None and b["bedrooms"] is not None:
        diff = abs(a["bedrooms"] - b["bedrooms"])
        score += 0.20 * max(0.0, 1 - diff / 3)

    # Price band — distance based
    total += 0.25
    diff_band = abs(a["price_band"] - b["price_band"])
    score += 0.25 * max(0.0, 1 - diff_band / 3)

    return round(score / total, 4) if total else 0.0


# ---------------------------------------------------------------------------
# Base query
# ---------------------------------------------------------------------------

def _active_listing_query():
    return (
        select(Listing)
        .join(Property, Property.id == Listing.property_id)
        .options(selectinload(Listing.property))
        .where(Listing.status == ListingStatus.ACTIVE)
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def similar_listings(
    db: AsyncSession,
    *,
    listing_id: UUID,
    limit: int = 8,
) -> RecommendationResult:
    """Find listings similar to the given one — "More like this"."""
    base = await db.scalar(
        select(Listing)
        .options(selectinload(Listing.property))
        .where(Listing.id == listing_id)
    )
    if not base or not base.property:
        return RecommendationResult(listing_ids=[], reason="Base listing not found")

    base_feat = _listing_features(base, base.property)

    # Pre-filter in SQL to a reasonable candidate set, then rank in Python.
    # This avoids loading thousands of rows.
    candidates_stmt = _active_listing_query().where(
        Listing.id != listing_id,
        Listing.purpose == base.purpose,
        Property.id != base.property_id,
        or_(
            Property.city == base.property.city,
            Property.state == base.property.state,
            Property.property_type == base.property.property_type,
        ),
    ).limit(200)

    rows = (await db.scalars(candidates_stmt)).all()

    scored: list[tuple[float, UUID]] = []
    for row in rows:
        if not row.property:
            continue
        score = _similarity(base_feat, _listing_features(row, row.property))
        if score > 0.2:
            scored.append((score, row.id))

    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:limit]

    return RecommendationResult(
        listing_ids=[lid for _, lid in top],
        scores={str(lid): s for s, lid in top},
        reason="Content-based similarity (location, type, bedrooms, price band)",
    )


async def recommend_for_user(
    db: AsyncSession,
    *,
    user_id: UUID,
    limit: int = 12,
    seed_listing_ids: Sequence[UUID] | None = None,
) -> RecommendationResult:
    """Personalized recommendations.

    Strategy (in order of preference):
      1. If ``seed_listing_ids`` provided (e.g. user's favorites), score
         all active listings against the *centroid* of those features.
      2. Otherwise, return a diverse "cold-start" set: popular listings
         across cities. Better than a random dump.

    We do NOT depend on a ``favorites`` table here — that belongs to
    Person 3's worker or a future service. Callers pass seeds explicitly.
    """
    # ---- Warm start: user has favorites/history -----------------------
    if seed_listing_ids:
        seeds = (
            await db.scalars(
                select(Listing)
                .options(selectinload(Listing.property))
                .where(Listing.id.in_(seed_listing_ids))
            )
        ).all()
        seeds = [s for s in seeds if s.property]

        if seeds:
            # Aggregate seed features: most common city/type, avg price band
            cities: dict[str, int] = {}
            states: dict[str, int] = {}
            types: dict[PropertyType, int] = {}
            bands: list[int] = []
            purposes: dict[ListingPurpose, int] = {}

            for s in seeds:
                p = s.property
                if p.city:
                    cities[p.city.lower()] = cities.get(p.city.lower(), 0) + 1
                if p.state:
                    states[p.state.lower()] = states.get(p.state.lower(), 0) + 1
                types[p.property_type] = types.get(p.property_type, 0) + 1
                bands.append(_price_band(s.price))
                purposes[s.purpose] = purposes.get(s.purpose, 0) + 1

            top_city = max(cities, key=cities.get) if cities else None
            top_state = max(states, key=states.get) if states else None
            top_type = max(types, key=types.get) if types else None
            top_purpose = max(purposes, key=purposes.get) if purposes else None
            avg_band = sum(bands) / len(bands) if bands else 3

            # Build centroid feature dict
            centroid = {
                "purpose": top_purpose,
                "price_band": int(round(avg_band)),
                "property_type": top_type,
                "bedrooms": None,
                "city": top_city,
                "state": top_state,
            }

            # Exclude seeds themselves
            candidates = (
                await db.scalars(
                    _active_listing_query().where(
                        Listing.id.notin_(seed_listing_ids),
                    ).limit(300)
                )
            ).all()

            scored: list[tuple[float, UUID]] = []
            for row in candidates:
                if not row.property:
                    continue
                score = _similarity(centroid, _listing_features(row, row.property))
                if score > 0.15:
                    scored.append((score, row.id))
            scored.sort(key=lambda t: t[0], reverse=True)
            top = scored[:limit]

            return RecommendationResult(
                listing_ids=[lid for _, lid in top],
                scores={str(lid): s for s, lid in top},
                reason="Based on your recent interests",
            )

    # ---- Cold start: popular + diverse -------------------------------
    stmt = (
        _active_listing_query()
        .order_by(Listing.views_count.desc(), Listing.created_at.desc())
        .limit(limit)
    )
    rows = (await db.scalars(stmt)).all()

    return RecommendationResult(
        listing_ids=[r.id for r in rows],
        scores={str(r.id): 1.0 for r in rows},
        reason="Popular listings",
    )


# ---------------------------------------------------------------------------
# Optional: comparable price fetch for fraud_detection
# ---------------------------------------------------------------------------

async def fetch_comparable_prices(
    db: AsyncSession,
    *,
    city: str,
    state: str,
    purpose: ListingPurpose,
    bedrooms: int | None,
    limit: int = 50,
) -> list[Decimal]:
    """Return recent active prices in the same city/state for a given purpose.

    Used by ``fraud_detection.score_listing`` to build a market median.
    Kept here because it shares the price-band logic.
    """
    stmt = (
        select(Listing.price)
        .join(Property, Property.id == Listing.property_id)
        .where(
            Listing.status == ListingStatus.ACTIVE,
            Listing.purpose == purpose,
            or_(
                and_(Property.city == city, Property.state == state),
                Property.city == city,
            ),
        )
        .order_by(Listing.created_at.desc())
        .limit(limit)
    )
    if bedrooms is not None:
        # Coarse filter: within ±1 bedroom
        stmt = stmt.where(
            Property.bedrooms.between(max(0, bedrooms - 1), bedrooms + 1)
        )

    rows = (await db.scalars(stmt)).all()
    return [r for r in rows if r is not None]