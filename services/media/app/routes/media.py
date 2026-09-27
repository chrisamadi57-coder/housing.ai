"""
HTTP routes for media upload, retrieval, and (later) status polling.

This file is the HTTP layer — it validates the request, calls the services
(storage, metadata), builds a MediaRecord, and returns JSON.

Storage is currently in-memory (MEDIA_DB). When Person 2's PostgreSQL
layer is ready, replace MEDIA_DB with real DB queries. Everything else
stays the same.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models import GPSPoint, MediaRecord
from app.services.metadata import extract_image_metadata, make_thumbnail
from app.services.storage import storage
from app.services.verification import verify_location

router = APIRouter()

# --- Configuration ---
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
}
MAX_FILE_SIZE_MB = 50
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

# --- In-memory store (replaced by DB later) ---
MEDIA_DB: dict[str, MediaRecord] = {}


@router.post("/upload", response_model=MediaRecord, status_code=201)
async def upload_media(
    file: UploadFile = File(..., description="Image or video file"),
    gps_lat: Optional[float] = Form(None, description="Capture latitude"),
    gps_lng: Optional[float] = Form(None, description="Capture longitude"),
    property_lat: Optional[float] = Form(None, description="Property latitude"),
    property_lng: Optional[float] = Form(None, description="Property longitude"),
):
    """
    Upload a media file for a property listing.

    Steps:
      1. Validate content type and filename
      2. Save to storage (returns path, sha256, size)
      3. Enforce max size
      4. Extract image metadata + generate thumbnail (images only)
      5. Build a MediaRecord and store it
      6. Return the record
    """

    # --- 1. Validate content type ---
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Allowed: {sorted(ALLOWED_CONTENT_TYPES)}",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # --- 2. Save ---
    media_id = str(uuid.uuid4())
    try:
        path, sha256, size_bytes = storage.save(file, subdir=media_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage failed: {e}")

    # --- 3. Enforce size limit (after save so we know the real size) ---
    if size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
        storage.delete(path)
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {MAX_FILE_SIZE_MB} MB",
        )

    # --- 4. Metadata + thumbnail (images only for now) ---
    metadata: dict = {}
    thumbnail_path: Optional[str] = None

    if file.content_type in IMAGE_TYPES:
        metadata = extract_image_metadata(path)
        if "error" not in metadata:
            try:
                thumb = make_thumbnail(path)
                thumbnail_path = str(thumb)
            except Exception as e:
                # Don't fail the whole upload for a thumbnail issue
                metadata["thumbnail_error"] = str(e)

    # --- 5. Build record ---
    gps = None
    if gps_lat is not None and gps_lng is not None:
        gps = GPSPoint(lat=gps_lat, lng=gps_lng)
    # --- 6. Location verification (only when we have both sides) ---
    verification = None
    if gps and property_lat is not None and property_lng is not None:
        try:
            verification = verify_location(
                upload_gps={"lat": gps_lat, "lng": property_lng},
                property_gps={"lat": property_lat, "lng": property_lng}
            )
        except Exception as e:
            # Never let verification failure kill the upload
            verification = {
                "verified": False,
                "reason": f"Verification error: {type(e).__name__}: {e}",
            }
    record = MediaRecord(
        id=media_id,
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        path=str(path),
        thumbnail_path=thumbnail_path,
        metadata=metadata,
        gps=gps,
        verification=verification,       # filled in during Phase 2
        status="ready" if "error" not in metadata else "failed",
        created_at=datetime.now(timezone.utc),
    )

    MEDIA_DB[media_id] = record
    return record


@router.get("/{media_id}", response_model=MediaRecord)
def get_media(media_id: str):
    """Fetch a previously uploaded media record by ID."""
    if media_id not in MEDIA_DB:
        raise HTTPException(status_code=404, detail="Media not found")
    return MEDIA_DB[media_id]


@router.get("", response_model=list[MediaRecord])
def list_media():
    """List all uploaded media. Handy for dev/testing."""
    return list(MEDIA_DB.values())