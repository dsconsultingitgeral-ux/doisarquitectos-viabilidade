SYNTHESIS_PROMPT = r'''
Transforma os dados do terreno, documentos e pesquisa oficial numa MATRIZ TÉCNICA de viabilidade preliminar.

CONTEXTO:
{study_context}

ANÁLISE DOCUMENTAL:
{document_context}

INVESTIGAÇÃO WEB OFICIAL:
{web_context}

REGRAS FUNDAMENTAIS:
- Preserva a morada/rua indicada pelo utilizador.
- Resolve freguesia/localidade quando houver suporte documental ou oficial. Não deixes "a_confirmar" se a pesquisa já forneceu uma freguesia inequívoca.
- Nunca inventes números.
- Para cada regra/condicionante guarda referências no formato [1], [2] correspondentes às fontes em web_context.citations.
- Se a pesquisa online não sustentou um parâmetro, usa null e status a_confirmar.
- Um estudo com todos os parâmetros numéricos null NÃO pode ter score alto.
- O score deve refletir a quantidade de dados regulamentares efetivamente confirmados.

DEVOLVE APENAS JSON VÁLIDO:
{
  "identification": {
    "street_or_place": "", "municipality": "", "parish": "", "location": "", "area_m2": null,
    "area_source": "", "coordinate_system": "", "matrices": [], "sources": []
  },
  "planning": {
    "instrument": "", "version": "", "soil_class": "", "category": "", "subcategory": "",
    "status": "confirmado|interpretacao|a_confirmar|conflito", "basis": "", "sources": []
  },
  "uses": [
    {"use":"habitação multifamiliar", "admissibility":"sim|não|condicionado|a_confirmar", "basis":"", "sources":[]}
  ],
  "parameters": {
    "utilization_index": {"value": null, "unit":"", "status":"a_confirmar", "basis":"", "sources":[]},
    "occupation_index": {"value": null, "unit":"", "status":"a_confirmar", "basis":"", "sources":[]},
    "impermeability_index": {"value": null, "unit":"", "status":"a_confirmar", "basis":"", "sources":[]},
    "max_height_m": {"value": null, "unit":"m", "status":"a_confirmar", "basis":"", "sources":[]},
    "max_floors_above_ground": {"value": null, "unit":"pisos", "status":"a_confirmar", "basis":"", "sources":[]},
    "max_floors_below_ground": {"value": null, "unit":"pisos", "status":"a_confirmar", "basis":"", "sources":[]},
    "front_setback_m": {"value": null, "unit":"m", "status":"a_confirmar", "basis":"", "sources":[]},
    "side_setback_m": {"value": null, "unit":"m", "status":"a_confirmar", "basis":"", "sources":[]},
    "rear_setback_m": {"value": null, "unit":"m", "status":"a_confirmar", "basis":"", "sources":[]},
    "parking_rule": {"value": "", "unit":"", "status":"a_confirmar", "basis":"", "sources":[]}
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
'''
