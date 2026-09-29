"""
Celery tasks — background work that runs in a separate process.

The pattern:
    routes/media.py saves a MediaRecord with status="processing", stage="received"
    routes/media.py calls process_media.delay(media_id) and returns 201
    a Celery worker picks up the job and calls process_media(media_id)
    process_media does the slow work, updates stage along the way, sets status="ready"

Everything the task needs is in the record — no large arguments passed
through the queue.

Stage progression:
    received → metadata → thumbnail → verification → done
    On error: stage="error", status="failed"
"""

from pathlib import Path

from app.services import record_store
from app.services.metadata import extract_image_metadata, make_thumbnail
from app.services.verification import verify_location
from app.workers.celery_app import celery_app


@celery_app.task(name="media.process", bind=True, max_retries=3)
def process_media(self, media_id: str) -> dict:
    """
    Background job: extract metadata, generate thumbnail, run verification.

    Saves the record after each stage so GET /media/{id}/status reflects
    real-time progress — even if the worker crashes mid-task, the last
    saved stage tells us where it stopped.

    Args:
        media_id: the ID of a MediaRecord previously saved to record_store.

    Returns:
        {"media_id": str, "status": str, "stage": str} on success
        {"error": str} on structural failure (missing record)
    """

    # --- Load the record ---
    record = record_store.get(media_id)
    if record is None:
        # Structural failure: retrying won't help. Return early.
        return {"error": f"Record {media_id} not found"}

    def save_stage(stage: str) -> None:
        """Update the record's stage and persist it."""
        record.stage = stage
        record_store.save(record)

    try:
        # --- Stage: metadata + thumbnail (images only) ---
        if record.content_type.startswith("image/"):
            save_stage("metadata")
            path = Path(record.path)
            record.metadata = extract_image_metadata(path)

            # Only try to thumbnail if the image was valid
            if "error" not in record.metadata:
                save_stage("thumbnail")
                try:
                    thumb = make_thumbnail(path)
                    record.thumbnail_path = str(thumb)
                except Exception as e:
                    # Thumbnail failure shouldn't fail the whole task
                    record.metadata["thumbnail_error"] = f"{type(e).__name__}: {e}"

        # --- Stage: verification (only if both GPS sides are present) ---
        if record.gps and record.property_gps:
            save_stage("verification")
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
        # Unexpected error — mark failed, keep whatever progress we made
        record.status = "failed"
        record.stage = "error"
        record.error = f"{type(e).__name__}: {e}"
        # NOTE: not re-raising, so Celery won't retry a deterministic bug.
        # If we want retries for specific errors, call self.retry(exc=e) instead.

    # --- Persist the final state ---
    record_store.save(record)
    return {
        "media_id": media_id,
        "status": record.status,
        "stage": record.stage,
    }