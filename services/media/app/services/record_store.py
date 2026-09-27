"""
Shared store for MediaRecords, backed by Redis.

Why Redis and not just a Python dict?
    The Celery worker runs in a SEPARATE PROCESS. An in-memory dict in
    routes/media.py is invisible to the worker. Redis is a real
    cross-process store that both the route and the worker can talk to.

Why not PostgreSQL?
    Person 2 owns the DB. This module is a temporary shim with the
    same shape as what the DB layer will eventually offer. When their
    DB is ready, we swap this file's internals for SQL queries.
    The route and worker won't change.

Storage format:
    Key:    media:{media_id}
    Value:  JSON-serialized MediaRecord (Pydantic's model_dump_json)
    TTL:    none for now — records live until manually deleted
"""

import redis

from app.config import settings
from app.models import MediaRecord

# decode_responses=True → Redis returns str instead of bytes.
# Saves us a .decode() everywhere.
_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

_KEY_PREFIX = "media:"


def _key(media_id: str) -> str:
    return f"{_KEY_PREFIX}{media_id}"


def save(record: MediaRecord) -> None:
    """Persist a record. Overwrites if it already exists."""
    _client.set(_key(record.id), record.model_dump_json())


def get(media_id: str) -> MediaRecord | None:
    """Fetch a record by ID. Returns None if not found."""
    raw = _client.get(_key(media_id))
    if raw is None:
        return None
    return MediaRecord.model_validate_json(raw)


def delete(media_id: str) -> None:
    """Remove a record. Silent if it doesn't exist."""
    _client.delete(_key(media_id))


def list_all() -> list[MediaRecord]:
    """Return every stored record. Fine for dev; don't do this in prod."""
    records: list[MediaRecord] = []
    for key in _client.scan_iter(match=f"{_KEY_PREFIX}*"):
        raw = _client.get(key)
        if raw:
            records.append(MediaRecord.model_validate_json(raw))
    return records