# Media Service API

**Owner:** Person 3
**Base path:** `/media`
**Base URL (dev):** `http://localhost:8000`

The media service handles upload, storage, metadata extraction, thumbnail
generation, location verification, duplicate detection, and fraud scoring
for property photos and videos.

**Heavy processing happens in a background worker** (Celery + Redis). The
upload endpoint returns immediately; the caller polls for completion.

---

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/media/upload` | Upload a new media file |
| GET    | `/media/{media_id}/status` | Poll processing status |
| GET    | `/media/{media_id}` | Fetch the full media record |
| GET    | `/media` | List all records (dev only) |
| POST   | `/media/parse-search` | Parse natural-language search query into filters |
| GET    | `/health` | Service health check |

---

## POST `/media/upload`

Upload a photo or video with optional location data.

### Request

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | file | ✅ | JPEG, PNG, WEBP, or MP4. Max 50 MB. |
| `gps_lat` | float | optional | Where the media was captured (-90 to 90) |
| `gps_lng` | float | optional | Where the media was captured (-180 to 180) |
| `property_lat` | float | optional | Where the property claims to be |
| `property_lng` | float | optional | Where the property claims to be |

**Rules:**
- `gps_lat` and `gps_lng` must both be present to be considered.
- `property_lat` and `property_lng` must both be present to be considered.
- If all four are present, location verification runs automatically.
- Leave a field **empty** (not `0`) to omit it.

### Response — `201 Created`

```json
{
  "id": "4f7a81bf-56df-4217-950b-4e5981119ed7",
  "filename": "living_room.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 245812,
  "sha256": "a3f1...",
  "path": "uploads/4f7a81bf-.../living_room.jpg",
  "thumbnail_path": null,
  "metadata": {},
  "gps": { "lat": 6.5244, "lng": 3.3792, "captured_at": null },
  "property_gps": { "lat": 6.5245, "lng": 3.3793, "captured_at": null },
  "verification": null,
  "fraud": null,
  "status": "processing",
  "stage": "received",
  "updated_at": "2026-09-30T...",
  "error": null,
  "created_at": "2026-09-30T..."
}