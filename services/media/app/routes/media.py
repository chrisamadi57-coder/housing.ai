"""
HTTP routes for media upload, retrieval, and status polling.

This file is the HTTP layer — it validates the request, saves the file,
builds a MediaRecord, enqueues a background job, and returns JSON.

The heavy lifting (metadata extraction, thumbnail generation, verification)
is done by the Celery worker in app/workers/tasks.py. The route returns
immediately with status="processing".

Records are stored in Redis via app/services/record_store.py.
When Person 2's PostgreSQL layer is ready, swap record_store's internals
for SQL queries. This file will not change.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.core.errors import MediaError
from app.models import GPSPoint, MediaRecord
from app.services import record_store
from app.services.storage import storage
from app.workers.tasks import process_media

router = APIRouter()

# --- Configuration ---
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
}
MAX_FILE_SIZE_MB = 50


@router.post("/upload", response_model=MediaRecord, status_code=201)
def upload_media(
    file: UploadFile = File(..., description="Image or video file"),
    gps_lat: Optional[float] = Form(None, description="Capture latitude"),
    gps_lng: Optional[float] = Form(None, description="Capture longitude"),
    property_lat: Optional[float] = Form(None, description="Property latitude"),
    property_lng: Optional[float] = Form(None, description="Property longitude"),
):
    """
    Upload a media file for a property listing.

    Returns a MediaRecord with status="processing". A background worker
    will complete metadata extraction, thumbnail generation, and location
    verification, then flip the status to "ready". Poll
    GET /media/{id}/status to check progress.
    """

    # --- 1. Validate ---
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise MediaError(
            code="UNSUPPORTED_FILE_TYPE",
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
            message="A filename is required.",
            status_code=400,
        )

    # --- 2. Save to storage ---
    media_id = str(uuid.uuid4())
    try:
        path, sha256, size_bytes = storage.save(file, subdir=media_id)
    except Exception:
        # Never leak internals to the client. Log server-side, generic message out.
        # TODO: replace with proper logger once we set up logging.
        raise MediaError(
            code="STORAGE_FAILED",
            message="Could not save the file. Please try again.",
            status_code=500,
        )

    # --- 3. Enforce size limit (after save so we know the real size) ---
    if size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
        storage.delete(path)
        raise MediaError(
            code="FILE_TOO_LARGE",
            message=f"File exceeds {MAX_FILE_SIZE_MB} MB.",
            status_code=400,
            details={"max_mb": MAX_FILE_SIZE_MB, "actual_bytes": size_bytes},
        )

    # --- 4. Build GPS objects ---
    gps = None
    if gps_lat is not None and gps_lng is not None:
        gps = GPSPoint(lat=gps_lat, lng=gps_lng)

    property_gps = None
    if property_lat is not None and property_lng is not None:
        property_gps = GPSPoint(lat=property_lat, lng=property_lng)

    # --- 5. Build record ---
    record = MediaRecord(
        id=media_id,
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        path=str(path),
        thumbnail_path=None,       # worker fills in
        metadata={},               # worker fills in
        gps=gps,
        property_gps=property_gps,
        verification=None,         # worker fills in
        status="processing",       # worker will set to "ready"
        stage="received",          # worker advances through stages
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # --- 6. Persist BEFORE enqueue (worker might pick up instantly) ---
    record_store.save(record)

    # --- 7. Enqueue the background job ---
    process_media.delay(media_id)

    return record


@router.get("/{media_id}/status")
def media_status(media_id: str):
    """
    Lightweight polling endpoint.

    The frontend calls this repeatedly after upload until `ready` is True,
    then fetches the full record via GET /media/{media_id}.
    """
    record = record_store.get(media_id)
    if record is None:
        raise MediaError(
            code="MEDIA_NOT_FOUND",
            message=f"No media found with id {media_id}.",
            status_code=404,
        )

    return {
        "media_id": record.id,
        "status": record.status,
        "stage": record.stage,
        "ready": record.status == "ready",
        "failed": record.status == "failed",
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "error": record.error,
    }


@router.get("/{media_id}", response_model=MediaRecord)
def get_media(media_id: str):
    """Fetch a previously uploaded media record by ID."""
    record = record_store.get(media_id)
    if record is None:
        raise MediaError(
            code="MEDIA_NOT_FOUND",
            message=f"No media found with id {media_id}.",
            status_code=404,
        )
    return record


@router.get("", response_model=list[MediaRecord])
def list_media():
    """List all uploaded media. Handy for dev/testing."""
    return record_store.list_all()