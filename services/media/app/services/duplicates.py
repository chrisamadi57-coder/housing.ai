"""
Perceptual hashing for duplicate image detection.

What is a perceptual hash (phash)?
    A fingerprint of an image's *visual* content, not its bytes.
    Two visually identical images — even after resizing, compression,
    or format conversion — produce nearly identical phashes.

What is Hamming distance?
    The number of bits that differ between two hashes. For 64-bit
    hashes, values 0-5 usually mean "same image", 5-10 "very similar",
    above 10 "different".

This module detects duplicates — it does NOT reject uploads.
    Detection is information; the caller decides what to do with it.
    Business rules (e.g. "flag if match is from a different agent")
    live at a higher layer.
"""

from pathlib import Path

import imagehash
from PIL import Image, UnidentifiedImageError


def compute_phash(path: Path) -> str:
    """
    Compute a 64-bit perceptual hash of an image file.

    Returns the hash as a hex string (16 characters, e.g. "a3f1c2b8d4e5f6a7").

    Raises FileNotFoundError if the file doesn't exist.
    Raises UnidentifiedImageError if the file isn't a valid image.
    """
    with Image.open(path) as img:
        # imagehash.phash() returns an ImageHash object.
        # str() gives us the hex form — storable in JSON.
        return str(imagehash.phash(img))


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Number of differing bits between two hex-encoded perceptual hashes.

    Both hashes must be the same length (16 hex chars = 64 bits).
    Returns an integer 0..64.

    Raises ValueError if the hashes have different lengths.
    """
    if len(hash1) != len(hash2):
        raise ValueError(
            f"Hash length mismatch: {len(hash1)} vs {len(hash2)} hex chars"
        )

    # XOR each hex pair, count set bits in the result.
    # int(x, 16) parses hex; int.bit_count() counts 1-bits.
    return sum(
        (int(a, 16) ^ int(b, 16)).bit_count()
        for a, b in zip(hash1, hash2)
    )


def is_probable_duplicate(hash1: str, hash2: str, threshold: int = 8) -> bool:
    """
    True if two phashes are within `threshold` bits of each other.

    Default threshold of 8 (out of 64) catches resized/recompressed
    duplicates without excessive false positives.
    """
    return hamming_distance(hash1, hash2) <= threshold