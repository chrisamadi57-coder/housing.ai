"""
Natural-language search query parser.

Takes a free-text query like "3 bed flat in Lekki under 50m" and returns
a structured filter dict that a search endpoint can consume.

Two backends:
  1. Rule-based parser — always available, no API key needed, deterministic.
     Handles common patterns. Fast, free, offline.
  2. LLM parser (OpenAI) — used when OPENAI_API_KEY is set.
     Handles complex phrasings, negations, and anything the rules miss.

Both return the SAME shape. The frontend doesn't know which one ran.

To enable LLM mode:
    Set OPENAI_API_KEY in .env and restart the service.
    No code changes needed.
"""

import json
import re
from typing import Any

from app.config import settings


# Field aliases — users say "flat" or "apartment" or "beds" or "bedrooms".
# We normalize everything to a canonical set of keys.

PROPERTY_TYPE_MAP = {
    "flat": "flat",
    "apartment": "flat",
    "house": "house",
    "duplex": "house",
    "bungalow": "house",
    "land": "land",
    "plot": "land",
    "warehouse": "warehouse",
    "shop": "shop",
    "office": "office",
    "studio": "studio",
}

LISTING_TYPE_MAP = {
    "for rent": "rent",
    "to rent": "rent",
    "rental": "rent",
    "for lease": "lease",
    "to lease": "lease",
    "for sale": "sale",
    "to buy": "sale",
    "buy": "sale",
    "selling": "sale",
}


def _empty_result() -> dict[str, Any]:
    """Return a parser result with no filters set."""
    return {
        "property_type": None,
        "listing_type": None,
        "bedrooms": None,
        "bathrooms": None,
        "location": None,
        "min_price": None,
        "max_price": None,
    }


# ---------------------------------------------------------------------------
# Rule-based parser
# ---------------------------------------------------------------------------

def _parse_bedrooms(text: str) -> int | None:
    """Extract bedroom count from patterns like '3 bed', '3-bedroom', '3br'."""
    m = re.search(r"\b(\d+)\s*(?:bed|bedroom|br|beds)\b", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_bathrooms(text: str) -> int | None:
    """Extract bathroom count from patterns like '2 bath', '2-bathroom', '2ba'."""
    m = re.search(r"\b(\d+)\s*(?:bath|bathroom|ba|baths)\b", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_location(text: str) -> str | None:
    """Extract location from patterns like 'in Lekki', 'at Ikoyi', 'around VI'."""
    m = re.search(
        r"\b(?:in|at|around|near)\s+([A-Z][A-Za-z\s]+?)(?:\s+(?:under|below|above|over|for|with|and|,)|$)",
        text,
    )
    return m.group(1).strip() if m else None

def _parse_price(text: str) -> tuple[int | None, int | None]:
    """
    Extract price constraints.

    Patterns:
        'under 50m'    → max_price=50,000,000
        'below 50m'    → max_price=50,000,000
        'over 20m'     → min_price=20,000,000
        'above 20m'    → min_price=20,000,000
        '50 million'   → max_price=50,000,000 (defaults to max)

    Suffixes:
        k = thousand (1,000)
        m = million (1,000,000)
        b = billion (1,000,000,000)
    """
    # Match "under/below/over/above/max/min <number><suffix>"
    pattern = r"\b(under|below|over|above|max|maximum|min|minimum|less than|more than|at least|at most)\s+(\d+(?:\.\d+)?)\s*([kmb]?)\b"
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None, None

    modifier = m.group(1).lower()
    amount = float(m.group(2))
    suffix = m.group(3).lower()

    multipliers = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    value = int(amount * multipliers.get(suffix, 1))

    if modifier in ("over", "above", "min", "minimum", "more than", "at least"):
        return value, None
    else:
        return None, value


def parse_query_rules(text: str) -> dict[str, Any]:
    """
    Rule-based parser — deterministic, no LLM.

    Handles common English patterns. Falls back silently when a pattern
    doesn't match; missing fields stay None.
    """
    result = _empty_result()
    lower = text.lower()

    # Property type
    for keyword, canonical in PROPERTY_TYPE_MAP.items():
        if re.search(rf"\b{keyword}\b", lower):
            result["property_type"] = canonical
            break

    # Listing type — order matters: check two-word phrases first
    for keyword, canonical in LISTING_TYPE_MAP.items():
        if keyword in lower:
            result["listing_type"] = canonical
            break

    # Numbers
    result["bedrooms"] = _parse_bedrooms(text)
    result["bathrooms"] = _parse_bathrooms(text)

    # Location
    result["location"] = _parse_location(text)

    # Price
    min_price, max_price = _parse_price(text)
    result["min_price"] = min_price
    result["max_price"] = max_price

    return result


# ---------------------------------------------------------------------------
# LLM parser (OpenAI)
# ---------------------------------------------------------------------------

_LLM_PROMPT = """You are a search query parser for a Nigerian real estate listing app.

Convert the user's query into a JSON object with EXACTLY these keys:
{
  "property_type": "flat" | "house" | "land" | "warehouse" | "shop" | "office" | "studio" | null,
  "listing_type": "rent" | "lease" | "sale" | null,
  "bedrooms": int | null,
  "bathrooms": int | null,
  "location": string | null,
  "min_price": int | null,
  "max_price": int | null
}

Rules:
- Prices are in Nigerian Naira. "50m" or "50 million" = 50000000.
- "under/below/less than" → max_price. "over/above/more than" → min_price.
- Do NOT invent values. If a field isn't mentioned, use null.
- Return ONLY the JSON. No explanation, no markdown.

Examples:
"3 bed flat in Lekki under 50m" → {"property_type":"flat","listing_type":null,"bedrooms":3,"bathrooms":null,"location":"Lekki","min_price":null,"max_price":50000000}
"warehouse for rent in Ikeja" → {"property_type":"warehouse","listing_type":"rent","bedrooms":null,"bathrooms":null,"location":"Ikeja","min_price":null,"max_price":null}

User query: """


def parse_query_llm(text: str) -> dict[str, Any]:
    """
    LLM-based parser using OpenAI. Only called when an API key is set.
    """
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": _LLM_PROMPT + text},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    # Normalize: ensure all expected keys are present
    result = _empty_result()
    result.update({k: parsed.get(k) for k in result.keys()})
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_query(text: str) -> dict[str, Any]:
    """
    Parse a natural-language query into structured filters.

    Uses the LLM if OPENAI_API_KEY is set and importable;
    otherwise falls back to the rule-based parser.

    The response includes a 'parser' field indicating which one ran:
        "llm"  — used OpenAI
        "rules" — used rule-based fallback
    """
    if settings.openai_api_key:
        try:
            result = parse_query_llm(text)
            result["parser"] = "llm"
            return result
        except Exception:
            # LLM call failed (network, quota, bad key). Fall through to rules.
            pass

    result = parse_query_rules(text)
    result["parser"] = "rules"
    return result