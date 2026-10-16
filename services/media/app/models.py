from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class GPSPoint(BaseModel):
    """A single geographic coordinate with optional capture time."""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")
    captured_at: Optional[datetime] = None


class MediaRecord(BaseModel):
    """Everything we know about one uploaded media file."""
    id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str

    # Storage location — local path now, R2 key later. Same field name either way.
    path: str
    thumbnail_path: Optional[str] = None

    # Extracted metadata (width, height, EXIF, duration for video, etc.)
    metadata: dict = Field(default_factory=dict)

    # Location proof — set if caller supplied GPS
    gps: Optional[GPSPoint] = None

    # The claimed location of the property this media is attached to
    # (used by the worker for verification). Optional -- listings may not have it yet.
    property_gps: Optional[GPSPoint] = None

    # Filled in during Phase 2 (GPS verification). Shape: {"verified": bool, "distance_meters": float, "reason": str}
    verification: Optional[dict] = None

    # Filled in during Phase 5 (fraud detection). Shape: {"risk_score": int, "signals": [...]}
    fraud: Optional[dict] = None

    # Lifecycle: pending → processing → ready | failed
    status: Literal["pending", "processing", "ready", "failed"] = "pending"

    # Stage of processing
    stage: Optional[str] = None

    updated_at: Optional[datetime] = None

    error: Optional[str] = None

    created_at: datetime