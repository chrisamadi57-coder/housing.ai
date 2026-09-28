"""Property model — the physical asset, independent of any listing."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from geoalchemy2 import Geography
from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import PropertyType

if TYPE_CHECKING:
    from app.models.listing import Listing
    from app.models.media import Media
    from app.models.user import User
    from app.models.verification import Verification


class Property(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "properties"

    # ---- Content --------------------------------------------------------
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    property_type: Mapped[PropertyType] = mapped_column(index=True, nullable=False)

    # ---- Physical attributes -------------------------------------------
    bedrooms: Mapped[int | None] = mapped_column(index=True)
    bathrooms: Mapped[int | None]
    toilets: Mapped[int | None]
    area_sqm: Mapped[float | None] = mapped_column(Float)
    year_built: Mapped[int | None]
    is_furnished: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)

    # ---- Location -------------------------------------------------------
    address: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    city: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    country: Mapped[str] = mapped_column(String(120), default="Nigeria", server_default="Nigeria", nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20))

    latitude: Mapped[float | None] = mapped_column(Float, index=True)
    longitude: Mapped[float | None] = mapped_column(Float, index=True)

    # PostGIS POINT(4326) — populated by the location_verification worker.
    # Nullable until geocoding succeeds. Indexed via GIST below.
    location: Mapped[str | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )

    # ---- Ownership ------------------------------------------------------
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    owner: Mapped["User"] = relationship(back_populates="properties")
    listings: Mapped[list["Listing"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    media: Mapped[list["Media"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Media.order_index",
    )
    verification: Mapped["Verification | None"] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

    __table_args__ = (
        Index("ix_properties_city_state", "city", "state"),
        Index("ix_properties_type_city", "property_type", "city"),
        # GIST index for geo radius queries — only meaningful once location is set.
        Index(
            "ix_properties_location_gist",
            "location",
            postgresql_using="gist",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Property {self.title!r} city={self.city}>"