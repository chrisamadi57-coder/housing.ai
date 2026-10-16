"""Smoke test for app/services/search_parser.py — run:
    python -m scripts.test_search_parser
"""
from app.services.search_parser import parse_query_rules, parse_query


def section(title):
    print("\n" + "=" * 40)
    print(title)
    print("=" * 40)


# --- 1. Simple query ---
section("1. '3 bed flat in Lekki under 50m'")
r = parse_query_rules("3 bed flat in Lekki under 50m")
print(r)
assert r["property_type"] == "flat"
assert r["bedrooms"] == 3
assert r["location"] == "Lekki"
assert r["max_price"] == 50_000_000
assert r["min_price"] is None
print("PASS")


# --- 2. For rent + warehouse ---
section("2. 'warehouse for rent in Ikeja'")
r = parse_query_rules("warehouse for rent in Ikeja")
print(r)
assert r["property_type"] == "warehouse"
assert r["listing_type"] == "rent"
assert r["location"] == "Ikeja"
print("PASS")


# --- 3. Min price ---
section("3. 'land above 20m in Abuja'")
r = parse_query_rules("land above 20m in Abuja")
print(r)
assert r["property_type"] == "land"
assert r["min_price"] == 20_000_000
assert r["max_price"] is None
print("PASS")


# --- 4. Bathrooms + bedrooms ---
section("4. '3 bed 2 bath apartment in Victoria Island'")
r = parse_query_rules("3 bed 2 bath apartment in Victoria Island")
print(r)
assert r["property_type"] == "flat"    # 'apartment' maps to 'flat'
assert r["bedrooms"] == 3
assert r["bathrooms"] == 2
assert r["location"] == "Victoria Island"
print("PASS")


# --- 5. Billion suffix ---
section("5. 'land for sale under 2b'")
r = parse_query_rules("land for sale under 2b")
print(r)
assert r["max_price"] == 2_000_000_000
print("PASS")


# --- 6. Empty query — all fields None ---
section("6. Unrecognized query → all None")
r = parse_query_rules("hello world")
print(r)
assert r["property_type"] is None
assert r["location"] is None
assert r["max_price"] is None
print("PASS")


# --- 7. Public parse_query() with no API key ---
section("7. parse_query() falls back to rules when no key")
r = parse_query("2 bed house in Yaba")
print(r)
assert r["parser"] == "rules"
assert r["bedrooms"] == 2
assert r["property_type"] == "house"
assert r["location"] == "Yaba"
print("PASS")


print("\nAll checks passed. search_parser.py is good.")