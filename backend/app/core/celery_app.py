"""Celery client used by the API to dispatch jobs.

Tasks are referenced by name (e.g. "tasks.media_processing.process_media").
Person 3's workers register tasks under those exact names. Names must match
exactly — put them in one place (TASK_NAMES) and message Person 3.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "housing_api",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)


# Single source of truth for task names. Person 3 imports these too.
class TASK_NAMES:
    PROCESS_MEDIA = "tasks.media_processing.process_media"
    VERIFY_LOCATION = "tasks.location_verification.verify_location"
    RUN_AI_ANALYSIS = "tasks.ai_analysis.run_ai_analysis"
    SEND_NOTIFICATION = "tasks.notifications.send_notification"


def dispatch(task_name: str, **kwargs) -> None:
    """Fire-and-forget. Never await this; never let it break a request."""
    try:
        celery_app.send_task(task_name, kwargs=kwargs)
    except Exception:
        # Never let a broker outage break an API request. Log and move on.
        # (In production, wire this to your logger / Sentry.)
        pass