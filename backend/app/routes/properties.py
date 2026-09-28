"""Property routes: CRUD for the physical asset."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.property import PropertyCreate, PropertyRead, PropertyUpdate
from app.services.property_service import PropertyService

router = APIRouter(prefix="/properties", tags=["properties"])


@router.post("", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
async def create_property(
    payload: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> PropertyRead:
    return await PropertyService(db).create(payload, owner_id=current.id)


@router.get("", response_model=PaginatedResponse[PropertyRead])
async def list_properties(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    city: str | None = Query(None),
    state: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[PropertyRead]:
    return await PropertyService(db).list_public(
        page=page, size=size, city=city, state=state
    )


@router.get("/mine", response_model=PaginatedResponse[PropertyRead])
async def list_my_properties(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> PaginatedResponse[PropertyRead]:
    return await PropertyService(db).list_by_owner(current.id, page=page, size=size)


@router.get("/{property_id}", response_model=PropertyRead)
async def get_property(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PropertyRead:
    return await PropertyService(db).get(property_id)


@router.patch("/{property_id}", response_model=PropertyRead)
async def update_property(
    property_id: UUID,
    payload: PropertyUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> PropertyRead:
    return await PropertyService(db).update(property_id, payload, actor=current)


@router.delete("/{property_id}", response_model=MessageResponse)
async def delete_property(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> MessageResponse:
    await PropertyService(db).delete(property_id, actor=current)
    return MessageResponse(message="Property deleted")