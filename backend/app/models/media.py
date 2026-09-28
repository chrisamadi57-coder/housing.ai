"""Media model — images, videos, docs attached to a Property."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import MediaType

if TYPE_CHECKING:
    from app.models.property import Property


class Media(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "media"

    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # ---- Storage --------------------------------------------------------
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000))
    storage_key: Mapped[str | None] = mapped_column(String(500), index=True)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(Integer)

    media_type: Mapped[MediaType] = mapped_column(
        default=MediaType.IMAGE,
        server_default=MediaType.IMAGE.value,
        index=True,
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # ---- Pipeline state (written by workers/media_processing.py) --------
    processed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, index=True
    )
    processing_error: Mapped[str | None] = mapped_column(String(500))

    # ---- AI annotations (written by workers/ai_analysis.py) -------------
    ai_labels: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ai_quality_score: Mapped[float | None] = mapped_column(Float)
    ai_caption: Mapped[str | None] = mapped_column(String(500))

    # ---- Relationships --------------------------------------------------
    property: Mapped["Property"] = relationship(back_populates="media")

    __table_args__ = (
        UniqueConstraint("property_id", "order_index", name="uq_media_property_order"),
        Index("ix_media_property_type", "property_id", "media_type"),
        # At most one cover per property (partial unique index).
        Index(
            "uq_media_property_cover",
            "property_id",
            unique=True,
            postgresql_where="is_cover = true",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Media {self.media_type.value} order={self.order_index} url={self.url[:40]}...>"