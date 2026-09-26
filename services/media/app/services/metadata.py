"""
Extract metadata from uploaded images, and generate thumbnails.

Used by the upload pipeline so we can:
  - know the real dimensions and format of an image
  - read EXIF (camera-written data: GPS, timestamp, model)
  - produce a small preview the frontend can display quickly

Videos are NOT handled here yet — that comes later with ffmpeg.
"""

from pathlib import Path
from typing import Any

from PIL import Image, ExifTags, UnidentifiedImageError

# Pillow's EXIF tag IDs are numeric. ExifTags.TAGS maps id -> human name.

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
    Create a thumbnail next to the source file.

    Example: uploads/abc/house.jpg -> uploads/abc/house_thumb.jpg

    Preserves aspect ratio. Caps the longest side to `size`.
    Returns the path to the thumbnail.
    """
    thumb_path = src.with_name(f"{src.stem}_thumb{src.suffix}")

    with Image.open(src) as img:
        img.thumbnail(size)          # modifies in place, keeps aspect ratio
        img.convert("RGB").save(thumb_path, quality=85)

    return thumb_path