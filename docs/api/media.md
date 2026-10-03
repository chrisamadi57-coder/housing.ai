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
```

**Notice:** `metadata`, `thumbnail_path`, `verification`, and `fraud` are
**empty/null on upload** — the worker fills them in. Poll `/status` to know
when done.

### Errors

| Code | HTTP | Meaning |
|------|------|---------|
| `UNSUPPORTED_FILE_TYPE` | 400 | Not a JPEG/PNG/WEBP/MP4 |
| `MISSING_FILENAME` | 400 | The `file` field has no filename |
| `FILE_TOO_LARGE` | 400 | Exceeds 50 MB |
| `STORAGE_FAILED` | 500 | Disk or storage error |
| `VALIDATION_ERROR` | 422 | Malformed form data (e.g. `gps_lat=abc`) |

**All errors share one shape:**

```json
{
  "error": {
    "code": "UNSUPPORTED_FILE_TYPE",
    "message": "Unsupported file type: application/pdf",
    "details": {
      "received": "application/pdf",
      "allowed": ["image/jpeg", "image/png", "image/webp", "video/mp4"]
    }
  }
}
```


---

## GET `/media/{media_id}/status`

Lightweight polling endpoint. Call this repeatedly after upload until `ready` is `true`.

### Response — `200 OK`

```json
{
  "media_id": "4f7a81bf-56df-4217-950b-4e5981119ed7",
  "status": "processing",
  "stage": "thumbnail",
  "ready": false,
  "failed": false,
  "created_at": "2026-09-30T...",
  "updated_at": "2026-09-30T...",
  "error": null
}
```

### Fields

| Field | Meaning |
|-------|---------|
| `status` | `pending` \| `processing` \| `ready` \| `failed` |
| `stage` | `received` \| `metadata` \| `thumbnail` \| `verification` \| `fraud` \| `done` \| `error` |
| `ready` | `true` when the record is complete and safe to fetch |
| `failed` | `true` when processing hit an error |
| `error` | Human-readable error message if failed |

### Errors

| Code | HTTP | Meaning |
|------|------|---------|
| `MEDIA_NOT_FOUND` | 404 | No record with that ID |

---

## GET `/media/{media_id}`

Fetch the full media record. Only call this **after** `/status` reports `ready: true`.

### Response — `200 OK`

```json
{
  "id": "4f7a81bf-...",
  "filename": "walkthrough.mp4",
  "content_type": "video/mp4",
  "size_bytes": 969201,
  "sha256": "18b9...",
  "path": "uploads/4f7a81bf-.../walkthrough.mp4",
  "thumbnail_path": "uploads/4f7a81bf-.../walkthrough_thumb.jpg",
  "metadata": {
    "duration_seconds": 10.0,
    "width": 1280,
    "height": 720,
    "codec": "h264",
    "fps": 30.0,
    "has_audio": false,
    "phash": "9d38848787f83047",
    "possible_duplicates": [
      { "media_id": "7e49d2e3-...", "distance": 0 },
      { "media_id": "7665f484-...", "distance": 6 }
    ]
  },
  "gps": { "lat": 6.5244, "lng": 3.3792, "captured_at": null },
  "property_gps": { "lat": 6.5245, "lng": 3.3793, "captured_at": null },
  "verification": {
    "verified": true,
    "distance_meters": 15.42,
    "threshold_meters": 100,
    "reason": "Within 100m of claimed property"
  },
  "fraud": {
    "risk_score": 45,
    "signals": [
      {
        "rule": "EXACT_DUPLICATE",
        "weight": 15,
        "reason": "Identical to 1 other listing"
      },
      {
        "rule": "MANY_DUPLICATES",
        "weight": 30,
        "reason": "Same image used across 3 listings"
      }
    ]
  },
  "status": "ready",
  "stage": "done",
  "created_at": "2026-09-30T...",
  "updated_at": "2026-09-30T...",
  "error": null
}
```

### Field Reference — New Since v0.1

#### `fraud` (optional)

Risk score produced by the fraud detection engine. `null` while the worker
is still processing; populated once `status="ready"`.

```json
{
  "risk_score": 45,
  "signals": [
    { "rule": "EXACT_DUPLICATE", "weight": 15, "reason": "..." },
    { "rule": "MANY_DUPLICATES", "weight": 30, "reason": "..." }
  ]
}
```

**Suggested frontend display:**
- `0–20` → 🟢 "Looks good"
- `21–50` → 🟡 "Review suggested"
- `51+` → 🔴 "Flagged for review"

**Available rules:**

| Rule | Triggers when |
|------|---------------|
| `EXACT_DUPLICATE` | `phash` distance 0 to another record |
| `NEAR_DUPLICATE` | `phash` distance 1–8 |
| `MANY_DUPLICATES` | Same image used on 3+ listings |
| `SUSPICIOUS_LOCATION` | Photo location very far from claimed property |

#### `metadata.phash` (optional)

16-character hex string. Perceptual hash of the image (or the video's
thumbnail). Similar images produce similar hashes. Only present after the
worker completes metadata extraction.

#### `metadata.possible_duplicates` (optional)

List of records whose `phash` is within 8 bits of this record's hash.

```json
[
  { "media_id": "7e49d2e3-...", "distance": 0 },
  { "media_id": "7665f484-...", "distance": 6 }
]
```

Only present when matches exist. Compare with `distance`:
- `0` — identical file
- `1–3` — same image, lightly transformed
- `4–8` — visually similar, could be legitimately different
- `>8` — not returned at all

### Errors

| Code | HTTP | Meaning |
|------|------|---------|
| `MEDIA_NOT_FOUND` | 404 | No record with that ID |

---

## GET `/media`

Lists all records. **Dev only** — do not call from production frontend.

---

## POST `/media/parse-search`

Parse a natural-language search query into structured filters.

### Request

**Content-Type:** `application/json`

```json
{
  "query": "3 bed flat in Lekki under 50m"
}
```

### Response — `200 OK`

```json
{
  "query": "3 bed flat in Lekki under 50m",
  "property_type": "flat",
  "listing_type": null,
  "bedrooms": 3,
  "bathrooms": null,
  "location": "Lekki",
  "min_price": null,
  "max_price": 50000000,
  "parser": "rules"
}
```

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `query` | string | Echoed back |
| `property_type` | string \| null | `flat`, `house`, `land`, `warehouse`, `shop`, `office`, `studio` |
| `listing_type` | string \| null | `rent`, `lease`, `sale` |
| `bedrooms` | int \| null |  |
| `bathrooms` | int \| null |  |
| `location` | string \| null | Best-guess location name |
| `min_price` | int \| null | Naira |
| `max_price` | int \| null | Naira |
| `parser` | string | `"rules"` (deterministic, offline) or `"llm"` (AI-powered) |

### Parser Modes

| Mode | When used | Notes |
|------|-----------|-------|
| `rules` | Default | Regex-based. Fast, free, offline. |
| `llm` | When `OPENAI_API_KEY` is set | Handles complex queries. Costs per query. |

Both modes return the same shape.

### Errors

| Code | HTTP | Meaning |
|------|------|---------|
| `EMPTY_QUERY` | 400 | Query string empty |
| `VALIDATION_ERROR` | 422 | `query` field missing |

---

## Recommended Frontend Flow

```
1. User selects a file and (optionally) enters GPS + property GPS
2. POST /media/upload  →  201 with id, status="processing"
3. Poll GET /media/{id}/status every 1–2 seconds until ready=true
4. GET /media/{id}  →  full record with metadata, thumbnail, verification, fraud
5. Render: thumbnail + video/image player + verification badge + fraud badge
```

### Suggested Polling Logic

```typescript
async function uploadAndWait(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const upload = await fetch("/media/upload", { method: "POST", body: formData });
  const record = await upload.json();

  while (true) {
    await new Promise(r => setTimeout(r, 1500));
    const res = await fetch(`/media/${record.id}/status`);
    const status = await res.json();

    if (status.ready) {
      const full = await fetch(`/media/${record.id}`);
      return await full.json();
    }
    if (status.failed) {
      throw new Error(status.error || "Processing failed");
    }
  }
}
```

**Why poll instead of webhook?** Simpler for a frontend. Webhooks can be
added later if needed.

### Rendering the Verification Badge

```typescript
const badge = record.verification?.verified
  ? "✅ Verified location"
  : record.verification
  ? "🚩 Location flagged"
  : "❓ Unverified";
```

### Rendering the Fraud Badge

```typescript
const score = record.fraud?.risk_score ?? 0;
const badge = score >= 51
  ? "🔴 Flagged for review"
  : score >= 21
  ? "🟡 Review suggested"
  : "🟢 Looks good";
```

---

## Notes for Person 2 (Backend Integration)

- The current storage layer is **Redis via `record_store.py`** — a temporary shim.
- When the PostgreSQL layer is ready, `record_store` will be swapped for SQL.
- **The HTTP surface will not change** — routes, request shapes, and response shapes stay identical.
- **New fields to persist on `MediaRecord`:**
  - `fraud: Optional[dict]`
  - `metadata.phash`, `metadata.possible_duplicates` (inside the JSONB metadata column)
- **`find_by_phash(phash, threshold=8)`** — new `record_store` function. On Postgres this becomes a query over indexed phash values or a vector search.

---

## Notes for Person 1 (Frontend)

- All endpoints return JSON.
- All errors share **one shape** (`error.code`, `error.message`, `error.details`).
- `thumbnail_path` is a **local path on the server** — when R2 is enabled, these become URLs.
- Video `metadata.has_audio` is always `true` or `false` — never null.
- `fraud.risk_score` is an integer 0–100, always present after `status="ready"`.
- `metadata.possible_duplicates` is only present when matches exist.

---

## Version History

| Date | Change |
|------|--------|
| 2026-09-30 | Initial version — image + video pipeline, GPS verification, async status polling |
| 2026-10-03 | Added `/media/parse-search`, `fraud` field, `phash`, `possible_duplicates` |