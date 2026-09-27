"""
Location verification for uploaded media.

Given:
  - the upload's GPS coordinates (from the form or EXIF)
  - the property's claimed GPS coordinates (from the listing)

...we compute the distance and produce a verdict.

The distance uses the haversine formula — the standard way to measure
distance between two points on a sphere. Accurate enough for
city-scale verification, which is all we need.
"""

from math import radians, sin, cos, sqrt, atan2
from typing import Any

from app.config import settings

# Earth's mean radius in meters.
EARTH_RADIUS_M = 6_371_000


def haversine_meters(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
) -> float:
    """
    Distance in meters between two (lat, lng) points on Earth.

    Uses the haversine formula. All inputs are in degrees
    (as GPS typically reports). Output is meters.
    """
    # Convert to radians — sin/cos work in radians.
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lng2 - lng1)

    # The "haversine" of the central angle.
    a = (
        sin(d_phi / 2) ** 2
        + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    )

    # Central angle in radians.
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    # Arc length on the sphere.
    return EARTH_RADIUS_M * c


def verify_location(
    upload_gps: dict[str, float],
    property_gps: dict[str, float],
    threshold_meters: int | None = None,
) -> dict[str, Any]:
    """
    Compare uploaded GPS against claimed property GPS.

    Args:
        upload_gps:      {"lat": float, "lng": float}
        property_gps:    {"lat": float, "lng": float}
        threshold_meters: optional override; defaults to settings value

    Returns:
        {
            "verified": bool,
            "distance_meters": float,
            "threshold_meters": int,
            "reason": str,
        }
    """
    threshold = threshold_meters or settings.gps_max_distance_meters

    distance = haversine_meters(
        upload_gps["lat"], upload_gps["lng"],
        property_gps["lat"], property_gps["lng"],
    )

    verified = distance <= threshold

    if verified:
        reason = f"Within {threshold}m of claimed property"
    else:
        reason = (
            f"Outside {threshold}m threshold "
            f"(actual distance: {round(distance)}m)"
        )

    return {
        "verified": verified,
        "distance_meters": round(distance, 2),
        "threshold_meters": threshold,
        "reason": reason,
    }