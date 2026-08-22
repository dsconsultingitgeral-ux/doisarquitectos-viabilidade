SYNTHESIS_PROMPT = r'''
Com base no contexto do terreno, na análise documental e na investigação oficial, cria uma MATRIZ TÉCNICA de viabilidade preliminar.

CONTEXTO:
{study_context}

ANÁLISE DOCUMENTAL:
{document_context}

INVESTIGAÇÃO WEB OFICIAL:
{web_context}

DEVOLVE APENAS JSON VÁLIDO:
{
  "identification": {
    "municipality": "", "parish": "", "location": "", "area_m2": null,
    "area_source": "", "coordinate_system": "", "matrices": []
  },
  "planning": {
    "instrument": "", "version": "", "soil_class": "", "category": "", "subcategory": "",
    "status": "confirmado|interpretacao|a_confirmar|conflito",
    "sources": []
  },
  "uses": [
    {"use":"habitação multifamiliar", "admissibility":"sim|não|condicionado|a_confirmar", "basis":"", "sources":[]}
  ],
  "parameters": {
    "utilization_index": {"value": null, "unit":"", "status":"a_confirmar", "basis":"", "sources":[]},
    "occupation_index": {"value": null, "unit":"", "status":"a_confirmar", "basis":"", "sources":[]},
    "impermeability_index": {"value": null, "unit":"", "status":"a_confirmar", "basis":"", "sources":[]},
    "max_height_m": {"value": null, "status":"a_confirmar", "basis":"", "sources":[]},
    "max_floors_above_ground": {"value": null, "status":"a_confirmar", "basis":"", "sources":[]},
    "max_floors_below_ground": {"value": null, "status":"a_confirmar", "basis":"", "sources":[]},
    "front_setback_m": {"value": null, "status":"a_confirmar", "basis":"", "sources":[]},
    "side_setback_m": {"value": null, "status":"a_confirmar", "basis":"", "sources":[]},
    "rear_setback_m": {"value": null, "status":"a_confirmar", "basis":"", "sources":[]},
    "parking_rule": {"value": "", "status":"a_confirmar", "basis":"", "sources":[]}
  },
  "constraints": [
    {"name":"REN", "status":"nao_identificado|abrange|parcial|nao_abrange|a_confirmar", "impact":"", "basis":"", "sources":[]}
  ],
  "physical": {
    "min_elevation_m": null, "max_elevation_m": null, "elevation_range_m": null,
    "frontages": [], "existing_buildings": [], "infrastructure": [], "notes": []
  },
  "calculation_inputs": {
    "parcel_area_m2": null,
    "utilization_index": null,
    "occupation_index": null,
    "impermeability_index": null,
    "max_height_m": null,
    "max_floors": null
  },
  "critical_questions": [],
  "conflicts": [],
  "overall_readiness": {"score":0, "label":"insuficiente|condicionada|boa|muito_boa", "reason":""}
}

Não preenchas um valor numérico por estimativa quando a norma não está confirmada. Usa null.
'''
