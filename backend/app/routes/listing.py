"""Listing routes: commercial offers on properties."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.enums import ListingPurpose, ListingStatus
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.listing import ListingCreate, ListingRead, ListingUpdate
from app.services.listing_service import ListingService

router = APIRouter(prefix="/listings", tags=["listings"])


@router.post("", response_model=ListingRead, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: ListingCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ListingRead:
    return await ListingService(db).create(payload, owner_id=current.id)


@router.get("", response_model=PaginatedResponse[ListingRead])
async def list_listings(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    purpose: ListingPurpose | None = Query(None),
    status_filter: ListingStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ListingRead]:
    return await ListingService(db).list(
        page=page, size=size, purpose=purpose, status=status_filter
    )


@router.get("/{listing_id}", response_model=ListingRead)
async def get_listing(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ListingRead:
    return await ListingService(db).get(listing_id)


@router.patch("/{listing_id}", response_model=ListingRead)
async def update_listing(
    listing_id: UUID,
    payload: ListingUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ListingRead:
    return await ListingService(db).update(listing_id, payload, actor=current)


@router.delete("/{listing_id}", response_model=MessageResponse)
async def delete_listing(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> MessageResponse:
    await ListingService(db).delete(listing_id, actor=current)
    return MessageResponse(message="Listing deleted")


@router.post("/{listing_id}/publish", response_model=ListingRead)
async def publish_listing(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ListingRead:
    """DRAFT/PENDING → ACTIVE. Triggers AI analysis via worker."""
    return await ListingService(db).publish(listing_id, actor=current)


@router.post("/{listing_id}/archive", response_model=ListingRead)
async def archive_listing(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ListingRead:
    """Any status → ARCHIVED. Hides from public search."""
    return await ListingService(db).archive(listing_id, actor=current)