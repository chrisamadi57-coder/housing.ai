"""Media service — attach images/videos to properties, dispatch processing."""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import TASK_NAMES, dispatch
from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import MediaType
from app.models.media import Media
from app.models.property import Property
from app.models.user import User
from app.services._helpers import authorize_owner_or_admin

ALLOWED_MIME = {
    MediaType.IMAGE: {"image/jpeg", "image/png", "image/webp"},
    MediaType.VIDEO: {"video/mp4", "video/quicktime"},
    MediaType.DOCUMENT: {"application/pdf"},
    MediaType.FLOOR_PLAN: {"image/jpeg", "image/png", "application/pdf"},
}

MAX_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class MediaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    async def _property_or_404(self, property_id: UUID) -> Property:
        prop = await self.db.get(Property, property_id)
        if not prop:
            raise NotFoundError("Property not found")
        return prop

    async def _media_or_404(self, media_id: UUID) -> Media:
        media = await self.db.get(Media, media_id)
        if not media:
            raise NotFoundError("Media not found")
        return media

    def _validate_file(self, file: UploadFile, media_type: MediaType) -> None:
        allowed = ALLOWED_MIME.get(media_type, set())
        if file.content_type not in allowed:
            raise ValidationError(
                f"Unsupported content type {file.content_type!r} for {media_type.value}"
            )

    def _save_local(self, file: UploadFile, property_id: UUID) -> tuple[str, str, int]:
        """Dev-only local storage. Swap for S3/Cloudinary in production."""
        root = Path(settings.MEDIA_ROOT)
        root.mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename or "").suffix or ".bin"
        key = f"{property_id}/{uuid.uuid4().hex}{ext}"
        dest = root / key
        dest.parent.mkdir(parents=True, exist_ok=True)

        contents = file.file.read()
        dest.write_bytes(contents)

        url = f"{settings.MEDIA_URL_BASE.rstrip('/')}/{key}"
        return url, key, len(contents)

    async def _clear_existing_cover(self, property_id: UUID) -> None:
        """At most one cover per property — enforced by a partial unique index too."""
        stmt = select(Media).where(Media.property_id == property_id, Media.is_cover.is_(True))
        for m in (await self.db.scalars(stmt)).all():
            m.is_cover = False

    async def _next_order_index(self, property_id: UUID) -> int:
        current_max = await self.db.scalar(
            select(func.max(Media.order_index)).where(Media.property_id == property_id)
        )
        return (current_max or -1) + 1

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def upload(
        self,
        *,
        property_id: UUID,
        file: UploadFile,
        media_type: MediaType,
        order_index: int,
        is_cover: bool,
        actor: User,
    ) -> Media:
        prop = await self._property_or_404(property_id)
        authorize_owner_or_admin(actor, prop.owner_id)
        self._validate_file(file, media_type)

        url, storage_key, size = self._save_local(file, property_id)

        if is_cover:
            await self._clear_existing_cover(property_id)

        media = Media(
            property_id=property_id,
            url=url,
            storage_key=storage_key,
            mime_type=file.content_type,
            size_bytes=size,
            media_type=media_type,
            order_index=order_index,
            is_cover=is_cover,
            processed=False,
        )
        self.db.add(media)
        await self.db.commit()
        await self.db.refresh(media)

        # Person 3 handles thumbnails, compression, AI labels.
        dispatch(TASK_NAMES.PROCESS_MEDIA, media_id=str(media.id))
        return media

    async def link(self, property_id: UUID, payload, *, actor: User) -> Media:
        """Attach an already-uploaded file (client uploaded directly to storage)."""
        prop = await self._property_or_404(property_id)
        authorize_owner_or_admin(actor, prop.owner_id)

        if payload.is_cover:
            await self._clear_existing_cover(property_id)

        media = Media(
            property_id=property_id,
            url=str(payload.url),
            thumbnail_url=str(payload.thumbnail_url) if payload.thumbnail_url else None,
            storage_key=payload.storage_key,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            media_type=payload.media_type,
            order_index=payload.order_index,
            is_cover=payload.is_cover,
            processed=False,
        )
        self.db.add(media)
        await self.db.commit()
        await self.db.refresh(media)

        dispatch(TASK_NAMES.PROCESS_MEDIA, media_id=str(media.id))
        return media

    async def list_for_property(self, property_id: UUID) -> list[Media]:
        stmt = (
            select(Media)
            .where(Media.property_id == property_id)
            .order_by(Media.order_index.asc())
        )
        return list((await self.db.scalars(stmt)).all())

    async def update(self, media_id: UUID, payload, *, actor: User) -> Media:
        media = await self._media_or_404(media_id)
        prop = await self._property_or_404(media.property_id)
        authorize_owner_or_admin(actor, prop.owner_id)

        changes = payload.model_dump(exclude_unset=True)
        if changes.get("is_cover") is True:
            await self._clear_existing_cover(media.property_id)

        for field, value in changes.items():
            if field == "thumbnail_url" and value is not None:
                value = str(value)
            setattr(media, field, value)
        await self.db.commit()
        await self.db.refresh(media)
        return media

    async def delete(self, media_id: UUID, *, actor: User) -> None:
        media = await self._media_or_404(media_id)
        prop = await self._property_or_404(media.property_id)
        authorize_owner_or_admin(actor, prop.owner_id)
        await self.db.delete(media)
        await self.db.commit()

    async def reorder(
        self, property_id: UUID, media_ids: list[UUID], *, actor: User
    ) -> list[Media]:
        prop = await self._property_or_404(property_id)
        authorize_owner_or_admin(actor, prop.owner_id)

        stmt = select(Media).where(Media.property_id == property_id)
        rows = {m.id: m for m in (await self.db.scalars(stmt)).all()}

        if set(media_ids) - set(rows.keys()):
            raise ValidationError("Some media IDs do not belong to this property")

        # Two-phase to avoid unique-constraint collisions during reorder.
        for idx, m in enumerate(rows.values()):
            m.order_index = 10_000 + idx
        await self.db.flush()

        for idx, mid in enumerate(media_ids):
            rows[mid].order_index = idx

        await self.db.commit()
        return await self.list_for_property(property_id)