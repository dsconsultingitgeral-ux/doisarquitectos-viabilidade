from __future__ import annotations
import requests

def geocode_location(query: str):
    q=(query or "").strip()
    if not q: return None
    variants=[q]
    if "portugal" not in q.lower(): variants.append(q+", Portugal")
    headers={"User-Agent":"doisarquitectos-viabilidade/3.0"}
    for v in variants:
        try:
            r=requests.get("https://nominatim.openstreetmap.org/search",params={"q":v,"format":"jsonv2","addressdetails":1,"limit":1,"countrycodes":"pt"},headers=headers,timeout=8)
            if r.ok and r.json():
                x=r.json()[0]; a=x.get("address") or {}
                parish=a.get("parish") or a.get("village") or a.get("town") or a.get("suburb") or a.get("city_district") or ""
                municipality=a.get("municipality") or a.get("city") or a.get("town") or a.get("county") or ""
                district=a.get("state_district") or a.get("state") or ""
                return {"lat":float(x["lat"]),"lon":float(x["lon"]),"display_name":x.get("display_name",v),"parish":parish,"municipality":municipality,"district":district,"raw":a}
        except Exception:
            continue
    return None
