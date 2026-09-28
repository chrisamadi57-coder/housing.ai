"""Listing service — commercial offers on properties."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.celery_app import TASK_NAMES, dispatch
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import ListingPurpose, ListingStatus
from app.models.listing import Listing
from app.models.property import Property
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.listing import ListingCreate, ListingRead, ListingUpdate
from app.services._helpers import authorize_owner_or_admin, paginate


class ListingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _base_stmt(self):
        return select(Listing).options(
            selectinload(Listing.property).selectinload(Property.media),
            selectinload(Listing.property).selectinload(Property.owner),
            selectinload(Listing.owner),
        )

    async def _get_or_404(self, listing_id: UUID) -> Listing:
        stmt = self._base_stmt().where(Listing.id == listing_id)
        listing = await self.db.scalar(stmt)
        if not listing:
            raise NotFoundError("Listing not found")
        return listing

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def create(self, payload: ListingCreate, owner_id: UUID) -> Listing:
        # The owner of the listing must own the underlying property.
        prop = await self.db.get(Property, payload.property_id)
        if not prop:
            raise NotFoundError("Property not found")
        if prop.owner_id != owner_id:
            raise ValidationError("You do not own this property")

        # A property can have at most one ACTIVE listing at a time.
        if payload.status == ListingStatus.ACTIVE:
            existing = await self.db.scalar(
                select(Listing).where(
                    Listing.property_id == payload.property_id,
                    Listing.status == ListingStatus.ACTIVE,
                )
            )
            if existing:
                raise ConflictError("Property already has an active listing")

        listing = Listing(
            **payload.model_dump(),
            owner_id=owner_id,
        )
        self.db.add(listing)
        await self.db.commit()
        await self.db.refresh(listing, attribute_names=["property", "owner"])

        if listing.status == ListingStatus.ACTIVE:
            dispatch(TASK_NAMES.RUN_AI_ANALYSIS, listing_id=str(listing.id))

        return listing

    async def get(self, listing_id: UUID) -> Listing:
        return await self._get_or_404(listing_id)

    async def list(
        self,
        *,
        page: int,
        size: int,
        purpose: ListingPurpose | None = None,
        status: ListingStatus | None = None,
    ) -> PaginatedResponse[ListingRead]:
        stmt = self._base_stmt()
        if purpose:
            stmt = stmt.where(Listing.purpose == purpose)
        if status:
            stmt = stmt.where(Listing.status == status)

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
        return paginate(list(rows), total, page, size)

    async def update(
        self, listing_id: UUID, payload: ListingUpdate, *, actor: User
    ) -> Listing:
        listing = await self._get_or_404(listing_id)
        authorize_owner_or_admin(actor, listing.owner_id)

        changed = payload.model_dump(exclude_unset=True)
        for field, value in changed.items():
            setattr(listing, field, value)
        await self.db.commit()
        await self.db.refresh(listing, attribute_names=["property", "owner"])
        return listing

    async def delete(self, listing_id: UUID, *, actor: User) -> None:
        listing = await self._get_or_404(listing_id)
        authorize_owner_or_admin(actor, listing.owner_id)
        await self.db.delete(listing)
        await self.db.commit()

    async def publish(self, listing_id: UUID, *, actor: User) -> Listing:
        listing = await self._get_or_404(listing_id)
        authorize_owner_or_admin(actor, listing.owner_id)

        if listing.status == ListingStatus.ACTIVE:
            return listing
        if listing.status in (ListingStatus.SOLD, ListingStatus.RENTED, ListingStatus.ARCHIVED):
            raise ConflictError(f"Cannot publish a {listing.status.value} listing")

        # Enforce "one active listing per property" on publish too.
        existing = await self.db.scalar(
            select(Listing).where(
                Listing.property_id == listing.property_id,
                Listing.status == ListingStatus.ACTIVE,
                Listing.id != listing.id,
            )
        )
        if existing:
            raise ConflictError("Property already has an active listing")

        listing.status = ListingStatus.ACTIVE
        await self.db.commit()
        await self.db.refresh(listing, attribute_names=["property", "owner"])

        dispatch(TASK_NAMES.RUN_AI_ANALYSIS, listing_id=str(listing.id))
        dispatch(TASK_NAMES.SEND_NOTIFICATION, user_id=str(actor.id), template="listing_published", payload={"listing_id": str(listing.id)})
        return listing

    async def archive(self, listing_id: UUID, *, actor: User) -> Listing:
        listing = await self._get_or_404(listing_id)
        authorize_owner_or_admin(actor, listing.owner_id)
        listing.status = ListingStatus.ARCHIVED
        await self.db.commit()
        await self.db.refresh(listing, attribute_names=["property", "owner"])
        return listing