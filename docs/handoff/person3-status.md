# Person 3 — Media Service Status

**Last updated:** 2026-10-03
**Branch:** `person3-media`
**Owner:** Person 3 (Daniel)
**Repo path:** `services/media/`

---

## TL;DR

The media service is **functionally complete** for everything buildable without
external inputs. Two items are blocked on teammates:

1. **R2 credentials** (Person 2 — needs to add a card to Cloudflare)
2. **OpenAI API key** (pending budget approval)

Every other feature — uploads, metadata, thumbnails, GPS verification,
duplicate detection, fraud scoring, natural-language search parsing — is
built, tested, and pushed.

---

## What's Built

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/media/upload` | Upload image or video |
| GET    | `/media/{id}/status` | Poll processing status |
| GET    | `/media/{id}` | Fetch full record |
| GET    | `/media` | List all (dev only) |
| POST   | `/media/parse-search` | Natural-language query parser |
| GET    | `/health` | Health check |

### Capabilities

- **File validation** — JPEG, PNG, WEBP, MP4. Max 50 MB.
- **Streaming storage** — local disk by default; R2 ready (see below).
- **Metadata extraction** — width, height, format, EXIF (images);
  duration, codec, fps, has_audio (videos).
- **Thumbnail generation** — Pillow (images), ffmpeg (videos).
- **GPS verification** — Haversine distance from claimed property location.
- **Duplicate detection** — Perceptual hashing (imagehash), Hamming distance.
- **Fraud scoring** — Rule-based engine, risk score 0–100.
- **Natural-language parsing** — rule-based + optional LLM.
- **Async processing** — Celery worker, Redis queue.
- **Structured errors** — consistent shape across all endpoints.

### Trust Stack

Three independent signals for every listing:

1. **Location** — photo actually taken where the property claims to be
2. **Uniqueness** — photo isn't reused from another listing
3. **Pattern** — aggregated signals scored for fraud risk
---
### Capabilities

- **File validation** — JPEG, PNG, WEBP, MP4. Max 50 MB.
- **Streaming storage** — local disk by default; R2 ready (see below).
- **Metadata extraction** — width, height, format, EXIF (images);
  duration, codec, fps, has_audio (videos).
- **Thumbnail generation** — Pillow (images), ffmpeg (videos).
- **GPS verification** — Haversine distance from claimed property location.
- **Duplicate detection** — Perceptual hashing (imagehash), Hamming distance.
- **Fraud scoring** — Rule-based engine, risk score 0–100.
- **Natural-language parsing** — rule-based + optional LLM.
- **Async processing** — Celery worker, Redis queue.
- **Structured errors** — consistent shape across all endpoints.

### Trust Stack

Three independent signals for every listing:

1. **Location** — photo actually taken where the property claims to be
2. **Uniqueness** — photo isn't reused from another listing
3. **Pattern** — aggregated signals scored for fraud risk
---

## What's Blocked

| Item | Blocker | Owner | Effort to Unblock |
|------|---------|-------|-------------------|
| R2 cloud storage | Needs a payment method added | Person 2 | 15 min (see checklist below) |
| OpenAI LLM mode | Needs API key | Pending budget | 1 min (paste key in .env) |
| Property recommendations | Needs real listing data | Person 2 | Build after DB exists |

**Everything else is done.**

---

## What Person 2 Needs to Do

### R2 Setup Checklist

To unlock cloud storage for the media service:

1. Sign up at https://dash.cloudflare.com/sign-up (if not already)
2. Add a payment method (**free tier — you will not be charged at our usage**)
3. Go to **Storage & Databases → R2** → **Add R2 subscription**
4. Create a bucket named **`housing-media`**
5. Generate an API token:
   - R2 overview → **Manage R2 API Tokens** → **Create API Token**
   - Name: `housing-ai-dev`
   - Permissions: **Object Read & Write**
   - Bucket: **Specify bucket → `housing-media`**
   - TTL: leave blank
6. Send me (DM, not public) these four values:
   - **Account ID** (from R2 overview, 32-char hex)
   - **Access Key ID** (shown once when token is created)
   - **Secret Access Key** (shown once)
   - **Bucket name** (`housing-media`)

Once I have these, I flip two values in `.env` and the media service
starts writing to R2. **No code changes. Approximately 2 minutes.**

### Storage Layer

When the PostgreSQL layer is ready, `record_store.py` will be swapped for
SQL. The HTTP surface will not change. Required fields to persist on
`MediaRecord`:

- `id`, `filename`, `content_type`, `size_bytes`, `sha256`, `path`,
  `thumbnail_path`, `metadata` (JSONB), `gps`, `property_gps`,
  `verification` (JSONB), `fraud` (JSONB), `status`, `stage`, `error`,
  `created_at`, `updated_at`
  
---

## What Person 1 Needs to Know

- **All endpoints return JSON.**
- **All errors share one shape:** `{"error": {"code": ..., "message": ..., "details": {...}}}`
- **Uploads return immediately** with `status="processing"`. Poll `/media/{id}/status` until `ready: true`.
- **`thumbnail_path` is a server-side path**, not a URL yet. When R2 is enabled, this becomes a proper URL.
- **`fraud.risk_score`** is an integer 0–100. **Suggested UI:**
  - `0–20` → 🟢 "Looks good"
  - `21–50` → 🟡 "Review suggested"
  - `51+` → 🔴 "Flagged for review"
- **`verification.verified`** is a boolean. Show a location badge accordingly.
- **Full API reference:** `docs/api/media.md`

---

## How to Run Locally

**Prerequisites:**
- Python 3.12
- Redis (or Memurai on Windows)
- ffmpeg (in PATH, or set `FFMPEG_BIN` / `FFPROBE_BIN` in `.env`)

**Setup (one-time):**
```bash
cd services/media
python -m venv .venv
source .venv/bin/activate           # Linux/macOS
# .\.venv\Scripts\Activate.ps1      # Windows
pip install -r requirements.txt
cp .env.example .env                # Linux/macOS
# Copy-Item .env.example .env       # Windows
```

**Run the two processes** (in separate terminals):

Terminal A — API:
```bash
cd services/media
source .venv/bin/activate
uvicorn app.main:app --reload
```

Terminal B — Worker:
```bash
cd services/media
source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
# Add --pool=solo on Windows
```

**Verify:**
- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

**Run tests:**
```bash
python -m scripts.test_models
python -m scripts.test_storage
python -m scripts.test_metadata
python -m scripts.test_verification
python -m scripts.test_record_store
python -m scripts.test_duplicates
python -m scripts.test_fraud
python -m scripts.test_video_metadata
python -m scripts.test_s3_storage
python -m scripts.test_search_parser
```

---

## File Map

```
services/media/
├── app/
│   ├── config.py                 Settings loader (.env)
│   ├── main.py                   FastAPI app entry
│   ├── models.py                 MediaRecord, GPSPoint
│   ├── core/
│   │   └── errors.py             Structured error handlers
│   ├── routes/
│   │   └── media.py              All HTTP endpoints
│   ├── services/
│   │   ├── storage.py            LocalStorage + S3Storage
│   │   ├── metadata.py           Image/video metadata + thumbnails
│   │   ├── verification.py       Haversine + GPS verdict
│   │   ├── record_store.py       Redis-backed record persistence
│   │   ├── duplicates.py         Perceptual hashing
│   │   ├── fraud.py              Rules engine + risk scoring
│   │   └── search_parser.py      NL query → structured filters
│   └── workers/
│       ├── celery_app.py         Celery config
│       └── tasks.py              process_media task
├── scripts/                      Test scripts (see list above)
├── requirements.txt
├── .env / .env.example
└── uploads/                      Local storage (gitignored)
```

---

## Branch & Contact

- **Branch:** `person3-media`
- **All changes pushed to GitHub.** Both Windows and Ubuntu dev machines synced.
- **Questions:** reach out on the team chat.