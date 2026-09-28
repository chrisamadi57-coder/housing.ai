"""Pydantic schemas package.

Re-exports every public schema so callers can import from ``app.schemas``
directly. Keeping this file accurate is worth it — one import surface
across the whole codebase.
"""

from app.schemas.common import (
    ErrorResponse,
    MessageResponse,
    PaginatedResponse,
    PaginationParams,
)
from app.schemas.listing import (
    ListingCreate,
    ListingRead,
    ListingSummary,
    ListingUpdate,
)
from app.schemas.media import (
    MediaCreate,
    MediaRead,
    MediaReorderRequest,
    MediaUpdate,
)
from app.schemas.property import (
    PropertyCreate,
    PropertyRead,
    PropertySummary,
    PropertyUpdate,
)
from app.schemas.search import (
    ParsedSearchFilters,
    SearchRequest,
    SearchResponse,
)
from app.schemas.user import (
    TokenPair,
    TokenPayload,
    UserCreate,
    UserLogin,
    UserRead,
    UserSummary,
    UserUpdate,
)
from app.schemas.verification import (
    VerificationCreate,
    VerificationRead,
    VerificationUpdate,
)

__all__ = [
    # common
    "ErrorResponse",
    "MessageResponse",
    "PaginatedResponse",
    "PaginationParams",
    # user
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserRead",
    "UserSummary",
    "TokenPair",
    "TokenPayload",
    # property
    "PropertyCreate",
    "PropertyUpdate",
    "PropertyRead",
    "PropertySummary",
    # listing
    "ListingCreate",
    "ListingUpdate",
    "ListingRead",
    "ListingSummary",
    # media
    "MediaCreate",
    "MediaUpdate",
    "MediaRead",
    "MediaReorderRequest",
    # verification
    "VerificationCreate",
    "VerificationUpdate",
    "VerificationRead",
    # search
    "SearchRequest",
    "SearchResponse",
    "ParsedSearchFilters",
]