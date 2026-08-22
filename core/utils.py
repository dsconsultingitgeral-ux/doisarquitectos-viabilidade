from __future__ import annotations
import hashlib, json, math, re
from typing import Any, Dict, Iterable, Optional


def stable_id(text: str, prefix="EST") -> str:
    digest = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:7].upper()
    return f"{prefix}-{digest}"


def safe_json_loads(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start:end+1]
    try:
        return json.loads(cleaned)
    except Exception:
        return {"raw_text": text, "parse_error": True}


def polygon_area_m2(latlon_points: Iterable) -> Optional[float]:
    pts = list(latlon_points or [])
    if len(pts) < 3:
        return None
    # Equirectangular local projection; adequate for a quick preliminary area estimate.
    lat0 = math.radians(sum(p[0] for p in pts) / len(pts))
    R = 6371008.8
    xy = [(R * math.radians(lon) * math.cos(lat0), R * math.radians(lat)) for lat, lon in pts]
    area = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i+1) % len(xy)]
        area += x1*y2 - x2*y1
    return abs(area) / 2.0


def get_nested(d: Dict[str, Any], path: str, default=None):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
