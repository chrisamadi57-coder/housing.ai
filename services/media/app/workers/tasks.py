"""
Celery tasks — background work that runs in a separate process.

The pattern:
    routes/media.py saves a MediaRecord with status="processing", stage="received"
    routes/media.py calls process_media.delay(media_id) and returns 201
    a Celery worker picks up the job and calls process_media(media_id)
    process_media does the slow work, updates stage along the way, sets status="ready"

Storage modes:
    Local: the file is on disk at record.path — process it directly.
    S3:    record.path is an object key — download to a temp dir first,
           process there, and let Python delete the temp dir when done.

Stage progression:
    received → metadata → thumbnail → verification → done
    On error: stage="error", status="failed"
"""

import tempfile
from pathlib import Path

from app.config import settings
from app.services import record_store
from app.services.metadata import (
    extract_image_metadata,
    extract_video_metadata,
    make_thumbnail,
    make_video_thumbnail,
)
from app.services.storage import storage
from app.services.verification import verify_location
from app.workers.celery_app import celery_app


def _process_file(record, path: Path) -> None:
    """
    Extract metadata and generate a thumbnail for a local file.

    Mutates `record` in place — sets .metadata and .thumbnail_path.
    Used by both the image and video branches.
    """
    if record.content_type.startswith("image/"):
        record.stage = "metadata"
        record_store.save(record)

        record.metadata = extract_image_metadata(path)

        if "error" not in record.metadata:
            record.stage = "thumbnail"
            record_store.save(record)
            try:
                record.thumbnail_path = str(make_thumbnail(path))
            except Exception as e:
                record.metadata["thumbnail_error"] = f"{type(e).__name__}: {e}"

    elif record.content_type.startswith("video/"):
        record.stage = "metadata"
        record_store.save(record)

        record.metadata = extract_video_metadata(path)

        if "error" not in record.metadata:
            record.stage = "thumbnail"
            record_store.save(record)
            try:
                record.thumbnail_path = str(make_video_thumbnail(path))
            except Exception as e:
                record.metadata["thumbnail_error"] = f"{type(e).__name__}: {e}"


@celery_app.task(name="media.process", bind=True, max_retries=3)
def process_media(self, media_id: str) -> dict:
    """
    Background job: extract metadata, generate thumbnail, run verification.

    Saves the record after each stage so GET /media/{id}/status reflects
    real-time progress — even if the worker crashes mid-task, the last
    saved stage tells us where it stopped.
    """

    # --- Load the record ---
    record = record_store.get(media_id)
    if record is None:
        return {"error": f"Record {media_id} not found"}

    try:
        # --- Resolve the file to a local path we can read ---
        if settings.storage_backend == "s3":
            # S3 mode: download to a temp dir, process, auto-cleanup
            with tempfile.TemporaryDirectory() as tmpdir:
                local_path = Path(tmpdir) / record.filename
                storage.download(record.path, local_path)
                _process_file(record, local_path)
        else:
            # Local mode: the file is already on disk
            _process_file(record, Path(record.path))

        # --- Verification (runs for both image and video) ---
        if record.gps and record.property_gps:
            record.stage = "verification"
            record_store.save(record)

            record.verification = verify_location(
                upload_gps={"lat": record.gps.lat, "lng": record.gps.lng},
                property_gps={
                    "lat": record.property_gps.lat,
                    "lng": record.property_gps.lng,
                },
            )

        # --- All good ---
        record.status = "ready"
        record.stage = "done"
        record.error = None

    except Exception as e:
        record.status = "failed"
        record.stage = "error"
        record.error = f"{type(e).__name__}: {e}"

    # --- Persist the final state ---
    record_store.save(record)
    return {
        "media_id": media_id,
        "status": record.status,
        "stage": record.stage,
    }