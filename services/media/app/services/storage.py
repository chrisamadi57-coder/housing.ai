"""
Storage abstraction layer.

Today: writes to local disk under UPLOAD_DIR.
Later (Phase 4): swap the internals for Cloudflare R2 — same public interface.

The rest of the app only ever calls:
    storage.save(file, subdir=...)  -> (Path | key, sha256, size_bytes)
    storage.get_path(key)           -> Path
    storage.delete(key)             -> None
"""

import hashlib
from pathlib import Path

from fastapi import UploadFile

from app.config import settings


class LocalStorage:
    """Local-disk implementation of the storage layer."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or settings.upload_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        file: UploadFile,
        subdir: str = "",
    ) -> tuple[Path, str, int]:
        """
        Stream `file` to disk under <root>/<subdir>/<filename>.

        Returns:
            (path, sha256_hex, size_bytes)
        """
        target_dir = self.root / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / file.filename

        hasher = hashlib.sha256()
        size = 0

        # Read in chunks — don't load whole file into RAM (videos can be GBs)
        with target.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):  # 1 MB
                out.write(chunk)
                hasher.update(chunk)
                size += len(chunk)

        # Rewind so callers can read the file again if needed
        file.file.seek(0)

        return target, hasher.hexdigest(), size

    def get_path(self, key: str | Path) -> Path:
        """Return an absolute Path for a stored key."""
        p = Path(key)
        return p if p.is_absolute() else (self.root / p)

    def delete(self, key: str | Path) -> None:
        """Remove a stored file. Silent if it doesn't exist."""
        p = self.get_path(key)
        if p.exists() and p.is_file():
            p.unlink()


# Module-level singleton — everything imports this
storage = LocalStorage()