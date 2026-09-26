"""Quick smoke test for app/models.py — run with: python scripts/test_models.py"""
from datetime import datetime, timezone
from app.models import GPSPoint, MediaRecord


def section(title):
    print("\n" + "=" * 40)
    print(title)
    print("=" * 40)


# --- 1. Valid GPS ---
section("1. Valid GPS")
g = GPSPoint(lat=6.5244, lng=3.3792)
print(g)
assert g.lat == 6.5244
assert g.lng == 3.3792
assert g.captured_at is None
print("PASS")


# --- 2. Invalid GPS should raise ---
section("2. Invalid GPS raises ValidationError")
try:
    GPSPoint(lat=999, lng=0)
    print("FAIL — no error raised")
except Exception as e:
    print("PASS — caught:", type(e).__name__)


# --- 3. Full MediaRecord ---
section("3. Full MediaRecord")
rec = MediaRecord(
    id="test-1",
    filename="house.jpg",
    content_type="image/jpeg",
    size_bytes=123456,
    sha256="abc123",
    path="uploads/test-1/house.jpg",
    gps=g,
    created_at=datetime.now(timezone.utc),
)
print(rec.model_dump_json(indent=2))
assert rec.status == "pending"
assert rec.metadata == {}
assert rec.thumbnail_path is None
assert rec.verification is None
print("PASS")


# --- 4. Mutable default check ---
section("4. metadata dict is not shared between records")
r1 = MediaRecord(id="a", filename="a.jpg", content_type="image/jpeg",
                 size_bytes=1, sha256="a", path="x",
                 created_at=datetime.now(timezone.utc))
r2 = MediaRecord(id="b", filename="b.jpg", content_type="image/jpeg",
                 size_bytes=1, sha256="b", path="y",
                 created_at=datetime.now(timezone.utc))
r1.metadata["touched"] = True
print("r1.metadata:", r1.metadata)
print("r2.metadata:", r2.metadata)
assert r2.metadata == {}, "FAIL — dict is shared!"
print("PASS")


print("\nAll checks passed. models.py is good.")