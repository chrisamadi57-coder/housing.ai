"""Natural-language search parser.

Rule-based implementation, no external services. Regex + city dictionary
+ price-unit normalization. Handles the 80% of queries people actually
type. Upgrade path: swap the body of ``parse_search_query`` for an LLM
call (e.g. Anthropic, OpenAI) that returns the same ParsedSearchFilters
shape. Callers do not change.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.models.enums import ListingPurpose, PropertyType
from app.schemas.search import ParsedSearchFilters

# ---------------------------------------------------------------------------
# Dictionaries
# ---------------------------------------------------------------------------

# Extend as you launch in more cities. Case-insensitive matching.
CITY_DICTIONARY: set[str] = {
    # Nigeria
    "lagos", "lekki", "ikeja", "victoria island", "vi", "ikoyi", "yaba",
    "surulere", "ajah", "gbagada", "magodo", "maryland", "oshodi",
    "abuja", "wuse", "garki", "maitama", "asokoro", "gwarinpa", "jabi",
    "port harcourt", "ph", "bonny", "rumuokoro",
    "ibadan", "bodija", "dugbe", "ring road",
    "kano", "kaduna", "benin city", "enugu", "aba", "uyo", "jos",
    "abeokuta", "akure", "owerri", "calabar", "warri", "ilorin",
    # Add other countries as needed
}

STATE_DICTIONARY: set[str] = {
    "lagos", "abuja", "fct", "rivers", "oyo", "kano", "kaduna",
    "edo", "enugu", "abia", "akwa ibom", "plateau", "ogun", "ondo",
    "imo", "cross river", "delta", "kwara",
}

# Hints for property type
PROPERTY_TYPE_HINTS: dict[PropertyType, tuple[str, ...]] = {
    PropertyType.APARTMENT: ("apartment", "flat", "studio", "self contain", "self-contain"),
    PropertyType.HOUSE: ("house", "home", "bungalow", "detached"),
    PropertyType.DUPLEX: ("duplex", "semi-detached", "semi detached", "terrace", "terraced"),
    PropertyType.BUNGALOW: ("bungalow",),
    PropertyType.LAND: ("land", "plot", "acre"),
    PropertyType.OFFICE: ("office", "workspace", "coworking", "co-working"),
    PropertyType.SHOP: ("shop", "store", "kiosk"),
    PropertyType.WAREHOUSE: ("warehouse", "storage"),
}

PURPOSE_HINTS: dict[ListingPurpose, tuple[str, ...]] = {
    ListingPurpose.RENT: ("rent", "renting", "lease", "per month", "per annum", "yearly", "/month", "/year"),
    ListingPurpose.SALE: ("buy", "buying", "purchase", "for sale", "sale"),
    ListingPurpose.SHORTLET: ("shortlet", "short let", "short-let", "airbnb", "per night", "daily", "/night"),
}

# Multipliers for shorthand prices
UNIT_MULTIPLIERS: dict[str, int] = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "bn": 1_000_000_000,
    "billion": 1_000_000_000,
}


# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

_BED_RE = re.compile(
    r"(\d+)\s*(?:\+|-)?\s*(?:bed(?:room)?s?|br|b/r)\b", re.IGNORECASE
)
_BATH_RE = re.compile(r"(\d+)\s*(?:bath(?:room)?s?|ba)\b", re.IGNORECASE)
_AREA_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:sqm|sq\.?m|square meters?|m2)\b", re.IGNORECASE)

# Price like "500k", "1.5m", "500,000", "NGN 500,000", "₦300k", "$2,000"
_PRICE_RE = re.compile(
    r"(?:₦|ngn|naira|\$|usd|€|eur|£|gbp)?\s*"
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(k|m|bn|thousand|million|billion)?\b",
    re.IGNORECASE,
)

_UNDER_RE = re.compile(r"\b(?:under|below|less than|max|up to|<=?)\b", re.IGNORECASE)
_OVER_RE = re.compile(r"\b(?:over|above|more than|min|at least|>=?)\b", re.IGNORECASE)
_BETWEEN_RE = re.compile(
    r"\b(?:between)\s+([\d.,]+\s*[kmb]?)\s+(?:and|to|-)\s+([\d.,]+\s*[kmb]?)",
    re.IGNORECASE,
)

_CURRENCY_MAP = {
    "₦": "NGN", "ngn": "NGN", "naira": "NGN",
    "$": "USD", "usd": "USD",
    "€": "EUR", "eur": "EUR",
    "£": "GBP", "gbp": "GBP",
}

_FURNISHED_RE = re.compile(r"\b(furnished|unfurnished|furnish)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_price(raw: str, unit: str | None) -> Decimal | None:
    """Convert "500k" or "1.5m" to Decimal. Returns None on garbage."""
    try:
        # Handle both "1,500" and "1.500,00" — this simplistic version assumes
        # comma = thousands separator (English locale). Refine per-locale later.
        cleaned = raw.replace(",", "")
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None

    if unit:
        mult = UNIT_MULTIPLIERS.get(unit.lower())
        if mult:
            value *= mult
    return value


def _find_city(text: str) -> str | None:
    """Longest match wins — so 'victoria island' beats 'victoria'."""
    lowered = text.lower()
    matches = [c for c in CITY_DICTIONARY if c in lowered]
    if not matches:
        return None
    return max(matches, key=len).title()


def _find_state(text: str) -> str | None:
    lowered = text.lower()
    matches = [s for s in STATE_DICTIONARY if re.search(rf"\b{re.escape(s)}\b", lowered)]
    if not matches:
        return None
    # If the city is also a state (e.g. Lagos), avoid duplicating.
    return max(matches, key=len).title()


def _find_property_type(text: str) -> PropertyType | None:
    lowered = text.lower()
    for ptype, hints in PROPERTY_TYPE_HINTS.items():
        if any(h in lowered for h in hints):
            return ptype
    return None


def _find_purpose(text: str) -> ListingPurpose | None:
    lowered = text.lower()
    # Shortlet beats rent because "shortlet per month" is unusual.
    for purpose in (ListingPurpose.SHORTLET, ListingPurpose.SALE, ListingPurpose.RENT):
        if any(h in lowered for h in PURPOSE_HINTS[purpose]):
            return purpose
    return None


def _find_price_range(text: str) -> tuple[Decimal | None, Decimal | None, str | None]:
    """Returns (min, max, currency). Rule-based, greedy."""
    currency: str | None = None
    for sym, code in _CURRENCY_MAP.items():
        if sym in text:
            currency = code
            break

    # "between X and Y"
    between = _BETWEEN_RE.search(text)
    if between:
        lo_raw, hi_raw = between.group(1), between.group(2)
        lo = _normalize_price(*_split_price(lo_raw))
        hi = _normalize_price(*_split_price(hi_raw))
        return lo, hi, currency

    # Scan every candidate price
    candidates: list[tuple[int, Decimal, bool]] = []  # (pos, value, has_qualifier)
    for m in _PRICE_RE.finditer(text):
        raw, unit = m.group(1), m.group(2)
        # Ignore tiny numbers (bedrooms, bathrooms, area — already stripped via context)
        value = _normalize_price(raw, unit)
        if value is None:
            continue
        # Ignore values that clearly aren't prices (< 100 and no unit)
        if value < 100 and not unit:
            continue

        # Look ~30 chars before for under/over qualifier
        before = text[max(0, m.start() - 30):m.start()].lower()
        candidates.append((m.start(), value, bool(_UNDER_RE.search(before) or _OVER_RE.search(before))))

    if not candidates:
        return None, None, currency

    # Prefer the first qualified candidate; else take min/max of all.
    qualified = [c for c in candidates if c[2]]
    pool = qualified or candidates
    values = [c[1] for c in pool]

    # Decide which candidate is min vs max by reading the preceding word.
    min_v: Decimal | None = None
    max_v: Decimal | None = None
    for pos, value, _ in pool:
        before = text[max(0, pos - 30):pos].lower()
        if _UNDER_RE.search(before) and max_v is None:
            max_v = value
        elif _OVER_RE.search(before) and min_v is None:
            min_v = value

    if min_v is None and max_v is None:
        # No qualifier — treat as the single target price.
        max_v = min(values)

    return min_v, max_v, currency


def _split_price(token: str) -> tuple[str, str | None]:
    """'500k' -> ('500', 'k')"""
    m = re.match(r"([\d.,]+)\s*([a-zA-Z]*)", token.strip())
    if not m:
        return token, None
    return m.group(1), (m.group(2) or None)


def _find_furnished(text: str) -> bool | None:
    m = _FURNISHED_RE.search(text)
    if not m:
        return None
    word = m.group(1).lower()
    if word == "unfurnished":
        return False
    if word == "furnish":
        return None
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def parse_search_query(raw_query: str) -> ParsedSearchFilters:
    """Parse a natural language search query into structured filters.

    Pure function. Async signature for future LLM-backed implementations.

    Examples
    --------
    >>> import asyncio
    >>> f = asyncio.run(parse_search_query("3 bedroom apartment in Lekki under 500k per month"))
    >>> f.bedrooms_min
    3
    >>> f.property_type.value
    'apartment'
    >>> f.city
    'Lekki'
    >>> f.purpose.value
    'rent'
    >>> f.max_price
    Decimal('500000')
    """
    text = raw_query.strip()

    bedrooms = None
    if m := _BED_RE.search(text):
        bedrooms = int(m.group(1))

    bathrooms = None
    if m := _BATH_RE.search(text):
        bathrooms = int(m.group(1))

    area_min = None
    if m := _AREA_RE.search(text):
        area_min = float(m.group(1))

    min_price, max_price, currency = _find_price_range(text)
    city = _find_city(text)
    state = _find_state(text)
    property_type = _find_property_type(text)
    purpose = _find_purpose(text)
    is_furnished = _find_furnished(text)

    # Sanity: min > max means the parser got confused. Swap.
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price

    return ParsedSearchFilters(
        q=text,
        keywords=[],  # reserved for LLM impl — rule-based version doesn't need it
        city=city,
        state=state,
        country=None,
        lat=None,
        lng=None,
        radius_km=None,
        property_type=property_type,
        purpose=purpose,
        min_price=min_price,
        max_price=max_price,
        currency=currency,
        bedrooms_min=bedrooms,
        bedrooms_max=None,
        bathrooms_min=bathrooms,
        area_sqm_min=area_min,
        is_furnished=is_furnished,
    )