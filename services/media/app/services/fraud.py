"""
Fraud detection rules.

Each rule is a pure function: it takes a MediaRecord (and any needed
context), and returns a signal dict or None.

A signal dict has the shape:
    {"rule": "RULE_NAME", "weight": int, "reason": "human-readable"}

The engine runs all rules, collects signals, and produces a risk score
from 0 to 100.

Design principle: DETECT, DON'T JUDGE.
    This module produces signals, not verdicts. It never rejects an upload
    or blocks a user. The frontend and future moderator tools decide what
    to do with the signals.

Adding a rule:
    1. Write a function that returns dict-or-None
    2. Add it to the RULES list at the bottom
    3. That's it.
"""

from typing import Any, Callable

from app.models import MediaRecord


# ----------------------------------------------------------------------------
# Individual rules
# ----------------------------------------------------------------------------

def rule_exact_duplicate(record: MediaRecord, **ctx: Any) -> dict | None:
    """
    Triggers when this record's phash matches another record's phash exactly.

    Weight scales with the number of matches: 15 for one match,
    +10 for each additional (capped at 40).
    """
    dupes = record.metadata.get("possible_duplicates", [])
    exact = [d for d in dupes if d.get("distance") == 0]
    if not exact:
        return None

    count = len(exact)
    weight = min(15 + (count - 1) * 10, 40)
    return {
        "rule": "EXACT_DUPLICATE",
        "weight": weight,
        "reason": f"Identical to {count} other listing{'s' if count > 1 else ''}",
    }


def rule_near_duplicate(record: MediaRecord, **ctx: Any) -> dict | None:
    """
    Triggers when this record's phash is close (but not identical) to
    another record's phash. Distance 1..8.

    Weight is fixed at 10. Near-duplicates are common for legitimate
    cases (same building, same agent, similar angles) — moderate signal.
    """
    dupes = record.metadata.get("possible_duplicates", [])
    near = [d for d in dupes if 0 < d.get("distance", 999) <= 8]
    if not near:
        return None

    return {
        "rule": "NEAR_DUPLICATE",
        "weight": 10,
        "reason": f"Visually similar to {len(near)} other listing{'s' if len(near) > 1 else ''}",
    }


def rule_many_duplicates(record: MediaRecord, **ctx: Any) -> dict | None:
    """
    Triggers when a single phash is shared across many records.

    This is the strongest signal we have — the same photo appearing
    on 3+ listings is almost always a reused image (legitimate or fraud).

    Weight: 30.
    """
    dupes = record.metadata.get("possible_duplicates", [])
    if len(dupes) < 3:
        return None

    return {
        "rule": "MANY_DUPLICATES",
        "weight": 30,
        "reason": f"Same image used across {len(dupes)} listings",
    }


def rule_suspicious_location(record: MediaRecord, **ctx: Any) -> dict | None:
    """
    Triggers when the photo location is dramatically different from
    the claimed property location.

    The verification already flagged this. We're scoring the severity:
    a mismatch of more than 1 km is notable; more than 10 km is severe.
    """
    verification = record.verification or {}
    if verification.get("verified") is not False:
        return None

    distance = verification.get("distance_meters", 0)
    threshold = verification.get("threshold_meters", 100)

    if distance <= threshold:
        # Verified=false but within threshold — shouldn't happen, but be safe
        return None

    # Scale weight by how far outside the threshold
    # (distance / threshold) > 10 means > 1000m off if threshold is 100
    ratio = distance / max(threshold, 1)

    if ratio >= 100:
        weight = 40
        severity = "very far"
    elif ratio >= 10:
        weight = 25
        severity = "far"
    else:
        weight = 10
        severity = "outside threshold"

    return {
        "rule": "SUSPICIOUS_LOCATION",
        "weight": weight,
        "reason": f"Photo {int(distance)}m from claimed location ({severity})",
    }


# ----------------------------------------------------------------------------
# Rule registry + engine
# ----------------------------------------------------------------------------

RULES: list[Callable[..., dict | None]] = [
    rule_exact_duplicate,
    rule_near_duplicate,
    rule_many_duplicates,
    rule_suspicious_location,
]


def evaluate(record: MediaRecord, **ctx: Any) -> dict:
    """
    Run every rule against `record`, collect signals, produce a risk score.

    Returns:
        {
            "risk_score": int,     # 0..100, capped
            "signals": [ {rule, weight, reason}, ... ],
        }

    The score is the sum of all signal weights, capped at 100.
    """
    signals: list[dict] = []
    for rule in RULES:
        try:
            signal = rule(record, **ctx)
        except Exception as e:
            # A broken rule shouldn't crash the whole evaluation.
            signal = {
                "rule": f"{rule.__name__}_ERROR",
                "weight": 0,
                "reason": f"{type(e).__name__}: {e}",
            }
        if signal:
            signals.append(signal)

    total = sum(s["weight"] for s in signals)
    return {
        "risk_score": min(total, 100),
        "signals": signals,
    }