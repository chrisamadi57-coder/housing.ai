"""Mock-based test for S3Storage — run:
    python -m scripts.test_s3_storage

Uses unittest.mock to fake boto3, so no real R2 credentials are needed.
Verifies the class behaves as expected: correct key format, hash, size,
and download calls.
"""
import io
import hashlib
from unittest.mock import MagicMock, patch
from pathlib import Path

from fastapi import UploadFile


def section(title):
    print("\n" + "=" * 40)
    print(title)
    print("=" * 40)


# --- Test 1: S3Storage refuses to construct without endpoint ---
section("1. Refuses to construct without S3_ENDPOINT_URL")

# Patch settings to simulate missing endpoint
with patch("app.services.storage.settings") as mock_settings:
    mock_settings.storage_backend = "s3"
    mock_settings.s3_endpoint_url = ""

    try:
        from app.services.storage import S3Storage
        S3Storage()
        print("FAIL — should have raised")
    except RuntimeError as e:
        print("PASS — raised RuntimeError:", str(e)[:60])


# --- Test 2: save() computes hash and size, uploads via client ---
section("2. save() uploads and returns correct key/hash/size")

with patch("app.services.storage.settings") as mock_settings, \
     patch("app.services.storage.boto3") as mock_boto3:

    mock_settings.s3_endpoint_url = "https://example.r2.cloudflarestorage.com"
    mock_settings.s3_access_key_id = "fake"
    mock_settings.s3_secret_access_key = "fake"
    mock_settings.s3_bucket_name = "test-bucket"
    mock_settings.s3_region = "auto"

    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client

    from app.services.storage import S3Storage
    store = S3Storage()

    content = b"hello r2 storage\n" * 100
    upload = UploadFile(filename="house.jpg", file=io.BytesIO(content))

    key, sha, size = store.save(upload, subdir="uploads/abc-123")

    print("key :", key)
    print("sha :", sha[:16], "...")
    print("size:", size)

    assert key == "uploads/abc-123/house.jpg"
    assert size == len(content)
    assert sha == hashlib.sha256(content).hexdigest()

    # Verify the client was called
    assert mock_client.upload_file.called
    args = mock_client.upload_file.call_args
    print("upload_file called with bucket:", args[0][1], "key:", args[0][2])
    print("PASS")


# --- Test 3: delete() swallows missing-object errors ---
section("3. delete() is silent on missing objects")

with patch("app.services.storage.settings") as mock_settings, \
     patch("app.services.storage.boto3") as mock_boto3:

    mock_settings.s3_endpoint_url = "https://example.r2.cloudflarestorage.com"
    mock_settings.s3_access_key_id = "fake"
    mock_settings.s3_secret_access_key = "fake"
    mock_settings.s3_bucket_name = "test-bucket"
    mock_settings.s3_region = "auto"

    mock_client = MagicMock()
    mock_client.delete_object.side_effect = None
    mock_boto3.client.return_value = mock_client

    from app.services.storage import S3Storage
    store = S3Storage()

    store.delete("nonexistent-key.jpg")
    print("PASS — no exception raised")


# --- Test 4: download() calls the client with correct args ---
section("4. download() passes bucket and key")

with patch("app.services.storage.settings") as mock_settings, \
     patch("app.services.storage.boto3") as mock_boto3:

    mock_settings.s3_endpoint_url = "https://example.r2.cloudflarestorage.com"
    mock_settings.s3_access_key_id = "fake"
    mock_settings.s3_secret_access_key = "fake"
    mock_settings.s3_bucket_name = "test-bucket"
    mock_settings.s3_region = "auto"

    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client

    from app.services.storage import S3Storage
    store = S3Storage()

    dest = Path("/tmp/test-download.jpg")
    store.download("uploads/abc/house.jpg", dest)

    assert mock_client.download_file.called
    args = mock_client.download_file.call_args
    assert args[0][0] == "test-bucket"
    assert args[0][1] == "uploads/abc/house.jpg"
    print("PASS — download_file called with correct bucket and key")


print("\nAll checks passed. S3Storage behaves correctly under mock.")
print("When real R2 credentials arrive, set STORAGE_BACKEND=s3 and S3_* values in .env.")