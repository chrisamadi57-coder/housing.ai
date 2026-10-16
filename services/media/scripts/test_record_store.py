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

# --- 6. find_by_phash finds matching records ---
section("6. find_by_phash() matches records by phash")

# Clean up first
for old_id in ["phash-test-1", "phash-test-2", "phash-test-3"]:
    record_store.delete(old_id)

from datetime import datetime, timezone
from app.models import MediaRecord

now = datetime.now(timezone.utc)

# Record 1 — hash A
r1 = MediaRecord(
    id="phash-test-1", filename="a.jpg", content_type="image/jpeg",
    size_bytes=100, sha256="a", path="x",
    metadata={"phash": "8000000000000000"}, created_at=now,
)
record_store.save(r1)

# Record 2 — hash B, one bit different from A
r2 = MediaRecord(
    id="phash-test-2", filename="b.jpg", content_type="image/jpeg",
    size_bytes=100, sha256="b", path="y",
    metadata={"phash": "8000000000000001"}, created_at=now,
)
record_store.save(r2)

# Record 3 — hash C, far from A
r3 = MediaRecord(
    id="phash-test-3", filename="c.jpg", content_type="image/jpeg",
    size_bytes=100, sha256="c", path="z",
    metadata={"phash": "a0125b7d1337db45"}, created_at=now,
)
record_store.save(r3)

# Query with a hash identical to A's
matches = record_store.find_by_phash("8000000000000000", threshold=2)
ids = [m.id for m in matches]
print("matches:", ids)

assert "phash-test-1" in ids    # exact match
assert "phash-test-2" in ids    # 1 bit away — within threshold 2
assert "phash-test-3" not in ids  # far away — excluded
print("PASS")

# Query with threshold=0 — only exact matches
matches = record_store.find_by_phash("8000000000000000", threshold=0)
ids = [m.id for m in matches]
assert "phash-test-1" in ids
assert "phash-test-2" not in ids  # 1 bit is too far for threshold 0
print("PASS — threshold 0 excludes 1-bit differences")

# Cleanup
for old_id in ["phash-test-1", "phash-test-2", "phash-test-3"]:
    record_store.delete(old_id)

print("\nAll checks passed. record_store.py is good.")