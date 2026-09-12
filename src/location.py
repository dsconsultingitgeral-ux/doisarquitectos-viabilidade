from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import re
import unicodedata
import requests

HEADERS = {"User-Agent": "doisarquitetos-viabilidade-urbanistica/1.1"}

@dataclass
class GeoResult:
    display_name: str
    lat: float
    lon: float
    address: dict
    source_url: str
    precision: str = "unknown"  # exact_street | street | locality | unknown


def _ascii(value: str) -> str:
    return unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")


def _norm(value: str) -> str:
    value = _ascii(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _result(item, fallback="", precision="unknown") -> GeoResult:
    return GeoResult(
        display_name=item.get("display_name", fallback),
        lat=float(item["lat"]),
        lon=float(item["lon"]),
        address=item.get("address", {}) or {},
        source_url="https://www.openstreetmap.org/",
        precision=precision,
    )


def _search(q: str, viewbox: str | None = None, bounded: int = 0, limit: int = 10):
    params = {
        "q": q.strip(),
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": limit,
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



def _arcgis_search(q: str, limit: int = 10):
    """Fallback sem chave de API usando o World Geocoding Service da Esri.

    Devolve uma lista normalizada para a mesma estrutura mínima usada pelo
    restante módulo. É usado apenas quando Nominatim falha/não devolve dados.
    """
    params = {
        "SingleLine": q.strip(),
        "f": "json",
        "countryCode": "PRT",
        "maxLocations": max(1, min(int(limit), 20)),
        "outFields": "*",
        "langCode": "PT",
    }
    r = requests.get(
        "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates",
        params=params,
        headers=HEADERS,
        timeout=12,
    )
    r.raise_for_status()
    data = r.json() or {}
    out = []
    for c in data.get("candidates", []) or []:
        loc = c.get("location") or {}
        attrs = c.get("attributes") or {}
        if "y" not in loc or "x" not in loc:
            continue
        addr_type = str(attrs.get("Addr_type") or attrs.get("Type") or "").lower()
        address = {
            "road": attrs.get("StName") or attrs.get("StAddr") or "",
            "house_number": attrs.get("AddNum") or "",
            "postcode": attrs.get("Postal") or attrs.get("PostalExt") or "",
            "suburb": attrs.get("Neighborhood") or attrs.get("District") or "",
            "village": attrs.get("City") or "",
            "town": attrs.get("City") or "",
            "city": attrs.get("City") or "",
            "municipality": attrs.get("Subregion") or attrs.get("City") or "",
            "county": attrs.get("Subregion") or "",
            "state": attrs.get("Region") or "",
            "country": attrs.get("Country") or "Portugal",
        }
        # Remover chaves vazias para não poluir a lógica a jusante.
        address = {k: v for k, v in address.items() if v}
        out.append({
            "display_name": c.get("address") or q,
            "lat": str(loc["y"]),
            "lon": str(loc["x"]),
            "address": address,
            "importance": float(c.get("score", 0) or 0) / 100.0,
            "type": "road" if any(x in addr_type for x in ("address", "street")) else "place",
            "addresstype": "road" if any(x in addr_type for x in ("address", "street")) else "place",
            "_provider": "arcgis",
            "_addr_type": addr_type,
        })
    return out


def _arcgis_reverse(lat: float, lon: float):
    params = {
        "location": f"{lon},{lat}",
        "f": "json",
        "langCode": "PT",
        "featureTypes": "PointAddress,StreetAddress,StreetName,Locality,Postal",
    }
    r = requests.get(
        "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode",
        params=params,
        headers=HEADERS,
        timeout=12,
    )
    r.raise_for_status()
    data = r.json() or {}
    a = data.get("address") or {}
    loc = data.get("location") or {}
    if not a or "y" not in loc or "x" not in loc:
        return None
    road = a.get("Address") or a.get("ShortLabel") or ""
    address = {
        "road": road,
        "postcode": a.get("Postal") or "",
        "suburb": a.get("Neighborhood") or a.get("District") or "",
        "village": a.get("City") or "",
        "town": a.get("City") or "",
        "city": a.get("City") or "",
        "municipality": a.get("Subregion") or a.get("City") or "",
        "county": a.get("Subregion") or "",
        "state": a.get("Region") or "",
        "country": a.get("CountryCode") or "Portugal",
    }
    address = {k: v for k, v in address.items() if v}
    return {
        "display_name": a.get("LongLabel") or a.get("Match_addr") or road or f"{lat},{lon}",
        "lat": str(loc["y"]),
        "lon": str(loc["x"]),
        "address": address,
        "_provider": "arcgis",
    }


def _coordinates_result(raw: str):
    """Aceita coordenadas no formato 'lat, lon' ou 'lat lon'."""
    m = re.fullmatch(r"\s*(-?\d{1,2}(?:\.\d+)?)\s*[,; ]\s*(-?\d{1,3}(?:\.\d+)?)\s*", raw)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    try:
        return reverse_geocode(lat, lon)
    except Exception:
        return GeoResult(
            display_name=f"{lat:.6f}, {lon:.6f}", lat=lat, lon=lon,
            address={}, source_url="https://www.openstreetmap.org/", precision="unknown"
        )

def _street_variants(street: str) -> list[str]:
    """Generate realistic Portuguese street-name variants.

    OSM can store 'Rua Juncais' while a user writes 'Rua dos Juncais'.
    We try both forms, plus variants without the street prefix.
    """
    s = re.sub(r"\s+", " ", street.strip())
    variants = [s]

    # Remove Portuguese contractions/articles immediately after a street type.
    substitutions = [
        (r"^(Rua|Avenida|Av\.?|Travessa|Largo|Praceta|Estrada)\s+dos\s+", r"\1 "),
        (r"^(Rua|Avenida|Av\.?|Travessa|Largo|Praceta|Estrada)\s+das\s+", r"\1 "),
        (r"^(Rua|Avenida|Av\.?|Travessa|Largo|Praceta|Estrada)\s+do\s+", r"\1 "),
        (r"^(Rua|Avenida|Av\.?|Travessa|Largo|Praceta|Estrada)\s+da\s+", r"\1 "),
        (r"^(Rua|Avenida|Av\.?|Travessa|Largo|Praceta|Estrada)\s+de\s+", r"\1 "),
    ]
    for pattern, repl in substitutions:
        candidate = re.sub(pattern, repl, s, flags=re.I)
        if candidate != s:
            variants.append(candidate)

    # Also try only the significant name portion.
    no_prefix = re.sub(
        r"^(Rua|Avenida|Av\.?|Travessa|Largo|Praceta|Estrada)\s+",
        "",
        s,
        flags=re.I,
    ).strip()
    if no_prefix and no_prefix not in variants:
        variants.append(no_prefix)

    # Remove duplicates preserving order.
    out = []
    seen = set()
    for v in variants:
        key = _norm(v)
        if key and key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _candidate_road(item: dict) -> str:
    a = item.get("address", {}) or {}
    return (
        a.get("road")
        or a.get("pedestrian")
        or a.get("residential")
        or a.get("footway")
        or item.get("name")
        or ""
    )


def _candidate_locality_text(item: dict) -> str:
    a = item.get("address", {}) or {}
    vals = [
        a.get("parish"),
        a.get("suburb"),
        a.get("village"),
        a.get("town"),
        a.get("city"),
        a.get("municipality"),
        a.get("county"),
        item.get("display_name"),
    ]
    return " ".join([str(x) for x in vals if x])


def _score_candidate(item: dict, street_variants: list[str], locality: str) -> int:
    """Prefer the requested street inside the requested locality."""
    road = _norm(_candidate_road(item))
    display = _norm(item.get("display_name", ""))
    locality_text = _norm(_candidate_locality_text(item))
    locality_norm = _norm(locality)

    score = 0
    for idx, variant in enumerate(street_variants):
        vn = _norm(variant)
        # Remove street prefixes for flexible comparison.
        name_only = re.sub(
            r"^(rua|avenida|av|travessa|largo|praceta|estrada)\s+",
            "",
            vn,
        ).strip()

        if road == vn:
            score = max(score, 120 - idx)
        if name_only and road.endswith(name_only):
            score = max(score, 112 - idx)
        if name_only and name_only in road:
            score = max(score, 105 - idx)
        if vn and vn in display:
            score = max(score, 100 - idx)
        if name_only and name_only in display:
            score = max(score, 95 - idx)

    if locality_norm and locality_norm in locality_text:
        score += 35

    # Road objects are preferable to locality centroids.
    addresstype = (item.get("addresstype") or item.get("type") or "").lower()
    if addresstype in {"road", "residential", "pedestrian", "street"}:
        score += 25

    return score


def _best_street_result(results: list[dict], street_variants: list[str], locality: str):
    if not results:
        return None
    scored = sorted(
        (( _score_candidate(item, street_variants, locality), item) for item in results),
        key=lambda x: x[0],
        reverse=True,
    )
    best_score, best = scored[0]
    # Require meaningful street evidence. This avoids silently accepting only
    # the parish centroid when the exact street was not found.
    return best if best_score >= 90 else None


def geocode_location(query: str) -> Optional[GeoResult]:
    """Geocode a Portuguese address, prioritizing the exact street.

    For input like 'Rua dos Juncais, Sandim', the function:
    1) resolves Sandim;
    2) searches the street inside Sandim's bounding box;
    3) tries Portuguese naming variants such as 'Rua Juncais';
    4) only falls back to the locality if the street genuinely cannot be found.
    """
    if not query or not query.strip():
        return None

    raw = " ".join(query.strip().split())

    coord = _coordinates_result(raw)
    if coord is not None:
        return coord

    parts = [p.strip() for p in raw.split(",") if p.strip()]

    # Strong path for "street, locality".
    if len(parts) >= 2:
        street = parts[0]
        locality = parts[-1]
        street_variants = _street_variants(street)

        locality_result = None
        viewbox = None

        try:
            locality_results = _search(f"{locality}, Portugal", limit=10)
            if locality_results:
                # Prefer a result explicitly matching the locality string.
                locality_results = sorted(
                    locality_results,
                    key=lambda item: (
                        1 if _norm(locality) in _norm(_candidate_locality_text(item)) else 0,
                        float(item.get("importance", 0) or 0),
                    ),
                    reverse=True,
                )
                locality_result = locality_results[0]

                bbox = locality_result.get("boundingbox") or []
                if len(bbox) == 4:
                    south, north, west, east = bbox
                    viewbox = f"{west},{north},{east},{south}"
        except requests.RequestException:
            locality_result = None

        # Search every useful street variant, constrained to the locality when possible.
        all_candidates = []
        for variant in street_variants:
            queries = [
                f"{variant}, {locality}, Portugal",
                f"{variant}, {locality}",
            ]
            for q in queries:
                try:
                    all_candidates.extend(
                        _search(q, viewbox=viewbox, bounded=1 if viewbox else 0, limit=10)
                    )
                except requests.RequestException:
                    pass

        # As a final exact-street attempt, search the significant street name
        # within the locality bounding box.
        if viewbox:
            for variant in street_variants:
                try:
                    all_candidates.extend(
                        _search(variant, viewbox=viewbox, bounded=1, limit=10)
                    )
                except requests.RequestException:
                    pass

        best = _best_street_result(all_candidates, street_variants, locality)
        if best:
            return _result(best, raw, precision="exact_street")

        # If exact street is not in OSM, return locality as a controlled fallback.
        if locality_result:
            return _result(locality_result, raw, precision="locality")

    # Generic path for full addresses, localities or coordinates-like free text.
    generic_queries = [raw]
    if "portugal" not in raw.lower():
        generic_queries.append(f"{raw}, Portugal")

    generic_candidates = []
    for q in generic_queries:
        try:
            generic_candidates.extend(_search(q, limit=10))
        except requests.RequestException:
            pass

    if generic_candidates:
        # Prefer results that actually contain the original significant terms.
        query_norm = _norm(raw)
        generic_candidates = sorted(
            generic_candidates,
            key=lambda item: (
                1 if query_norm and query_norm in _norm(item.get("display_name", "")) else 0,
                float(item.get("importance", 0) or 0),
            ),
            reverse=True,
        )
        return _result(generic_candidates[0], raw, precision="street")

    # Fallback independente: ArcGIS. Isto evita que uma indisponibilidade,
    # rate-limit ou bloqueio do Nominatim inutilize toda a Etapa 01.
    arc_queries = [raw]
    if "portugal" not in raw.lower():
        arc_queries.append(f"{raw}, Portugal")
    for q in arc_queries:
        try:
            candidates = _arcgis_search(q, limit=10)
            if candidates:
                first = candidates[0]
                addr_type = (first.get("_addr_type") or "").lower()
                precision = "exact_street" if any(x in addr_type for x in ("address", "street")) else "locality"
                return _result(first, raw, precision=precision)
        except requests.RequestException:
            continue

    return None


def reverse_geocode(lat: float, lon: float) -> Optional[GeoResult]:
    # 1) Nominatim
    try:
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
            timeout=12,
        )
        r.raise_for_status()
        item = r.json()
        if item and item.get("lat"):
            return _result(item, precision="exact_street")
    except (requests.RequestException, ValueError, TypeError):
        pass

    # 2) ArcGIS fallback para cliques no mapa.
    try:
        item = _arcgis_reverse(lat, lon)
        if item:
            return _result(item, precision="exact_street")
    except (requests.RequestException, ValueError, TypeError):
        pass

    return None


def inferred_fields(result: GeoResult) -> dict:
    a = result.address

    municipality = (
        a.get("municipality")
        or a.get("city")
        or a.get("town")
        or a.get("county")
        or ""
    )

    # Prefer the administrative parish field. In Portugal OSM/Nominatim does
    # not always expose "parish" even when the place name clearly corresponds
    # to the freguesia. We therefore use a controlled hierarchy and, when the
    # parish is absent, reuse the best locality-level administrative name.
    parish = (
        a.get("parish")
        or a.get("city_district")
        or a.get("suburb")
        or a.get("village")
        or a.get("hamlet")
        or a.get("locality")
        or ""
    )

    locality = (
        a.get("neighbourhood")
        or a.get("suburb")
        or a.get("village")
        or a.get("hamlet")
        or a.get("locality")
        or a.get("town")
        or a.get("city")
        or parish
        or ""
    )

    # If Nominatim supplied a locality but omitted the parish, that locality is
    # generally the best available freguesia-level label for this workflow.
    # Avoid copying the municipality name into the parish field.
    if not parish and locality and locality.strip().lower() != municipality.strip().lower():
        parish = locality

    road = (
        a.get("road")
        or a.get("pedestrian")
        or a.get("residential")
        or ""
    )
    postcode = a.get("postcode") or ""
    house_number = a.get("house_number") or ""

    concise = ", ".join(
        [x for x in [f"{road} {house_number}".strip(), parish or locality, municipality] if x]
    )

    return {
        "municipality": municipality,
        "parish": parish,
        "locality": locality,
        "road": road,
        "postcode": postcode,
        "house_number": house_number,
        "concise": concise or result.display_name,
        "precision": result.precision,
    }
