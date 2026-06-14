"""
Geographic utility functions for the allocation agent.
Pure Python — no external dependencies beyond stdlib math.
"""

import math
from typing import List, Tuple, Optional


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great-circle distance in kilometres between two points
    on Earth using the Haversine formula.

    Args:
        lat1, lng1: Coordinates of point A (decimal degrees).
        lat2, lng2: Coordinates of point B (decimal degrees).

    Returns:
        Distance in kilometres (float).
    """
    R = 6371.0  # Earth radius in km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def nearest_resources(
    inc_lat: float,
    inc_lng: float,
    resources: list,
    preferred_types: Optional[List[str]] = None,
    max_distance_km: float = 500.0,
    top_n: int = 3,
) -> List[Tuple[object, float]]:
    """
    Find the nearest available resources to an incident location.

    Args:
        inc_lat, inc_lng: Incident coordinates.
        resources: List of Resource ORM objects with .lat, .lng, .type attributes.
        preferred_types: Ordered list of preferred resource types (first = most preferred).
        max_distance_km: Hard cutoff — resources beyond this are excluded.
        top_n: Maximum number of results to return.

    Returns:
        List of (Resource, distance_km) tuples sorted by:
          1. Type preference index (lower index = higher preference).
          2. Distance ascending within same preference tier.
        Returns empty list if no resources are within range.
    """
    if not resources:
        return []

    candidates: List[Tuple[object, float, int]] = []

    for resource in resources:
        try:
            distance = haversine(inc_lat, inc_lng, resource.lat, resource.lng)
        except Exception:
            continue

        if distance > max_distance_km:
            continue

        # Preference index: lower = better match
        if preferred_types and resource.type in preferred_types:
            pref_index = preferred_types.index(resource.type)
        else:
            pref_index = len(preferred_types) if preferred_types else 999

        candidates.append((resource, distance, pref_index))

    # Sort: primary = type preference, secondary = distance
    candidates.sort(key=lambda x: (x[2], x[1]))

    return [(resource, distance) for resource, distance, _ in candidates[:top_n]]


def bbox_filter(
    resources: list,
    center_lat: float,
    center_lng: float,
    radius_km: float,
) -> list:
    """
    Quick bounding-box pre-filter before running Haversine.
    Reduces candidate set for large resource pools.

    Args:
        resources: List of Resource ORM objects.
        center_lat, center_lng: Center point.
        radius_km: Approximate radius to filter within.

    Returns:
        Subset of resources within the bounding box.
    """
    # Approximate degree offsets (1 degree lat ≈ 111km)
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * math.cos(math.radians(center_lat)) + 1e-9)

    lat_min = center_lat - lat_delta
    lat_max = center_lat + lat_delta
    lng_min = center_lng - lng_delta
    lng_max = center_lng + lng_delta

    return [
        r for r in resources
        if lat_min <= r.lat <= lat_max and lng_min <= r.lng <= lng_max
]
