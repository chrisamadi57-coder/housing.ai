"""Verification service — trust / fraud / location confirmation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import TASK_NAMES, dispatch
from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import VerificationStatus
from app.models.property import Property
from app.models.user import User
from app.models.verification import Verification
from app.schemas.common import PaginatedResponse
from app.schemas.verification import (
    VerificationCreate,
    VerificationRead,
    VerificationUpdate,
)
from app.services._helpers import authorize_owner_or_admin, paginate


class VerificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    async def _get_or_404(self, verification_id: UUID) -> Verification:
        v = await self.db.get(Verification, verification_id)
        if not v:
            raise NotFoundError("Verification not found")
        return v

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def request(self, payload: VerificationCreate, *, actor: User) -> Verification:
        prop = await self.db.get(Property, payload.property_id)
        if not prop:
            raise NotFoundError("Property not found")
        authorize_owner_or_admin(actor, prop.owner_id)

        # One verification per property (unique constraint enforces this too).
        existing = await self.db.scalar(
            select(Verification).where(Verification.property_id == payload.property_id)
        )
        if existing:
            if existing.status in (VerificationStatus.PENDING, VerificationStatus.IN_PROGRESS):
                raise ConflictError("Verification already in progress")
            if existing.status == VerificationStatus.VERIFIED:
                raise ConflictError("Property is already verified")
            # REJECTED — allow resubmission by updating in place.
            existing.status = VerificationStatus.PENDING
            existing.document_urls = [
                d.model_dump() for d in payload.document_urls
            ] or None
            existing.notes = payload.notes
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        v = Verification(
            property_id=payload.property_id,
            status=VerificationStatus.PENDING,
            document_urls=[d.model_dump() for d in payload.document_urls] or None,
            notes=payload.notes,
        )
        self.db.add(v)
        await self.db.commit()
        await self.db.refresh(v)

        # Kick off location + fraud checks.
        dispatch(TASK_NAMES.VERIFY_LOCATION, property_id=str(prop.id))
        dispatch(TASK_NAMES.RUN_AI_ANALYSIS, property_id=str(prop.id))
        return v

    async def get_by_property(self, property_id: UUID) -> Verification:
        v = await self.db.scalar(
            select(Verification).where(Verification.property_id == property_id)
        )
        if not v:
            raise NotFoundError("No verification record for this property")
        return v

    async def list(
        self,
        *,
        page: int,
        size: int,
        status: VerificationStatus | None = None,
    ) -> PaginatedResponse[VerificationRead]:
        stmt = select(Verification)
        if status:
            stmt = stmt.where(Verification.status == status)

        total = await self.db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0
        rows = (
            await self.db.scalars(
                stmt.order_by(Verification.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()
        return paginate(list(rows), total, page, size)

    async def update(
        self, verification_id: UUID, payload: VerificationUpdate, *, actor: User
    ) -> Verification:
        v = await self._get_or_404(verification_id)

        changes = payload.model_dump(exclude_unset=True)
        if "document_urls" in changes and changes["document_urls"] is not None:
            changes["document_urls"] = [
                d.model_dump() if hasattr(d, "model_dump") else d
                for d in changes["document_urls"]
            ]

        # Whenever an admin flips status to a terminal value, stamp the reviewer.
        if changes.get("status") in (VerificationStatus.VERIFIED, VerificationStatus.REJECTED):
            v.verified_by_id = actor.id

        for field, value in changes.items():
            setattr(v, field, value)

        await self.db.commit()
        await self.db.refresh(v)

        # Notify the property owner of the outcome.
        if "status" in changes:
            prop = await self.db.get(Property, v.property_id)
            if prop:
                dispatch(
                    TASK_NAMES.SEND_NOTIFICATION,
                    user_id=str(prop.owner_id),
                    template="verification_update",
                    payload={"property_id": str(prop.id), "status": v.status.value},
                )

        return v