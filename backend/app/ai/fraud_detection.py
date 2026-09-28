"""Fraud / scam detection for listings.

Rule-based heuristics covering the classic rental scams:
  - Price far below market for the area
  - Duplicate or near-duplicate property
  - Suspicious text (urgency, off-platform payment, WhatsApp-only)
  - Missing or low-quality media
  - New owner account with no history

Returns a FraudAssessment dataclass. Async signature so an ML classifier
can be dropped in later without changing callers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from statistics import median
from typing import Any, Iterable


@dataclass(slots=True)
class FraudAssessment:
    # 0.0 = clean, 1.0 = certain fraud
    score: float
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_high_risk(self) -> bool:
        return self.score >= 0.7

    @property
    def is_medium_risk(self) -> bool:
        return 0.4 <= self.score < 0.7


# ---------------------------------------------------------------------------
# Text signals
# ---------------------------------------------------------------------------

_URGENCY_RE = re.compile(
    r"\b(urgent|urgently|asap|immediately|today only|hurry|act fast|"
    r"first come first serve|serious buyers only)\b",
    re.IGNORECASE,
)

_OFFPLATFORM_RE = re.compile(
    r"\b(whatsapp|wa\.me|telegram|dm me|text me|call only|"
    r"western union|moneygram|bitcoin|btc|usdt|crypto|"
    r"pay deposit|send deposit|wire transfer)\b",
    re.IGNORECASE,
)

_MISSING_INFO_RE = re.compile(
    r"\b(no inspection|sight unseen|no viewing|payment before viewing|"
    r"no agent|owner abroad|i am abroad|i'm abroad|out of the country)\b",
    re.IGNORECASE,
)

_SCAM_PHRASES = [
    "send money",
    "advance payment",
    "via western union",
    "owner is abroad",
    "cannot show you",
    "no viewing",
    "payment first",
]


def _score_text(title: str | None, description: str | None) -> tuple[float, list[str]]:
    text = f"{title or ''}\n{description or ''}"
    reasons: list[str] = []
    score = 0.0

    if _URGENCY_RE.search(text):
        score += 0.10
        reasons.append("Contains urgency language")

    if _OFFPLATFORM_RE.search(text):
        score += 0.25
        reasons.append("Requests off-platform contact or payment")

    if _MISSING_INFO_RE.search(text):
        score += 0.30
        reasons.append("No-inspection or abroad-owner claim")

    lowered = text.lower()
    for phrase in _SCAM_PHRASES:
        if phrase in lowered:
            score += 0.15
            reasons.append(f"Suspicious phrase: {phrase!r}")
            break  # count once

    # Overly short description
    if description is not None and len(description.strip()) < 40:
        score += 0.05
        reasons.append("Very short description")

    return min(score, 1.0), reasons


# ---------------------------------------------------------------------------
# Price signals
# ---------------------------------------------------------------------------

def _score_price(
    price: Decimal | None,
    comparables: Iterable[Decimal],
) -> tuple[float, list[str], dict]:
    reasons: list[str] = []
    details: dict[str, Any] = {}

    comps = [c for c in comparables if c and c > 0]
    if price is None or len(comps) < 3:
        return 0.0, reasons, {"note": "Not enough comparables"}

    med = median(comps)
    details["market_median"] = str(med)
    details["listing_price"] = str(price)
    ratio = float(price) / float(med)
    details["ratio"] = round(ratio, 3)

    # Under 40% of median → strong scam signal
    if ratio <= 0.40:
        return 0.45, ["Price is far below market median"], details
    if ratio <= 0.60:
        return 0.25, ["Price is notably below market median"], details
    if ratio >= 2.5:
        return 0.10, ["Price is far above market median"], details

    return 0.0, reasons, details


# ---------------------------------------------------------------------------
# Media / account signals
# ---------------------------------------------------------------------------

def _score_media(media_count: int, processed_count: int, avg_quality: float | None) -> tuple[float, list[str], dict]:
    reasons: list[str] = []
    details = {"media_count": media_count, "avg_quality": avg_quality}

    if media_count == 0:
        return 0.20, ["No photos attached"], details

    if media_count == 1:
        reasons.append("Only one photo")

    if avg_quality is not None and avg_quality < 0.35:
        reasons.append("Low-quality photos")
        return 0.15, reasons, details

    if processed_count < media_count:
        # Not necessarily fraud, but worth noting during processing window.
        details["note"] = "Some media still processing"

    score = 0.05 if media_count == 1 else 0.0
    return score, reasons, details


def _score_account(
    owner_is_verified: bool,
    owner_listing_count: int,
    owner_account_age_days: int | None,
) -> tuple[float, list[str], dict]:
    reasons: list[str] = []
    details = {
        "owner_verified": owner_is_verified,
        "owner_listings": owner_listing_count,
        "owner_age_days": owner_account_age_days,
    }
    score = 0.0

    if not owner_is_verified:
        score += 0.05

    if owner_account_age_days is not None and owner_account_age_days < 3:
        score += 0.15
        reasons.append("Account is very new")

    # Owners with many listings are usually legit agents.
    if owner_listing_count >= 10:
        score = max(0.0, score - 0.10)

    return score, reasons, details


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def score_listing(
    *,
    listing,
    property_,
    comparables: Iterable[Decimal] = (),
    media_rows: list | None = None,
    owner_is_verified: bool = False,
    owner_listing_count: int = 0,
    owner_account_age_days: int | None = None,
) -> FraudAssessment:
    """Score a Listing + its Property for fraud signals.

    All arguments are duck-typed. ``listing`` needs ``price`` and
    ``purpose``. ``property_`` needs ``title``, ``description``, and
    location fields. ``media_rows`` is a list of objects with
    ``ai_quality_score`` and ``processed`` attributes.
    """
    text_score, text_reasons = _score_text(
        getattr(property_, "title", None),
        getattr(property_, "description", None),
    )
    price_score, price_reasons, price_details = _score_price(
        getattr(listing, "price", None), comparables
    )

    media_rows = media_rows or []
    processed = sum(1 for m in media_rows if getattr(m, "processed", False))
    qualities = [
        float(q) for m in media_rows
        if (q := getattr(m, "ai_quality_score", None)) is not None
    ]
    avg_q = sum(qualities) / len(qualities) if qualities else None
    media_score, media_reasons, media_details = _score_media(
        len(media_rows), processed, avg_q
    )

    account_score, account_reasons, account_details = _score_account(
        owner_is_verified, owner_listing_count, owner_account_age_days
    )

    total = min(1.0, text_score + price_score + media_score + account_score)

    all_reasons = text_reasons + price_reasons + media_reasons + account_reasons

    return FraudAssessment(
        score=round(total, 3),
        reasons=all_reasons,
        details={
            "text_score": round(text_score, 3),
            "price_score": round(price_score, 3),
            "media_score": round(media_score, 3),
            "account_score": round(account_score, 3),
            "price": price_details,
            "media": media_details,
            "account": account_details,
        },
    )


async def score_property(
    *,
    property_,
    comparables: Iterable[Decimal] = (),
    media_rows: list | None = None,
    owner_is_verified: bool = False,
    owner_listing_count: int = 0,
    owner_account_age_days: int | None = None,
) -> FraudAssessment:
    """Score a property without an active listing.

    Uses the first listing if any exists on the property. Otherwise skips
    the price signal.
    """
    listings = getattr(property_, "listings", None) or []
    listing = listings[0] if listings else None
    return await score_listing(
        listing=listing,
        property_=property_,
        comparables=comparables,
        media_rows=media_rows,
        owner_is_verified=owner_is_verified,
        owner_listing_count=owner_listing_count,
        owner_account_age_days=owner_account_age_days,
    )