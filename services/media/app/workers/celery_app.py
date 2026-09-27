"""
Celery application for background job processing.

This module is imported by:
  - the Celery worker process (`celery -A app.workers.celery_app worker`)
  - task definitions in `app/workers/tasks.py`

It knows:
  - which broker (Redis) to connect to
  - which backend to store results in
  - how to serialize tasks and results
"""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "media_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Optional: how long a task result stays in Redis (seconds)
    result_expires=3600,
)