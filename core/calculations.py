from __future__ import annotations
from .utils import numeric,pct_fraction

def calculate_capacity(area_m2, parameters):
    out={"area_m2":area_m2,"inputs":{},"results":{},"warnings":[]}
    def item(k): return parameters.get(k) or {}
    ui=numeric(item("utilization_index").get("numeric_value") or item("utilization_index").get("value"))
    ci=numeric(item("construction_index").get("numeric_value") or item("construction_index").get("value"))
    oi=pct_fraction(item("occupation_index").get("numeric_value") or item("occupation_index").get("value"))
    imp=pct_fraction(item("impermeability_index").get("numeric_value") or item("impermeability_index").get("value"))
    floors=numeric(item("max_floors_above_ground").get("numeric_value") or item("max_floors_above_ground").get("value"))
    index=ui if ui is not None else ci
    out["inputs"]={"utilization_or_construction_index":index,"occupation_index":oi,"impermeability_index":imp,"max_floors":floors}
    if area_m2 and oi is not None: out["results"]["max_footprint_m2"]=round(area_m2*oi,2)
    if area_m2 and imp is not None: out["results"]["max_impermeable_m2"]=round(area_m2*imp,2)
    if area_m2 and index is not None: out["results"]["max_gfa_by_index_m2"]=round(area_m2*index,2)
    if out["results"].get("max_footprint_m2") and floors:
        out["results"]["max_gfa_by_floors_m2"]=round(out["results"]["max_footprint_m2"]*floors,2)
    vals=[v for k,v in out["results"].items() if k.startswith("max_gfa_")]
    if vals: out["results"]["max_gfa_governing_m2"]=round(min(vals),2)
    if not out["results"]: out["warnings"].append("Ainda não existem parâmetros quantitativos confirmados/prováveis suficientes para calcular capacidade.")
    return out
