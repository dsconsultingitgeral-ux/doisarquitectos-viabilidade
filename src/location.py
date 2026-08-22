from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import requests

HEADERS = {"User-Agent": "doisarquitetos-previabilidade/4.2-plus"}

@dataclass
class GeoResult:
    display_name: str
    lat: float
    lon: float
    address: dict
    source_url: str

def _result(item, fallback="") -> GeoResult:
    return GeoResult(
        display_name=item.get("display_name", fallback),
        lat=float(item["lat"]),
        lon=float(item["lon"]),
        address=item.get("address", {}) or {},
        source_url="https://www.openstreetmap.org/"
    )

def geocode_location(query: str) -> Optional[GeoResult]:
    if not query or not query.strip():
        return None
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": query.strip(),
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 1,
            "countrycodes": "pt",
        },
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    return _result(data[0], query) if data else None

def reverse_geocode(lat: float, lon: float) -> Optional[GeoResult]:
    r = requests.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={
            "lat": lat,
            "lon": lon,
            "format": "jsonv2",
            "addressdetails": 1,
            "zoom": 18,
        },
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    item = r.json()
    return _result(item) if item and item.get("lat") else None

def inferred_fields(result: GeoResult) -> dict:
    a = result.address
    municipality = a.get("municipality") or a.get("city") or a.get("town") or a.get("county") or ""
    parish = a.get("parish") or a.get("suburb") or a.get("city_district") or a.get("village") or ""
    locality = a.get("neighbourhood") or a.get("suburb") or a.get("village") or a.get("city") or ""
    road = a.get("road") or a.get("pedestrian") or a.get("residential") or ""
    postcode = a.get("postcode") or ""
    house_number = a.get("house_number") or ""
    concise = ", ".join([x for x in [f"{road} {house_number}".strip(), locality, municipality] if x])
    return {
        "municipality": municipality,
        "parish": parish,
        "locality": locality,
        "road": road,
        "postcode": postcode,
        "house_number": house_number,
        "concise": concise or result.display_name,
    }
