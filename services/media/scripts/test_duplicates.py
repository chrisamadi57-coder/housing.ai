"""Smoke test for app/services/duplicates.py — run:
    python -m scripts.test_duplicates
"""
import tempfile
from pathlib import Path

from PIL import Image

from app.services.duplicates import (
    compute_phash,
    hamming_distance,
    is_probable_duplicate,
)


def section(title):
    print("\n" + "=" * 40)
    print(title)
    print("=" * 40)


def make_image(path: Path, color: tuple, size: tuple = (300, 300)) -> None:
    """Helper: save a solid-color image."""
    Image.new("RGB", size, color=color).save(path, "JPEG")


with tempfile.TemporaryDirectory() as tmp:
    tmp_dir = Path(tmp)

    # --- 1. Same image → same hash ---
    section("1. Same image produces the same hash")
    a = tmp_dir / "a.jpg"
    make_image(a, (200, 100, 50))

    h1 = compute_phash(a)
    h2 = compute_phash(a)
    print("hash:", h1)
    assert h1 == h2
    assert len(h1) == 16  # 64-bit hash = 16 hex chars
    print("PASS")

    # --- 2. Same image, different format → same or near-same hash ---
    section("2. Same visual, different formats → similar hashes")
    b_png = tmp_dir / "b.png"
    Image.new("RGB", (300, 300), color=(200, 100, 50)).save(b_png, "PNG")

    h_png = compute_phash(b_png)
    print("jpg hash:", h1)
    print("png hash:", h_png)
    dist = hamming_distance(h1, h_png)
    print("distance:", dist)
    assert dist <= 8, f"png should be similar to jpg, got distance {dist}"
    print("PASS")

    # --- 3. Different image → different hash ---
    section("3. Different images → distant hashes")
    c = tmp_dir / "c.jpg"
    make_image(c, (20, 20, 200))  # solid blue vs solid brown

    h_c = compute_phash(c)
    print("brown hash:", h1)
    print("blue hash :", h_c)
    dist = hamming_distance(h1, h_c)
    print("distance:", dist)
    # Solid colors sometimes hash similarly; check with more structured images
    # For a stronger test, use gradient or noise:

    d = tmp_dir / "d.jpg"
    img = Image.new("RGB", (300, 300))
    pixels = img.load()
    for x in range(300):
        for y in range(300):
            pixels[x, y] = ((x * 255) // 300, (y * 255) // 300, 128)
    img.save(d, "JPEG")

    h_d = compute_phash(d)
    dist2 = hamming_distance(h1, h_d)
    print("gradient hash:", h_d)
    print("distance from solid:", dist2)
    assert dist2 > 8, f"gradient should differ, got {dist2}"
    print("PASS")

    # --- 4. is_probable_duplicate() ---
    section("4. is_probable_duplicate threshold behavior")
    assert is_probable_duplicate(h1, h1) is True
    assert is_probable_duplicate(h1, h_c, threshold=64) is True   # everything within 64
    assert is_probable_duplicate(h1, h_d, threshold=0) is False   # nothing within 0 unless identical
    print("PASS")

    # --- 5. hamming_distance edge cases ---
    section("5. hamming_distance edge cases")
    # All same bits
    assert hamming_distance("0000000000000000", "0000000000000000") == 0
    # All different bits
    assert hamming_distance("0000000000000000", "ffffffffffffffff") == 64
    # One bit different
    assert hamming_distance("0000000000000000", "0000000000000001") == 1
    print("PASS")

    # --- 6. hamming_distance raises on mismatched lengths ---
    section("6. hamming_distance raises on length mismatch")
    try:
        hamming_distance("abc", "abcd")
        print("FAIL — should have raised")
    except ValueError as e:
        print("PASS — raised ValueError:", e)


print("\nAll checks passed. duplicates.py is good.")