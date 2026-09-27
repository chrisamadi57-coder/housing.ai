"""Smoke test for app/services/record_store.py — run:
    python -m scripts.test_record_store
"""
from datetime import datetime, timezone

from app.models import GPSPoint, MediaRecord
from app.services import record_store


def section(title):
    print("\n" + "=" * 40)
    print(title)
    print("=" * 40)


TEST_ID = "test-record-store-001"


# --- Cleanup from previous runs ---
record_store.delete(TEST_ID)


# --- 1. get() on missing key returns None ---
section("1. get() on missing key -> None")
assert record_store.get(TEST_ID) is None
print("PASS")


# --- 2. Save + get round-trip ---
section("2. save() then get() returns an equivalent record")
rec = MediaRecord(
    id=TEST_ID,
    filename="test.jpg",
    content_type="image/jpeg",
    size_bytes=12345,
    sha256="deadbeef",
    path="uploads/test/test.jpg",
    gps=GPSPoint(lat=6.5244, lng=3.3792),
    status="processing",
    created_at=datetime.now(timezone.utc),
)
record_store.save(rec)

fetched = record_store.get(TEST_ID)
print("fetched:", fetched.model_dump_json(indent=2) if fetched else None)
assert fetched is not None
assert fetched.id == rec.id
assert fetched.filename == rec.filename
assert fetched.gps is not None
assert fetched.gps.lat == 6.5244
assert fetched.status == "processing"
print("PASS")


# --- 3. Update overwrites ---
section("3. save() overwrites an existing record")
rec.status = "ready"
rec.metadata = {"width": 1920, "height": 1080}
record_store.save(rec)

fetched = record_store.get(TEST_ID)
assert fetched is not None
assert fetched.status == "ready"
assert fetched.metadata["width"] == 1920
print("PASS")


# --- 4. list_all() includes our record ---
section("4. list_all() includes our record")
all_records = record_store.list_all()
ids = [r.id for r in all_records]
print(f"found {len(all_records)} records; ours present:", TEST_ID in ids)
assert TEST_ID in ids
print("PASS")


# --- 5. delete() removes it ---
section("5. delete() removes the record")
record_store.delete(TEST_ID)
assert record_store.get(TEST_ID) is None
print("PASS")


print("\nAll checks passed. record_store.py is good.")