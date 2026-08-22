from __future__ import annotations
from typing import Any, Dict, Optional


def _num(v):
    try:
        if isinstance(v, dict):
            v = v.get("value")
        return float(v) if v is not None else None
    except Exception:
        return None


def calculate_capacity(rules: Dict[str, Any], fallback_area_m2: Optional[float] = None) -> Dict[str, Any]:
    inputs = rules.get("calculation_inputs", {}) or {}
    area = fallback_area_m2 or _num(inputs.get("parcel_area_m2"))
    iu = _num(inputs.get("utilization_index"))
    io = _num(inputs.get("occupation_index"))
    ii = _num(inputs.get("impermeability_index"))
    floors = _num(inputs.get("max_floors"))
    h = _num(inputs.get("max_height_m"))

    out = {"inputs": {"parcel_area_m2": area, "utilization_index": iu, "occupation_index": io,
                      "impermeability_index": ii, "max_floors": floors, "max_height_m": h},
           "derived": {}, "notes": []}
    if area and iu is not None:
        out["derived"]["max_above_ground_gfa_by_utilization_m2"] = round(area * iu, 2)
    if area and io is not None:
        # Accept either fraction (0.4) or percent (40)
        ratio = io / 100 if io > 1 else io
        out["derived"]["max_footprint_by_occupation_m2"] = round(area * ratio, 2)
    if area and ii is not None:
        ratio = ii / 100 if ii > 1 else ii
        out["derived"]["max_impermeable_area_m2"] = round(area * ratio, 2)
    if area and floors and "max_footprint_by_occupation_m2" in out["derived"]:
        out["derived"]["simple_volume_ceiling_m2"] = round(out["derived"]["max_footprint_by_occupation_m2"] * floors, 2)
        out["notes"].append("Teto geométrico simples; não substitui índice de utilização, recuos, alinhamentos ou morfologia.")
    if not area:
        out["notes"].append("Área do terreno não confirmada: cálculos principais ficaram por executar.")
    return out
