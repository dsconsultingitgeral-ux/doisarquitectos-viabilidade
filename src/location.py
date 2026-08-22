from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import requests

@dataclass
class GeoResult:
    display_name: str
    lat: float
    lon: float
    address: dict
    source_url: str

def geocode_location(query: str) -> Optional[GeoResult]:
    """Geocode a free-text location through OpenStreetMap Nominatim.

    This is used only as an initial localisation aid. It must never be treated as
    proof of cadastral limits, plot area, PDM classification or legal identity.
    """
    if not query or not query.strip():
        return None

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query.strip(),
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "countrycodes": "pt",
    }
    headers = {
        "User-Agent": "doisarquitetos-viabilidade-v4/1.0"
    }
    r = requests.get(url, params=params, headers=headers, timeout=12)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    item = data[0]
    return GeoResult(
        display_name=item.get("display_name", query),
        lat=float(item["lat"]),
        lon=float(item["lon"]),
        address=item.get("address", {}) or {},
        source_url="https://www.openstreetmap.org/"
    )

def inferred_fields(result: GeoResult) -> dict:
    a = result.address
    municipality = (
        a.get("municipality")
        or a.get("city")
        or a.get("town")
        or a.get("county")
        or ""
    )
    parish = (
        a.get("suburb")
        or a.get("city_district")
        or a.get("village")
        or ""
    )
    locality = (
        a.get("neighbourhood")
        or a.get("suburb")
        or a.get("village")
        or a.get("city")
        or ""
    )
    road = a.get("road") or a.get("pedestrian") or a.get("residential") or ""
    postcode = a.get("postcode") or ""
    return {
        "municipality": municipality,
        "parish": parish,
        "locality": locality,
        "road": road,
        "postcode": postcode,
    }
