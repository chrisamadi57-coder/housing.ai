"""
Extract metadata from uploaded images and videos, and generate thumbnails.

Used by the upload pipeline so we can:
  - know the real dimensions, format, and duration of media
  - read EXIF (camera-written data: GPS, timestamp, model) from images
  - produce a small preview the frontend can display quickly

Images  → Pillow (EXIF, dimensions, thumbnail)
Videos  → ffmpeg/ffprobe (duration, resolution, codec, fps, has_audio, thumbnail)
"""

from pathlib import Path
from typing import Any

import ffmpeg
from PIL import Image, ExifTags, UnidentifiedImageError

from app.config import settings


# ============================================================================
# Images (Pillow)
# ============================================================================

def extract_image_metadata(path: Path) -> dict[str, Any]:
    """
    Read an image file and return a dict describing it.

    Returned keys (when available):
        width:  int
        height: int
        format: str        e.g. "JPEG", "PNG"
        exif:   dict       human-readable EXIF key/value pairs

    If the file isn't a valid image, returns {"error": "<message>"}.
    """
    meta: dict[str, Any] = {}

    try:
        with Image.open(path) as img:
            meta["width"] = img.width
            meta["height"] = img.height
            meta["format"] = img.format

            exif = img.getexif()
            if exif:
                # Cast everything to str — EXIF values can be bytes/ratios/etc,
                # and we want them JSON-serializable for the API response.
                meta["exif"] = {
                    ExifTags.TAGS.get(tag_id, str(tag_id)): str(value)
                    for tag_id, value in exif.items()
                }

    except UnidentifiedImageError:
        meta["error"] = "File is not a valid image"
    except Exception as e:
        # Catch-all so one corrupt file doesn't kill the whole pipeline
        meta["error"] = f"{type(e).__name__}: {e}"

    return meta


def make_thumbnail(src: Path, size: tuple[int, int] = (400, 400)) -> Path:
    """
    Create an image thumbnail next to the source file.

    Example: uploads/abc/house.jpg -> uploads/abc/house_thumb.jpg

    Preserves aspect ratio. Caps the longest side to `size`.
    Returns the path to the thumbnail.
    """
    thumb_path = src.with_name(f"{src.stem}_thumb{src.suffix}")

    with Image.open(src) as img:
        img.thumbnail(size)          # modifies in place, keeps aspect ratio
        img.convert("RGB").save(thumb_path, quality=85)

    return thumb_path


# ============================================================================
# Videos (ffmpeg / ffprobe)
# ============================================================================

def extract_video_metadata(path: Path) -> dict[str, Any]:
    """
    Read a video file via ffprobe and return a dict describing it.

    Returned keys (when available):
        duration_seconds: float
        width: int
        height: int
        codec: str          e.g. "h264", "hevc"
        fps: float          frames per second
        has_audio: bool     True if the file has an audio stream, False otherwise

    If the file isn't a valid video, returns {"error": "<message>"}.
    """
    try:
        info = ffmpeg.probe(str(path), cmd=settings.ffprobe_bin)

        # Find the video stream
        try:
            video_stream = next(
                s for s in info["streams"] if s["codec_type"] == "video"
            )
        except StopIteration:
            return {"error": "No video stream found"}

        # Frame rate comes as a fraction like "30/1" — convert to float
        fps = 0.0
        rate = video_stream.get("r_frame_rate", "0/1")
        if "/" in rate:
            num, denom = rate.split("/")
            if float(denom) > 0:
                fps = float(num) / float(denom)

        # Duration lives on the format level (in seconds, as a string)
        duration_seconds = 0.0
        if "duration" in info.get("format", {}):
            duration_seconds = float(info["format"]["duration"])

        # Audio: does an audio stream exist?
        has_audio = any(s["codec_type"] == "audio" for s in info["streams"])

        return {
            "duration_seconds": round(duration_seconds, 2),
            "width": video_stream["width"],
            "height": video_stream["height"],
            "codec": video_stream.get("codec_name", "unknown"),
            "fps": round(fps, 2),
            "has_audio": has_audio,
        }

    except ffmpeg.Error as e:
        # ffprobe returns non-zero for bad files; stderr has the reason
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        return {"error": f"ffprobe failed: {stderr.strip()}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def make_video_thumbnail(src: Path, timestamp_sec: float = 1.0) -> Path:
    """
    Extract a single frame from a video at `timestamp_sec` and save it as a JPEG.

    Output: <src_stem>_thumb.jpg, next to the source file.
    Returns the path to the thumbnail.
    """
    thumb_path = src.with_name(f"{src.stem}_thumb.jpg")

    (
        ffmpeg
        .input(str(src), ss=timestamp_sec)
        .filter("scale", 400, -1)          # width 400, keep aspect ratio
        .output(str(thumb_path), vframes=1)
        .overwrite_output()
        .run(cmd=settings.ffmpeg_bin, capture_stdout=True, capture_stderr=True, quiet=True)
    )

    return thumb_path