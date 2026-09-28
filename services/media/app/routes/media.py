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
from app.services import record_store
from app.workers.tasks import process_media
from app.services.verification import verify_location
from app.core.errors import MediaError

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
        raise MediaError(
            code= "UNSUPPORTED_FILE_TYPE",
            message=f"Unsupported file type: {file.content_type}",
            status_code=400,
            details={
                "received": file.content_type,
                "allowed": sorted(ALLOWED_CONTENT_TYPES),
            },
            )

    if not file.filename:
        raise MediaError(
            code="MISSING_FILENAME",
            message="A filename is required",
            status_code=400,
        )   
     # --- 2. Save ---
    media_id = str(uuid.uuid4())
    try:
        path, sha256, size_bytes = storage.save(file, subdir=media_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage failed: {e}")

    # --- 3. Enforce size limit (after save so we know the real size) ---
    if size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
        storage.delete(path)
        raise MediaError(
            code="FILE_TOO_LARGE",
            message=f"File exceeds {MAX_FILE_SIZE_MB} MB.",
            status_code=400,
            details={"max_mb": MAX_FILE_SIZE_MB, "actual_bytes": size_bytes},
        )

    # For storage failure, dont leak internals - log server-side, generic client message
    try:
        path,sha256,size_bytes = storage.save(file, subdir=media_id)
    except Exception  as e:
        # In a real app: logger.exception("Storage failed", extra=["media_id": media_id])
        raise MediaError(
            code="STORAGE_FAILED",
            message="Could not save the file. Please try again.",
            status_code=500,
        )
    # --- 4. Build GPS objects ---
    gps = None
    if gps_lat is not None and gps_lng is not None:
        gps = GPSPoint(lat=gps_lat, lng=gps_lng)

    property_gps = None
    if property_lat is not None and property_lng is not None:
        property_gps = GPSPoint(lat=property_lat, lng=property_lng)
    record = MediaRecord(
        id=media_id,
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        path=str(path),
        thumbnail_path=None,          # worker fills in
        metadata={},                  # worker fills in
        gps=gps,                      
        property_gps=property_gps,
        verification=None,            # worker fills in
        status="processing",          # worker will set to "ready"
        created_at=datetime.now(timezone.utc),
    )

    # --- 5. Persist BEFORE enqueue (worker might pick up instantly) ---
    record_store.save(record)

    # --- 6. Enqueue the background job ---
    process_media.delay(media_id)

    return record


@router.get("/{media_id}", response_model=MediaRecord)
def get_media(media_id: str):
    """Fetch a previously uploaded media record by ID."""
    record = record_store.get(media_id)
    if record is None:
        raise MediaError(
            code="MEDIA_NOT_FOUND",
            message=f"No media found with it {media_id}.",
            status_code=404,
        )
    return record


@router.get("", response_model=list[MediaRecord])
def list_media():
    """List all uploaded media. Handy for dev/testing."""
    return record_store.list_all()