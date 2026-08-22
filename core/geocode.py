from __future__ import annotations
import re
import requests

HEADERS = {
    "User-Agent": "doisarquitectos-viabilidade/2.1 (technical feasibility tool; contact: info@doisarquitectos.com)",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.5",
}


def _clean_query(query: str) -> str:
    q = re.sub(r"\s+", " ", (query or "").strip())
    return q


def _nominatim(query: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 5,
        "countrycodes": "pt",
        "addressdetails": 1,
        "accept-language": "pt",
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


def _arcgis(query: str):
    """Fallback público para geocodificação. Normaliza o resultado para o formato Nominatim."""
    url = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
    params = {
        "SingleLine": query,
        "f": "json",
        "countryCode": "PRT",
        "maxLocations": 5,
        "outFields": "Match_addr,LongLabel,City,Subregion,Region,Postal,Neighborhood,District",
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    out = []
    for c in data.get("candidates", []):
        loc = c.get("location") or {}
        attrs = c.get("attributes") or {}
        if "x" not in loc or "y" not in loc:
            continue
        city = attrs.get("City") or ""
        region = attrs.get("Region") or ""
        subregion = attrs.get("Subregion") or ""
        neighborhood = attrs.get("Neighborhood") or attrs.get("District") or ""
        out.append({
            "lat": str(loc["y"]),
            "lon": str(loc["x"]),
            "display_name": attrs.get("LongLabel") or c.get("address") or query,
            "address": {
                "city": city,
                "town": city,
                "municipality": subregion or city,
                "suburb": neighborhood,
                "village": neighborhood,
                "state": region,
                "postcode": attrs.get("Postal") or "",
            },
            "source": "ArcGIS World Geocoder",
            "score": c.get("score", 0),
        })
    return out


def geocode_location(query: str):
    q = _clean_query(query)
    if not q:
        return []

    # Várias formulações aumentam muito a taxa de acerto de arruamentos portugueses.
    candidates = [q]
    if "portugal" not in q.lower():
        candidates.append(f"{q}, Portugal")

    # Para moradas do tipo "Rua X, freguesia, concelho", tenta também com código do país explícito.
    parts = [p.strip() for p in q.split(",") if p.strip()]
    if len(parts) >= 2:
        candidates.append(", ".join(parts[:2]) + ", Portugal")

    seen = set()
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            res = _nominatim(candidate)
            if res:
                for item in res:
                    item.setdefault("source", "OpenStreetMap/Nominatim")
                return res
        except Exception:
            pass

    # Fallback independente do OpenStreetMap. Evita deixar o mapa preso na localização anterior.
    for candidate in candidates:
        try:
            res = _arcgis(candidate)
            if res:
                return res
        except Exception:
            pass
    return []
