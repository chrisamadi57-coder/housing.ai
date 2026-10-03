"""Smoke test for app/services/storage.py — run from services/media:
    python -m scripts.test_storage
"""
import io
import tempfile
from pathlib import Path
from fastapi import UploadFile

from app.services.storage import LocalStorage


def section(title):
    print("\n" + "=" * 40)
    print(title)
    print("=" * 40)


# Use a temp dir so we don't pollute the real uploads/ folder
with tempfile.TemporaryDirectory() as tmp:
    store = LocalStorage(root=tmp)

    # --- 1. Save a small file ---
    section("1. save() writes file, returns sha256 + size")
    content = b"hello housing.ai\n" * 100
    upload = UploadFile(filename="test.txt", file=io.BytesIO(content))

    path, sha, size = store.save(upload, subdir="test-1")
    print("path:", path)
    print("sha :", sha)
    print("size:", size)

    assert path.exists()
    assert size == len(content)
    assert path.read_bytes() == content
    print("PASS")

    # --- 2. Same content → same hash ---
    section("2. sha256 is deterministic")
    upload2 = UploadFile(filename="test.txt", file=io.BytesIO(content))
    _, sha2, _ = store.save(upload2, subdir="test-2")
    assert sha2 == sha
    print("PASS — both hashes:", sha[:16], "...")

    # --- 3. get_path returns absolute path ---
    section("3. get_path() resolves correctly")
    p = store.get_path("test-1/test.txt")
    assert p.is_absolute()
    assert p.exists()
    print("PASS —", p)

    # --- 4. delete() removes file ---
    section("4. delete() removes the file")
    store.delete("test-1/test.txt")
    assert not (Path(tmp) / "test-1" / "test.txt").exists()
    print("PASS")

    # --- 5. delete() on missing file is silent ---
    section("5. delete() on missing file is silent")
    store.delete("does-not-exist.txt")
    print("PASS — no exception raised")

    # --- 6. file pointer rewound after save ---
    section("6. UploadFile is rewound after save")
    upload3 = UploadFile(filename="rewind.txt", file=io.BytesIO(b"abcdef"))
    store.save(upload3)
    first_byte = upload3.file.read(1)
    assert first_byte == b"a"
    print("PASS — pointer back at start")


print("\nAll checks passed. storage.py is good.")