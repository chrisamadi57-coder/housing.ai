"""Shared schema primitives: pagination, error envelopes, generic responses."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query-string params for any paginated endpoint."""

    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard envelope for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class MessageResponse(BaseModel):
    """Simple acknowledgment response."""

    message: str


class ErrorResponse(BaseModel):
    """Uniform error envelope — mirrors core/exceptions.py handlers."""

    detail: str
    code: str | None = None