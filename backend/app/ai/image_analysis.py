"""Image analysis for property media.

Provides:
  - quality score (0-1)
  - labels (list of strings)
  - short caption

Rule-based fallback uses Pillow for basic checks (resolution, aspect,
brightness) and returns neutral labels. Swap ``analyze_image_bytes`` for
a vision model (e.g. Claude, GPT-4V, a local CLIP) with the same return
type. Workers calling it don't change.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

try:
    from PIL import Image, ImageStat
    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PIL_AVAILABLE = False


@dataclass(slots=True)
class ImageAnalysisResult:
    quality_score: float
    labels: list[str] = field(default_factory=list)
    caption: str | None = None
    is_property_photo: bool = True
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Rule-based implementation
# ---------------------------------------------------------------------------

def _resolution_score(width: int, height: int) -> float:
    """Higher resolution -> higher score, capped at 1.0."""
    pixels = width * height
    if pixels >= 1920 * 1080:  # full HD or better
        return 1.0
    if pixels >= 1280 * 720:
        return 0.8
    if pixels >= 800 * 600:
        return 0.55
    if pixels >= 640 * 480:
        return 0.35
    return 0.15


def _aspect_score(width: int, height: int) -> float:
    """Photos in typical aspect ratios score higher (0.5–2.5 wide)."""
    if height == 0:
        return 0.0
    ratio = width / height
    if 1.2 <= ratio <= 2.0:
        return 1.0
    if 0.8 <= ratio <= 2.5:
        return 0.7
    return 0.4  # extreme panorama or tall strip


def _brightness_score(img: "Image.Image") -> tuple[float, float]:
    """Mean brightness 0-255 → score 0-1. Also returns raw mean."""
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    mean = stat.mean[0]
    # Ideal brightness around 120-160
    if 100 <= mean <= 180:
        score = 1.0
    elif 60 <= mean < 100 or 180 < mean <= 220:
        score = 0.7
    else:
        score = 0.35
    return score, mean


def _rule_based_analyze(data: bytes) -> ImageAnalysisResult:
    if not _PIL_AVAILABLE:
        # Pillow missing — cannot do anything meaningful.
        return ImageAnalysisResult(
            quality_score=0.5,
            labels=["image"],
            caption="Property image",
            is_property_photo=True,
            details={"reason": "Pillow not installed"},
        )

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        return ImageAnalysisResult(
            quality_score=0.0,
            labels=["invalid"],
            caption=None,
            is_property_photo=False,
            details={"error": str(e)},
        )

    width, height = img.size
    res = _resolution_score(width, height)
    asp = _aspect_score(width, height)
    bright, mean_brightness = _brightness_score(img)

    # Simple heuristic labels from brightness + aspect
    labels: list[str] = ["property"]
    if asp >= 1.2:
        labels.append("landscape")
    if bright >= 0.9:
        labels.append("well-lit")
    elif bright <= 0.4:
        labels.append("low-light")
    if res >= 0.8:
        labels.append("high-resolution")

    # Weighted quality
    quality = round(0.45 * res + 0.2 * asp + 0.35 * bright, 3)

    caption = f"Property photo ({width}x{height})"

    return ImageAnalysisResult(
        quality_score=quality,
        labels=labels,
        caption=caption,
        is_property_photo=True,
        details={
            "width": width,
            "height": height,
            "brightness": round(mean_brightness, 1),
            "resolution_score": res,
            "aspect_score": asp,
            "brightness_score": bright,
        },
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_image_bytes(data: bytes) -> ImageAnalysisResult:
    """Analyze raw image bytes.

    Async signature is intentional — replace the body with an API call
    later without touching callers.
    """
    return _rule_based_analyze(data)


async def analyze_media_row(media_row) -> ImageAnalysisResult:
    """Analyze a Media ORM row by reading its local storage key.

    In production this would download from S3. For dev, we read from the
    local MEDIA_ROOT configured in core.config.

    `media_row` is duck-typed: any object with ``storage_key`` and
    ``mime_type`` attributes works.
    """
    from pathlib import Path

    from app.core.config import settings

    storage_key = getattr(media_row, "storage_key", None)
    mime = getattr(media_row, "mime_type", "") or ""

    if not storage_key or not mime.startswith("image/"):
        return ImageAnalysisResult(
            quality_score=0.0,
            labels=["skipped"],
            caption=None,
            is_property_photo=False,
            details={"reason": "Not an image or missing storage_key"},
        )

    path = Path(settings.MEDIA_ROOT) / storage_key
    if not path.exists():
        return ImageAnalysisResult(
            quality_score=0.0,
            labels=["missing"],
            caption=None,
            is_property_photo=False,
            details={"reason": "File not found"},
        )

    return await analyze_image_bytes(path.read_bytes())