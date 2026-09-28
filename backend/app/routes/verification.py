"""Verification routes — trust / fraud / location confirmation.

Read endpoints are public. Write endpoints are owner-or-admin for the
initial request, and admin-only for status transitions.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.enums import UserRole, VerificationStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.verification import (
    VerificationCreate,
    VerificationRead,
    VerificationUpdate,
)
from app.services.verification_service import VerificationService

router = APIRouter(prefix="/verifications", tags=["verifications"])


@router.post("", response_model=VerificationRead, status_code=status.HTTP_201_CREATED)
async def request_verification(
    payload: VerificationCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> VerificationRead:
    """Owner requests verification for their property."""
    return await VerificationService(db).request(payload, actor=current)


@router.get("", response_model=PaginatedResponse[VerificationRead])
async def list_verifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: VerificationStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.ADMIN)),
) -> PaginatedResponse[VerificationRead]:
    """Admin: list all verification records."""
    return await VerificationService(db).list(page=page, size=size, status=status_filter)


@router.get("/property/{property_id}", response_model=VerificationRead)
async def get_by_property(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> VerificationRead:
    """Public: anyone can see a property's verification record."""
    return await VerificationService(db).get_by_property(property_id)


@router.patch("/{verification_id}", response_model=VerificationRead)
async def update_verification(
    verification_id: UUID,
    payload: VerificationUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_role(UserRole.ADMIN)),
) -> VerificationRead:
    """Admin: update status, location confirmation, notes."""
    return await VerificationService(db).update(verification_id, payload, actor=current)