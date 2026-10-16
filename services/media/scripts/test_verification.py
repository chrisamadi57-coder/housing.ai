"""Smoke test for app/services/verification.py — run:
    python -m scripts.test_verification
"""
from app.services.verification import haversine_meters, verify_location


def section(title):
    print("\n" + "=" * 40)
    print(title)
    print("=" * 40)


# --- 1. Same point -> 0 meters ---
section("1. Same coordinates -> distance ~0")
d = haversine_meters(6.5244, 3.3792, 6.5244, 3.3792)
print("distance:", d)
assert d < 0.001
print("PASS")


# --- 2. Known reference: 1 degree of latitude ~ 111,195 m ---
section("2. 1 degree of latitude ~ 111,195 m")
d = haversine_meters(0.0, 0.0, 1.0, 0.0)
print("distance:", round(d, 2), "m")
assert 110_000 < d < 112_000, f"expected ~111km, got {d}"
print("PASS")


# --- 3. Small local distance (Lagos, ~1km) ---
section("3. Realistic local distance")
# Two points roughly 1 km apart in Lagos
d = haversine_meters(6.5244, 3.3792, 6.5334, 3.3792)
print("distance:", round(d, 2), "m")
assert 900 < d < 1100
print("PASS")


# --- 4. Verify: within threshold ---
section("4. verify_location: within threshold")
result = verify_location(
    upload_gps={"lat": 6.5244, "lng": 3.3792},
    property_gps={"lat": 6.5245, "lng": 3.3793},   # ~15m away
    threshold_meters=100,
)
print(result)
assert result["verified"] is True
assert result["distance_meters"] < 100
assert result["threshold_meters"] == 100
print("PASS")


# --- 5. Verify: outside threshold ---
section("5. verify_location: outside threshold")
result = verify_location(
    upload_gps={"lat": 6.5244, "lng": 3.3792},
    property_gps={"lat": 6.6244, "lng": 3.3792},   # ~11km north
    threshold_meters=100,
)
print(result)
assert result["verified"] is False
assert result["distance_meters"] > 100
print("PASS")


# --- 6. Default threshold comes from settings ---
section("6. Default threshold from settings")
result = verify_location(
    upload_gps={"lat": 6.5244, "lng": 3.3792},
    property_gps={"lat": 6.5244, "lng": 3.3792},
)
print(result)
assert result["threshold_meters"] == 100   # from .env
print("PASS")


# --- 7. Lagos to Abuja (long distance sanity check) ---
section("7. Lagos to Abuja ~ 530 km")
# Rough coordinates: Lagos (6.5244, 3.3792) -> Abuja (9.0765, 7.3986)
d = haversine_meters(6.5244, 3.3792, 9.0765, 7.3986)
print("distance:", round(d / 1000, 1), "km")
assert 500_000 < d < 600_000, f"expected ~530 km, got {d/1000:.0f} km"
print("PASS")


print("\nAll checks passed. verification.py is good.")