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

import tempfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


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

    def download(self,key: str | Path, dest: Path) -> Path:
        """

        For local storage, the file is already on disk - just copy it to dest.
        Keeps the interface symmetric with S3Storage.download().
        """

        src = self.get_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        return dest

    def delete(self, key: str | Path) -> None:
        """Remove a stored file. Silent if it doesn't exist."""
        p = self.get_path(key)
        if p.exists() and p.is_file():
            p.unlink()

class S3Storage:
    """
    S3-compatible object storage.

    Works with Cloudflare R2, AWS S3, Backblaze B2, MinIO — anywhere that
    speaks the S3 API. Configure via S3_* environment variables.

    Keys returned are S3 object keys (e.g. "uploads/<media_id>/house.jpg"),
    NOT local filesystem paths. Callers that need a real file on disk
    should call download() first.
    """

    def __init__(self):
        if not settings.s3_endpoint_url:
            raise RuntimeError(
                "S3 storage selected but S3_ENDPOINT_URL is not set. "
                "Check your .env configuration."
            )

        self.bucket = settings.s3_bucket_name
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )

    def save(
        self,
        file: UploadFile,
        subdir: str = "",
    ) -> tuple[str, str, int]:
        """
        Stream `file` to S3 and return (s3_key, sha256_hex, size_bytes).
        """
        # Build the object key
        key = f"{subdir}/{file.filename}" if subdir else file.filename

        # Stream the upload to a temp file, computing hash + size along the way
        hasher = hashlib.sha256()
        size = 0
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            while chunk := file.file.read(1024 * 1024):
                tmp.write(chunk)
                hasher.update(chunk)
                size += len(chunk)
        file.file.seek(0)

        try:
            self.client.upload_file(str(tmp_path), self.bucket, key)
        finally:
            tmp_path.unlink(missing_ok=True)

        return key, hasher.hexdigest(), size

    def get_path(self, key: str | Path) -> Path:
        """
        For S3, there is no local path — return the key as a Path.
        Callers should call download() if they need a real file.
        """
        return Path(key)

    def delete(self, key: str | Path) -> None:
        """Delete the object from S3. Silent if it doesn't exist."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=str(key))
        except ClientError:
            pass

    def download(self, key: str | Path, dest: Path) -> Path:
        """Download an object from S3 to a local destination path."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, str(key), str(dest))
        return dest

# Choose storage backend from config. Defaults to local disk.
if settings.storage_backend == "s3":
    storage: LocalStorage | S3Storage = S3Storage()
else:
    storage = LocalStorage()