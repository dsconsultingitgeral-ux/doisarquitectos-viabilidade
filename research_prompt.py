DIRECT_RESEARCH_PROMPT = r'''
És um arquiteto urbanista sénior em Portugal. Tens de produzir uma MATRIZ URBANÍSTICA PRELIMINAR para UM TERRENO CONCRETO, não uma explicação genérica do PDM.

DADOS DO TERRENO:
{study_context}

DOCUMENTAÇÃO JÁ ANALISADA:
{document_context}

OBJETIVO
Determinar, com a maior precisão possível e usando prioritariamente fontes oficiais, o enquadramento territorial, os usos admissíveis, os parâmetros de edificabilidade e as condicionantes que incidem sobre este terreno.

REGRAS ABSOLUTAS
1. Usa SEMPRE a morada/rua, freguesia/localidade, município, coordenadas e polígono fornecidos como contexto espacial. Não pesquises apenas pelo município.
2. Se a morada contiver uma localidade/freguesia (ex.: "Rua dos Juncais, Sandim, Vila Nova de Gaia"), tenta confirmá-la e preserva-a.
3. Se a documentação contém Planta de Ordenamento / SIG / PDM, usa-a para identificar a classe/categoria/subcategoria da parcela. Cruza a marcação do terreno com a legenda. Se não for legível com segurança, indica explicitamente isso.
4. Depois de identificar a categoria/subcategoria, procura no REGULAMENTO EM VIGOR os artigos aplicáveis a essa categoria e extrai os valores/regas concretas.
5. Verifica se há PP, PU, loteamento, medidas preventivas ou outra figura mais específica que altere/complemente o PDM.
6. Não uses blogs, portais imobiliários ou diretórios como fundamento urbanístico. Para regras urbanísticas, privilegia Município/SIG, Diário da República, DGT/SNIT, CCDR, APA, ICNF, Património Cultural, IP e outras entidades públicas.
7. Nunca inventes números. Se um valor não for encontrado, usa null e explica o que falta.
8. Se uma regra for morfológica (ex.: cércea dominante/alinhamento) em vez de um número fixo, regista a regra textual em "value_text".
9. REN/RAN/linhas de água/incêndio/ruído/património/servidões: só declarar "não abrange" quando existir suporte claro. Caso contrário usa "a_confirmar".
10. Não calcules áreas de construção. Apenas extrai os parâmetros de entrada; os cálculos serão feitos em Python.
11. A área do terreno vem apenas do utilizador, polígono ou documentos. NUNCA inferir área por geocodificação.
12. Devolve somente JSON válido, sem markdown, sem comentários e sem código.

DEVOLVE ESTA ESTRUTURA:
{
  "identification": {
    "street_or_place": "",
    "municipality": "",
    "parish": "",
    "district": "",
    "lat": null,
    "lon": null,
    "area_m2": null,
    "area_source": "",
    "confidence": 0
  },
  "planning": {
    "instrument": "",
    "version": "",
    "specific_instrument": "",
    "soil_class": "",
    "category": "",
    "subcategory": "",
    "status": "confirmado|interpretacao|a_confirmar|conflito",
    "basis": "",
    "source_urls": [],
    "confidence": 0
  },
  "uses": [
    {"use":"habitação multifamiliar","admissibility":"sim|não|condicionado|a_confirmar","basis":"","article":"","source_urls":[],"confidence":0}
  ],
  "parameters": {
    "utilization_index": {"value":null,"value_text":"","unit":"","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "occupation_index": {"value":null,"value_text":"","unit":"","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "impermeability_index": {"value":null,"value_text":"","unit":"","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "max_height_m": {"value":null,"value_text":"","unit":"m","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "max_floors_above_ground": {"value":null,"value_text":"","unit":"pisos","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "max_floors_below_ground": {"value":null,"value_text":"","unit":"pisos","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "front_setback_m": {"value":null,"value_text":"","unit":"m","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "side_setback_m": {"value":null,"value_text":"","unit":"m","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "rear_setback_m": {"value":null,"value_text":"","unit":"m","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "parking_rule": {"value":null,"value_text":"","unit":"","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0}
  },
  "constraints": [
    {"name":"REN","status":"abrange|parcial|nao_abrange|a_confirmar","impact":"","basis":"","source_urls":[],"confidence":0}
  ],
  "critical_questions": [],
  "conflicts": [],
  "research_notes": [],
  "viability": {
    "status":"favoravel|favoravel_condicionada|inconclusiva|desfavoravel",
    "summary":"",
    "confidence":0
  }
}
'''

DEEP_PARAMETER_PROMPT = r'''
És um arquiteto urbanista sénior. Já foi feita uma primeira pesquisa de um terreno e faltam parâmetros urbanísticos concretos. Faz APENAS uma verificação aprofundada dos parâmetros em falta, usando fontes oficiais e o instrumento/categoria já identificados.

TERRENO E MATRIZ ATUAL:
{current_rules}

LOCALIZAÇÃO:
{study_context}

PROCURA ESPECIFICAMENTE:
- índice de utilização/edificabilidade;
- índice de ocupação/implantação;
- impermeabilização;
- altura/cércea;
- pisos acima/abaixo do solo;
- afastamentos/alinhamentos;
- estacionamento;
- qualquer regra especial do PP/PU/loteamento/medidas preventivas aplicável à parcela.

Se o regulamento definir a regra por morfologia, alinhamento ou ficha de parcela em vez de número fixo, devolve essa regra em value_text. Não inventes valores.

DEVOLVE APENAS JSON VÁLIDO:
{
  "parameters": {
    "utilization_index": {"value":null,"value_text":"","unit":"","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "occupation_index": {"value":null,"value_text":"","unit":"","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "impermeability_index": {"value":null,"value_text":"","unit":"","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "max_height_m": {"value":null,"value_text":"","unit":"m","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "max_floors_above_ground": {"value":null,"value_text":"","unit":"pisos","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "max_floors_below_ground": {"value":null,"value_text":"","unit":"pisos","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "front_setback_m": {"value":null,"value_text":"","unit":"m","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "side_setback_m": {"value":null,"value_text":"","unit":"m","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "rear_setback_m": {"value":null,"value_text":"","unit":"m","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0},
    "parking_rule": {"value":null,"value_text":"","unit":"","status":"confirmado|interpretacao|a_confirmar","article":"","basis":"","source_urls":[],"confidence":0}
  },
  "notes": []
}
'''
