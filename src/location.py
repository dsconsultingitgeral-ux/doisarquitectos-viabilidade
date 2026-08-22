from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import requests

HEADERS = {"User-Agent": "doisarquitetos-viabilidade-urbanistica/1.0"}

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

def _search(q: str, viewbox: str | None = None, bounded: int = 0):
    params = {
        "q": q.strip(),
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 5,
        "countrycodes": "pt",
        "accept-language": "pt",
    }
    if viewbox:
        params["viewbox"] = viewbox
        params["bounded"] = bounded
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params=params,
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

def geocode_location(query: str) -> Optional[GeoResult]:
    """Robust free-text geocoding for Portugal.

    Tries the original phrase, a Portugal-qualified phrase, and a locality-first
    fallback that is useful for small streets such as "Rua X, Sandim".
    """
    if not query or not query.strip():
        return None

    raw = " ".join(query.strip().split())
    attempts = [raw]

    if "portugal" not in raw.lower():
        attempts.append(f"{raw}, Portugal")

    # Direct attempts first.
    for q in attempts:
        try:
            data = _search(q)
            if data:
                return _result(data[0], raw)
        except requests.RequestException:
            pass

    # If the user typed "street, locality", first locate the locality and then
    # constrain the street search around that area.
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) >= 2:
        street = parts[0]
        locality = parts[-1]
        try:
            locality_results = _search(f"{locality}, Portugal")
            if locality_results:
                loc = locality_results[0]
                bbox = loc.get("boundingbox") or []
                viewbox = None
                if len(bbox) == 4:
                    # Nominatim expects left,top,right,bottom = lon1,lat2,lon2,lat1
                    south, north, west, east = bbox
                    viewbox = f"{west},{north},{east},{south}"

                # Try the full phrase again constrained to the locality.
                for q in (
                    f"{street}, {locality}, Portugal",
                    street,
                ):
                    results = _search(q, viewbox=viewbox, bounded=1 if viewbox else 0)
                    if results:
                        return _result(results[0], raw)

                # If the exact street is absent from OSM, return the locality so
                # the user can still continue and click the map precisely.
                return _result(loc, raw)
        except requests.RequestException:
            pass

    return None

def reverse_geocode(lat: float, lon: float) -> Optional[GeoResult]:
    r = requests.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={
            "lat": lat,
            "lon": lon,
            "format": "jsonv2",
            "addressdetails": 1,
            "zoom": 18,
            "accept-language": "pt",
        },
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    item = r.json()
    return _result(item) if item and item.get("lat") else None

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
        a.get("parish")
        or a.get("suburb")
        or a.get("city_district")
        or a.get("village")
        or ""
    )
    locality = (
        a.get("neighbourhood")
        or a.get("suburb")
        or a.get("village")
        or a.get("town")
        or a.get("city")
        or ""
    )
    road = a.get("road") or a.get("pedestrian") or a.get("residential") or ""
    postcode = a.get("postcode") or ""
    house_number = a.get("house_number") or ""
    concise = ", ".join(
        [x for x in [f"{road} {house_number}".strip(), locality, municipality] if x]
    )
    return {
        "municipality": municipality,
        "parish": parish,
        "locality": locality,
        "road": road,
        "postcode": postcode,
        "house_number": house_number,
        "concise": concise or result.display_name,
    }
