"""Smoke test for app/services/metadata.py — run:
    python -m scripts.test_metadata
"""
import tempfile
from pathlib import Path

from PIL import Image

from app.services.metadata import extract_image_metadata, make_thumbnail


def section(title):
    print("\n" + "=" * 40)
    print(title)
    print("=" * 40)


with tempfile.TemporaryDirectory() as tmp:
    tmp_dir = Path(tmp)

    # --- 1. Valid JPEG ---
    section("1. Extract metadata from a valid JPEG")
    img_path = tmp_dir / "sample.jpg"
    Image.new("RGB", (1200, 800), color=(200, 100, 50)).save(img_path, "JPEG")

    meta = extract_image_metadata(img_path)
    print("meta:", meta)
    assert meta.get("width") == 1200
    assert meta.get("height") == 800
    assert meta.get("format") == "JPEG"
    assert "error" not in meta
    print("PASS")

    # --- 2. Thumbnail creation ---
    section("2. Generate a thumbnail")
    thumb_path = make_thumbnail(img_path, size=(400, 400))
    print("thumb:", thumb_path)
    assert thumb_path.exists()
    with Image.open(thumb_path) as t:
        print("thumb size:", t.size)
        assert max(t.size) <= 400
    print("PASS")

    # --- 3. Non-image file ---
    section("3. Non-image file is caught gracefully")
    bad = tmp_dir / "fake.jpg"
    bad.write_text("this is not an image")
    meta = extract_image_metadata(bad)
    print("meta:", meta)
    assert "error" in meta
    print("PASS")

    # --- 4. PNG also works ---
    section("4. PNG format works")
    png_path = tmp_dir / "sample.png"
    Image.new("RGBA", (300, 300), color=(0, 0, 0, 0)).save(png_path, "PNG")
    meta = extract_image_metadata(png_path)
    print("meta:", meta)
    assert meta.get("format") == "PNG"
    print("PASS")


print("\nAll checks passed. metadata.py is good.")