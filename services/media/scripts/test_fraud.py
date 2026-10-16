"""Smoke test for app/services/fraud.py — run:
    python -m scripts.test_fraud
"""
from datetime import datetime, timezone

from app.models import MediaRecord
from app.services.fraud import evaluate


def section(title):
    print("\n" + "=" * 40)
    print(title)
    print("=" * 40)


def make_record(**overrides) -> MediaRecord:
    """Build a minimal MediaRecord for testing."""
    defaults = dict(
        id="test-1",
        filename="test.jpg",
        content_type="image/jpeg",
        size_bytes=100,
        sha256="abc",
        path="uploads/test/test.jpg",
        metadata={},
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return MediaRecord(**defaults)


# --- 1. Clean record — no signals ---
section("1. Clean record → risk_score 0")
r = make_record()
result = evaluate(r)
print(result)
assert result["risk_score"] == 0
assert result["signals"] == []
print("PASS")


# --- 2. Exact duplicate ---
section("2. Exact duplicate fires")
r = make_record(metadata={
    "possible_duplicates": [{"media_id": "other", "distance": 0}],
})
result = evaluate(r)
print(result)
assert result["risk_score"] == 15
assert any(s["rule"] == "EXACT_DUPLICATE" for s in result["signals"])
print("PASS")


# --- 3. Multiple exact duplicates ---
section("3. Three exact duplicates → higher weight")
r = make_record(metadata={
    "possible_duplicates": [
        {"media_id": "a", "distance": 0},
        {"media_id": "b", "distance": 0},
        {"media_id": "c", "distance": 0},
    ],
})
result = evaluate(r)
print(result)
# EXACT_DUPLICATE: 15 + 2*10 = 35
# MANY_DUPLICATES: 30 (3+ dupes)
assert result["risk_score"] == 65
print("PASS")


# --- 4. Near duplicate ---
section("4. Near duplicate fires")
r = make_record(metadata={
    "possible_duplicates": [{"media_id": "other", "distance": 4}],
})
result = evaluate(r)
print(result)
assert result["risk_score"] == 10
assert any(s["rule"] == "NEAR_DUPLICATE" for s in result["signals"])
print("PASS")


# --- 5. Suspicious location (very far) ---
section("5. Very far location → high weight")
r = make_record(verification={
    "verified": False,
    "distance_meters": 50000,     # 50 km
    "threshold_meters": 100,
    "reason": "Outside 100m threshold",
})
result = evaluate(r)
print(result)
assert result["risk_score"] == 40
assert any(s["rule"] == "SUSPICIOUS_LOCATION" for s in result["signals"])
print("PASS")


# --- 6. Verified record — no location signal ---
section("6. Verified record → no location signal")
r = make_record(verification={
    "verified": True,
    "distance_meters": 15,
    "threshold_meters": 100,
})
result = evaluate(r)
print(result)
assert result["risk_score"] == 0
print("PASS")


# --- 7. Combined — multiple signals stack ---
section("7. Combined signals stack, capped at 100")
r = make_record(
    metadata={
        "possible_duplicates": [
            {"media_id": "a", "distance": 0},
            {"media_id": "b", "distance": 0},
            {"media_id": "c", "distance": 0},
        ],
    },
    verification={
        "verified": False,
        "distance_meters": 50000,
        "threshold_meters": 100,
    },
)
result = evaluate(r)
print(result)
# 35 (exact) + 30 (many) + 40 (location) = 105 → capped at 100
assert result["risk_score"] == 100
print("PASS")


print("\nAll checks passed. fraud.py is good.")