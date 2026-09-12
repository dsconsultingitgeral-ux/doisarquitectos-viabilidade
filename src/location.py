from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import re
import unicodedata
import requests

HEADERS = {"User-Agent": "doisarquitectos-viabilidade-urbanistica/6.2"}
COUNTRY_WORDS = {"portugal", "pt", "prt"}
STREET_RE = re.compile(r"^(rua|avenida|av\.?|travessa|tv\.?|largo|praceta|estrada|alameda|rotunda|beco|caminho)\b", re.I)
POSTCODE_RE = re.compile(r"^\s*\d{4}(?:-\d{3})?\s*")


@dataclass
class GeoResult:
    display_name: str
    lat: float
    lon: float
    address: dict
    source_url: str
    precision: str = "unknown"  # exact_street | street | locality | coordinates | unknown


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
        source_url=item.get("source_url") or "https://www.openstreetmap.org/",
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
        timeout=12,
    )
    r.raise_for_status()
    return r.json()


def _arcgis_search(q: str, limit: int = 10):
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
            "source_url": "https://www.arcgis.com/",
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
        "source_url": "https://www.arcgis.com/",
    }


def _coordinates_result(raw: str):
    m = re.fullmatch(r"\s*(-?\d{1,2}(?:\.\d+)?)\s*[,; ]\s*(-?\d{1,3}(?:\.\d+)?)\s*", raw)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    # Coordinates typed by the user are authoritative. Reverse geocoding is
    # only used to add a human-readable label; it must never move the point.
    try:
        rev = reverse_geocode(lat, lon)
        if rev:
            rev.lat, rev.lon, rev.precision = lat, lon, "coordinates"
            return rev
    except Exception:
        pass
    return GeoResult(
        display_name=f"{lat:.6f}, {lon:.6f}", lat=lat, lon=lon,
        address={}, source_url="https://www.openstreetmap.org/", precision="coordinates"
    )


def _street_variants(street: str) -> list[str]:
    s = re.sub(r"\s+", " ", street.strip())
    variants = [s]
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
    no_prefix = STREET_RE.sub("", s).strip()
    if no_prefix:
        variants.append(no_prefix)
    out, seen = [], set()
    for v in variants:
        key = _norm(v)
        if key and key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _candidate_road(item: dict) -> str:
    a = item.get("address", {}) or {}
    return a.get("road") or a.get("pedestrian") or a.get("residential") or a.get("footway") or item.get("name") or ""


def _candidate_locality_text(item: dict) -> str:
    a = item.get("address", {}) or {}
    vals = [
        a.get("parish"), a.get("city_district"), a.get("suburb"), a.get("village"),
        a.get("town"), a.get("city"), a.get("municipality"), a.get("county"),
        a.get("state"), item.get("display_name"),
    ]
    return " ".join(str(x) for x in vals if x)


def _clean_context_part(part: str) -> str:
    p = POSTCODE_RE.sub("", part or "").strip(" ,")
    return p


def _parse_query(raw: str):
    parts = [_clean_context_part(p) for p in raw.split(",")]
    parts = [p for p in parts if p and _norm(p) not in COUNTRY_WORDS]
    is_street = bool(parts and STREET_RE.match(parts[0]))
    street = parts[0] if is_street else ""
    context = parts[1:] if is_street else parts
    # First locality after the street is the most specific user-supplied place.
    locality = context[0] if context else ""
    return street, locality, context


def _has_locality_match(item: dict, context: list[str]) -> bool:
    if not context:
        return True
    txt = _norm(_candidate_locality_text(item))
    # Require at least the most specific place term. Additional terms are
    # bonuses, not hard requirements, because OSM may omit district labels.
    return bool(_norm(context[0]) and _norm(context[0]) in txt)


def _street_score(item: dict, variants: list[str], context: list[str]) -> int:
    road = _norm(_candidate_road(item))
    display = _norm(item.get("display_name", ""))
    locality_ok = _has_locality_match(item, context)
    if not locality_ok:
        return -1000
    score = 0
    for idx, variant in enumerate(variants):
        vn = _norm(variant)
        name_only = re.sub(r"^(rua|avenida|av|travessa|tv|largo|praceta|estrada|alameda|rotunda|beco|caminho)\s+", "", vn).strip()
        if road == vn:
            score = max(score, 160 - idx)
        if name_only and re.sub(r"^(rua|avenida|av|travessa|tv|largo|praceta|estrada|alameda|rotunda|beco|caminho)\s+", "", road).strip() == name_only:
            score = max(score, 155 - idx)
        if name_only and name_only in road:
            score = max(score, 145 - idx)
        if vn and vn in display:
            score = max(score, 140 - idx)
        if name_only and name_only in display:
            score = max(score, 130 - idx)
    if score <= 0:
        return -1000
    score += 40
    for extra in context[1:]:
        if _norm(extra) and _norm(extra) in _norm(_candidate_locality_text(item)):
            score += 10
    typ = (item.get("addresstype") or item.get("type") or "").lower()
    if typ in {"road", "residential", "pedestrian", "street"}:
        score += 20
    return score


def _best_street_result(results: list[dict], variants: list[str], context: list[str]):
    if not results:
        return None
    scored = sorted(((_street_score(i, variants, context), i) for i in results), key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] >= 150 else None


def _best_locality_result(results: list[dict], locality: str):
    ln = _norm(locality)
    if not ln:
        return None
    valid = [i for i in results if ln in _norm(_candidate_locality_text(i))]
    if not valid:
        return None
    return sorted(valid, key=lambda i: float(i.get("importance", 0) or 0), reverse=True)[0]


def geocode_location(query: str) -> Optional[GeoResult]:
    """Geocodificação segura para Portugal.

    Regra principal: uma pesquisa de rua nunca pode ser transformada num ponto
    arbitrário de outra cidade. Se a rua não for validada dentro da localidade
    pedida, devolvemos apenas a localidade correta (precision='locality') ou
    None. O utilizador confirma então o ponto no mapa.
    """
    if not query or not query.strip():
        return None
    raw = " ".join(query.strip().split())

    coord = _coordinates_result(raw)
    if coord is not None:
        return coord

    street, locality, context = _parse_query(raw)

    if street and locality:
        variants = _street_variants(street)
        context_text = ", ".join(context)

        # Resolve the requested locality itself first. Crucially, 'Portugal'
        # and postcodes are not mistaken for the locality anymore.
        locality_candidates = []
        for q in [f"{context_text}, Portugal", f"{locality}, Portugal"]:
            try:
                locality_candidates.extend(_search(q, limit=10))
            except requests.RequestException:
                pass
        locality_result = _best_locality_result(locality_candidates, locality)

        viewbox = None
        if locality_result:
            bbox = locality_result.get("boundingbox") or []
            if len(bbox) == 4:
                south, north, west, east = bbox
                viewbox = f"{west},{north},{east},{south}"

        candidates = []
        for variant in variants:
            searches = [
                f"{variant}, {context_text}, Portugal",
                f"{variant}, {locality}, Portugal",
            ]
            for q in searches:
                try:
                    candidates.extend(_search(q, viewbox=viewbox, bounded=1 if viewbox else 0, limit=10))
                except requests.RequestException:
                    pass
            if viewbox:
                try:
                    candidates.extend(_search(variant, viewbox=viewbox, bounded=1, limit=10))
                except requests.RequestException:
                    pass

        best = _best_street_result(candidates, variants, context)
        if best:
            return _result(best, raw, precision="exact_street")

        # ArcGIS as a SECOND provider, but it must pass the same locality+street
        # validation. Never accept its first candidate blindly.
        arc_candidates = []
        for variant in variants:
            for q in [f"{variant}, {context_text}, Portugal", f"{variant}, {locality}, Portugal"]:
                try:
                    arc_candidates.extend(_arcgis_search(q, limit=10))
                except requests.RequestException:
                    pass
        best_arc = _best_street_result(arc_candidates, variants, context)
        if best_arc:
            return _result(best_arc, raw, precision="exact_street")

        # Controlled fallback: only the requested locality, never another city.
        if locality_result:
            return _result(locality_result, raw, precision="locality")
        try:
            arc_loc = _arcgis_search(f"{context_text}, Portugal", limit=10)
            arc_loc = [i for i in arc_loc if _has_locality_match(i, [locality])]
            if arc_loc:
                return _result(arc_loc[0], raw, precision="locality")
        except requests.RequestException:
            pass
        return None

    # Non-street search (city, parish, village): accept only a result matching
    # the user's place terms. This prevents unrelated fallback points.
    candidates = []
    for q in [raw, f"{raw}, Portugal" if "portugal" not in raw.lower() else raw]:
        try:
            candidates.extend(_search(q, limit=10))
        except requests.RequestException:
            pass
    raw_clean = POSTCODE_RE.sub("", raw).replace(", Portugal", "").replace(", portugal", "").strip(" ,")
    target = _norm(raw_clean.split(",")[0])
    valid = [i for i in candidates if target and target in _norm(_candidate_locality_text(i))]
    if valid:
        best = sorted(valid, key=lambda i: float(i.get("importance", 0) or 0), reverse=True)[0]
        return _result(best, raw, precision="locality")

    try:
        arc = _arcgis_search(raw, limit=10)
        valid = [i for i in arc if target and target in _norm(_candidate_locality_text(i))]
        if valid:
            return _result(valid[0], raw, precision="locality")
    except requests.RequestException:
        pass
    return None


def reverse_geocode(lat: float, lon: float) -> Optional[GeoResult]:
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1, "zoom": 18, "accept-language": "pt"},
            headers=HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        item = r.json()
        if item and item.get("lat"):
            # Keep the CLICKED point, not the provider's snapped coordinate.
            result = _result(item, precision="street")
            result.lat, result.lon = float(lat), float(lon)
            return result
    except (requests.RequestException, ValueError, TypeError):
        pass
    try:
        item = _arcgis_reverse(lat, lon)
        if item:
            result = _result(item, precision="street")
            result.lat, result.lon = float(lat), float(lon)
            return result
    except (requests.RequestException, ValueError, TypeError):
        pass
    return None


def inferred_fields(result: GeoResult) -> dict:
    a = result.address
    municipality = a.get("municipality") or a.get("city") or a.get("town") or a.get("county") or ""
    parish = a.get("parish") or a.get("city_district") or a.get("suburb") or a.get("village") or a.get("hamlet") or a.get("locality") or ""
    locality = a.get("neighbourhood") or a.get("suburb") or a.get("village") or a.get("hamlet") or a.get("locality") or a.get("town") or a.get("city") or parish or ""
    if not parish and locality and locality.strip().lower() != municipality.strip().lower():
        parish = locality
    road = a.get("road") or a.get("pedestrian") or a.get("residential") or ""
    postcode = a.get("postcode") or ""
    house_number = a.get("house_number") or ""
    concise = ", ".join([x for x in [f"{road} {house_number}".strip(), parish or locality, municipality] if x])
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
