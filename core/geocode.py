from __future__ import annotations
import requests

HEADERS = {"User-Agent": "doisarquitectos-viabilidade/2.0 (technical feasibility tool)"}

def geocode_location(query: str):
    if not query.strip():
        return []
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "jsonv2", "limit": 5, "countrycodes": "pt", "addressdetails": 1}
    r = requests.get(url, params=params, headers=HEADERS, timeout=12)
    r.raise_for_status()
    return r.json()
