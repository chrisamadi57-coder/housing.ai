from fastapi import FastAPI
from app.config import settings

app = FastAPI(
    title="Housing AI — Media Service",
    version="0.1.0",
    description="Person 3 slice: media upload, GPS verification, AI, background jobs",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "media",
        "storage_backend": settings.storage_backend,
    }