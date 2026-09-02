"""Automated facility location scraping via OpenStreetMap Overpass API.

Collects coordinates and details of hospitals, welfare trusts, and
scholarship offices across Pakistani cities (defaulting to Karachi).
Results are de-duplicated and persisted to the SQLite facilities table.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Overpass API configuration
# ---------------------------------------------------------------------------
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_TIMEOUT = 25  # seconds for Overpass query
DEFAULT_RADIUS = 15000  # metres around city centre

# City centre coordinates for Pakistan's major cities
CITY_CENTRES: dict[str, tuple[float, float]] = {
    "Karachi": (24.8607, 67.0011),
    "Lahore": (31.5204, 74.3587),
    "Islamabad": (33.6844, 73.0479),
    "Rawalpindi": (33.5651, 73.0169),
    "Peshawar": (34.0151, 71.5249),
    "Quetta": (30.1798, 66.9750),
    "Faisalabad": (31.4504, 73.1350),
    "Multan": (30.1575, 71.5249),
    "Hyderabad": (25.3960, 68.3578),
    "Sukkur": (27.7052, 68.8574),
}

# Amenity filters mapped to our category system
AMENITY_QUERIES: dict[str, dict[str, str]] = {
    "hospital": {
        "selector": '[amenity=hospital]',
        "category": "hospital",
        "facility_type": "Hospital / Medical Center",
    },
    "clinic": {
        "selector": '[amenity=clinic]',
        "category": "hospital",
        "facility_type": "Clinic / Health Center",
    },
    "pharmacy": {
        "selector": '[amenity=pharmacy]',
        "category": "hospital",
        "facility_type": "Pharmacy",
    },
    "social_facility": {
        "selector": '[amenity=social_facility]',
        "category": "welfare",
        "facility_type": "Welfare / Social Center",
    },
    "community_centre": {
        "selector": '[amenity=community_centre]',
        "category": "welfare",
        "facility_type": "Community / Welfare Center",
    },
    "university": {
        "selector": '[amenity=university]',
        "category": "university",
        "facility_type": "University / Scholarship Office",
    },
    "college": {
        "selector": '[amenity=college]',
        "category": "university",
        "facility_type": "College / Education Center",
    },
}


# ---------------------------------------------------------------------------
# Core fetcher
# ---------------------------------------------------------------------------

def fetch_facilities(
    city: str = "Karachi",
    categories: list[str] | None = None,
    radius: int = DEFAULT_RADIUS,
) -> list[dict[str, Any]]:
    """Query Overpass API and return a list of raw facility dicts.

    Parameters
    ----------
    city : str
        City name (must be in CITY_CENTRES or a nominatim lookup is attempted).
    categories : list[str] | None
        List of amenity keys to query (e.g. ["hospital", "welfare"]).
        Defaults to all known categories.
    radius : int
        Search radius in metres around the city centre.
    """
    centre = CITY_CENTRES.get(city)
    if not centre:
        centre = _geocode_city(city)
    if not centre:
        return []

    lat, lon = centre
    if categories is None:
        categories = list(AMENITY_QUERIES.keys())

    # Build a union query for all requested amenity types
    selectors = []
    for cat in categories:
        info = AMENITY_QUERIES.get(cat)
        if info:
            selectors.append(info["selector"])

    if not selectors:
        return []

    union = ";".join(
        f"nwr(around:{radius},{lat},{lon}){sel}" for sel in selectors
    )
    query = f"[out:json][timeout:{DEFAULT_TIMEOUT}];({union});out center 50;"

    try:
        res = requests.post(OVERPASS_URL, data=query, timeout=DEFAULT_TIMEOUT + 5)
        res.raise_for_status()
        data = res.json()
    except Exception:
        return []

    facilities: list[dict[str, Any]] = []
    for element in data.get("elements", []):
        parsed = _parse_element(element, city, lat, lon)
        if parsed:
            facilities.append(parsed)

    return facilities


def collect_and_store(
    city: str = "Karachi",
    categories: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch facilities from Overpass and store unique ones in SQLite.

    Returns a summary dict with counts.
    """
    from . import database as db

    raw = fetch_facilities(city=city, categories=categories)
    added = 0
    skipped = 0

    for fac in raw:
        if db.insert_facility(fac):
            added += 1
        else:
            skipped += 1

    return {
        "city": city,
        "fetched": len(raw),
        "added": added,
        "duplicates_skipped": skipped,
        "total_in_db": db.facility_count(),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_element(
    element: dict[str, Any], city: str, centre_lat: float, centre_lon: float,
) -> dict[str, Any] | None:
    """Convert an Overpass element into a clean facility dict."""
    tags = element.get("tags", {})
    if not tags:
        return None

    name = tags.get("name", "").strip()
    if not name or len(name) < 3:
        # Try alternative tag names
        name = tags.get("official_name", tags.get("alt_name", "")).strip()
    if not name:
        return None

    # Determine coordinates
    if element.get("type") == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    else:
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        return None

    # Determine category from amenity tag
    amenity = tags.get("amenity", "")
    category = "welfare"
    facility_type = "Facility"
    for key, info in AMENITY_QUERIES.items():
        if amenity == key:
            category = info["category"]
            facility_type = info["facility_type"]
            break

    # Build address from available tags
    addr_parts = []
    for tag_key in ("addr:street", "addr:road", "addr:suburb", "addr:district", "addr:city"):
        val = tags.get(tag_key, "")
        if val and val not in addr_parts:
            addr_parts.append(val)
    address = ", ".join(addr_parts) if addr_parts else f"{name}, {city}"

    # Build unique ID
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower())[:30].strip("_")
    fac_id = f"geo_{slug}_{int(lat * 10000)}_{int(lon * 10000)}"

    return {
        "id": fac_id,
        "name": name,
        "category": category,
        "city": city,
        "zone": tags.get("addr:suburb", tags.get("addr:district", "")),
        "address": address,
        "phone": tags.get("phone", tags.get("contact:phone", "")),
        "facility_type": facility_type,
        "lat": float(lat),
        "lon": float(lon),
        "source": "overpass",
    }


def _geocode_city(city: str) -> tuple[float, float] | None:
    """Attempt to geocode an unknown city via Nominatim."""
    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{city}, Pakistan", "format": "json", "limit": 1},
            headers={"User-Agent": "KhidmatAI-GeoScraper/6.0"},
            timeout=8,
        )
        data = res.json()
        if data and len(data) > 0:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None
