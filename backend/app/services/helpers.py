"""Internal helpers shared by service modules."""

from __future__ import annotations

from typing import TypeVar
from uuid import UUID

from app.core.exceptions import PermissionDeniedError
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import PaginatedResponse

T = TypeVar("T")


def paginate(items: list, total: int, page: int, size: int) -> PaginatedResponse:
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if total else 0,
    )


def authorize_owner_or_admin(actor: User, owner_id: UUID) -> None:
    if actor.role == UserRole.ADMIN:
        return
    if actor.id != owner_id:
        raise PermissionDeniedError("You do not have access to this resource")