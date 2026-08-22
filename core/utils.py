from __future__ import annotations
import json, math, re
from typing import Any

def safe_json_loads(text: str) -> Any:
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I|re.S).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = min([i for i in [text.find("{"), text.find("[")] if i >= 0] or [-1])
    if start < 0:
        return None
    for end in range(len(text), start, -1):
        chunk = text[start:end].strip()
        if not chunk.endswith(("}", "]")):
            continue
        try:
            return json.loads(chunk)
        except Exception:
            continue
    return None

def polygon_area_m2(coords):
    if not coords or len(coords) < 3:
        return None
    # equirectangular local approximation, adequate for preliminary map areas
    lat0 = sum(p[0] for p in coords) / len(coords)
    R = 6371008.8
    xy=[]
    for lat,lon in coords:
        x=math.radians(lon)*R*math.cos(math.radians(lat0))
        y=math.radians(lat)*R
        xy.append((x,y))
    area=0.0
    for i,(x1,y1) in enumerate(xy):
        x2,y2=xy[(i+1)%len(xy)]
        area += x1*y2-x2*y1
    return abs(area)/2

def numeric(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value,(int,float)):
        return float(value)
    s=str(value).strip().replace("%","")
    m=re.search(r"-?\d+(?:[.,]\d+)?", s)
    if not m: return None
    try: return float(m.group(0).replace(",","."))
    except Exception: return None

def pct_fraction(value):
    n=numeric(value)
    if n is None: return None
    return n/100.0 if n > 1.0 else n
