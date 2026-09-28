"""User model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.listing import Listing
    from app.models.property import Property
    from app.models.verification import Verification


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    # ---- Identity -------------------------------------------------------
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # ---- Profile --------------------------------------------------------
    avatar_url: Mapped[str | None] = mapped_column(String(1000))
    bio: Mapped[str | None] = mapped_column(String(1000))

    # ---- Access ---------------------------------------------------------
    role: Mapped[UserRole] = mapped_column(
        default=UserRole.USER, server_default=UserRole.USER.value, index=True, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # ---- Relationships --------------------------------------------------
    properties: Mapped[list["Property"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    listings: Mapped[list["Listing"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    verified_properties: Mapped[list["Verification"]] = relationship(
        back_populates="verified_by",
        foreign_keys="Verification.verified_by_id",
    )

    __table_args__ = (
        Index("ix_users_role_active", "role", "is_active"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} role={self.role.value}>"