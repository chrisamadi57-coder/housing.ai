"""Media routes: attach images/videos to properties.

Two-step flow:
  1. Client requests a presigned URL (POST /media/upload-url).
  2. Client uploads the file directly to storage.
  3. Client links the result to a property (POST /properties/{id}/media).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.enums import MediaType
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.media import (
    MediaCreate,
    MediaRead,
    MediaReorderRequest,
    MediaUpdate,
)
from app.services.media_service import MediaService

router = APIRouter(tags=["media"])


# ---- Direct upload (multipart) --------------------------------------------
# Simpler for local dev; swap to presigned URLs for production S3.

@router.post(
    "/properties/{property_id}/media/upload",
    response_model=MediaRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_media(
    property_id: UUID,
    file: UploadFile = File(...),
    media_type: MediaType = Form(MediaType.IMAGE),
    order_index: int = Form(0),
    is_cover: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> MediaRead:
    return await MediaService(db).upload(
        property_id=property_id,
        file=file,
        media_type=media_type,
        order_index=order_index,
        is_cover=is_cover,
        actor=current,
    )


# ---- Link an already-uploaded file ----------------------------------------

@router.post(
    "/properties/{property_id}/media",
    response_model=MediaRead,
    status_code=status.HTTP_201_CREATED,
)
async def link_media(
    property_id: UUID,
    payload: MediaCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> MediaRead:
    return await MediaService(db).link(property_id, payload, actor=current)


@router.get("/properties/{property_id}/media", response_model=list[MediaRead])
async def list_media(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[MediaRead]:
    return await MediaService(db).list_for_property(property_id)


@router.patch("/media/{media_id}", response_model=MediaRead)
async def update_media(
    media_id: UUID,
    payload: MediaUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> MediaRead:
    return await MediaService(db).update(media_id, payload, actor=current)


@router.delete("/media/{media_id}", response_model=MessageResponse)
async def delete_media(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> MessageResponse:
    await MediaService(db).delete(media_id, actor=current)
    return MessageResponse(message="Media deleted")


@router.post(
    "/properties/{property_id}/media/reorder",
    response_model=list[MediaRead],
)
async def reorder_media(
    property_id: UUID,
    payload: MediaReorderRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[MediaRead]:
    return await MediaService(db).reorder(property_id, payload.media_ids, actor=current)