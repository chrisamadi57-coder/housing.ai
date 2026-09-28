"""SQLAlchemy models package.

Import every model here so that ``Base.metadata`` is fully populated
before Alembic autogenerate runs.
"""

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    ListingPurpose,
    ListingStatus,
    MediaType,
    PropertyType,
    UserRole,
    VerificationStatus,
)
from app.models.listing import Listing
from app.models.media import Media
from app.models.property import Property
from app.models.user import User
from app.models.verification import Verification

__all__ = [
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "User",
    "Property",
    "Listing",
    "Media",
    "Verification",
    "UserRole",
    "PropertyType",
    "ListingPurpose",
    "ListingStatus",
    "MediaType",
    "VerificationStatus",
]