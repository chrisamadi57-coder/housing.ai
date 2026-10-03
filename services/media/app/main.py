from fastapi import FastAPI
from app.config import settings
from app.routes import media
from app.core.errors import install_error_handlers

app = FastAPI(
    title="Housing AI — Media Service",
    version="0.1.0",
    description="Person 3 slice: media upload, GPS verification, AI, background jobs",
)

install_error_handlers(app)
app.include_router(media.router, prefix="/media", tags=["media"])


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "media",
        "storage_backend": settings.storage_backend,
    }