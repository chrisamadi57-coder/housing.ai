"""Property service — CRUD for the physical asset."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.celery_app import TASK_NAMES, dispatch
from app.core.exceptions import NotFoundError
from app.models.enums import ListingStatus
from app.models.listing import Listing
from app.models.property import Property
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.property import PropertyCreate, PropertyRead, PropertyUpdate
from app.services._helpers import authorize_owner_or_admin, paginate


class PropertyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _base_stmt(self):
        """Property + media + owner, since PropertyRead embeds both."""
        return select(Property).options(
            selectinload(Property.media),
            selectinload(Property.owner),
        )

    async def _get_or_404(self, property_id: UUID) -> Property:
        stmt = self._base_stmt().where(Property.id == property_id)
        prop = await self.db.scalar(stmt)
        if not prop:
            raise NotFoundError("Property not found")
        return prop

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def create(self, payload: PropertyCreate, owner_id: UUID) -> Property:
        prop = Property(**payload.model_dump(), owner_id=owner_id)
        self.db.add(prop)
        await self.db.commit()
        await self.db.refresh(prop, attribute_names=["media", "owner"])

        # Background: geocode + location verification + fraud analysis.
        # The API never blocks on any of this.
        dispatch(TASK_NAMES.VERIFY_LOCATION, property_id=str(prop.id))
        dispatch(TASK_NAMES.RUN_AI_ANALYSIS, property_id=str(prop.id))

        return prop

    async def get(self, property_id: UUID) -> Property:
        return await self._get_or_404(property_id)

    async def list_public(
        self,
        *,
        page: int,
        size: int,
        city: str | None = None,
        state: str | None = None,
    ) -> PaginatedResponse[PropertyRead]:
        """Properties that have at least one ACTIVE listing — i.e. visible stock."""
        stmt = (
            self._base_stmt()
            .join(Listing, Listing.property_id == Property.id)
            .where(Listing.status == ListingStatus.ACTIVE)
            .distinct()
        )
        if city:
            stmt = stmt.where(Property.city.ilike(f"%{city}%"))
        if state:
            stmt = stmt.where(Property.state.ilike(f"%{state}%"))

        total = await self.db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0
        rows = (
            await self.db.scalars(
                stmt.order_by(Property.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()
        return paginate(list(rows), total, page, size)

    async def list_by_owner(
        self, owner_id: UUID, *, page: int, size: int
    ) -> PaginatedResponse[PropertyRead]:
        stmt = self._base_stmt().where(Property.owner_id == owner_id)
        total = await self.db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0
        rows = (
            await self.db.scalars(
                stmt.order_by(Property.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()
        return paginate(list(rows), total, page, size)

    async def update(
        self, property_id: UUID, payload: PropertyUpdate, *, actor: User
    ) -> Property:
        prop = await self._get_or_404(property_id)
        authorize_owner_or_admin(actor, prop.owner_id)

        changed = payload.model_dump(exclude_unset=True)
        for field, value in changed.items():
            setattr(prop, field, value)
        await self.db.commit()
        await self.db.refresh(prop, attribute_names=["media", "owner"])

        # If the address changed, re-geocode.
        if {"address", "city", "state", "country"} & changed.keys():
            dispatch(TASK_NAMES.VERIFY_LOCATION, property_id=str(prop.id))

        return prop

    async def delete(self, property_id: UUID, *, actor: User) -> None:
        prop = await self._get_or_404(property_id)
        authorize_owner_or_admin(actor, prop.owner_id)
        await self.db.delete(prop)
        await self.db.commit()