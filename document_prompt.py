DOCUMENT_PROMPT = r'''
Analisa TODOS os ficheiros anexados como documentação potencial de um estudo preliminar de viabilidade urbanística.

CLASSIFICA CADA FICHEIRO numa das categorias (podes usar subtipo):
- levantamento_topografico
- planta_localizacao_cartografia
- plantas_municipais_sig
- pdm_ordenamento
- pdm_condicionantes
- ren
- ran
- risco_incendio
- ruido
- recursos_hidricos
- patrimonio
- servidao_infraestrutura
- cadastro_planta_predial
- caderneta_predial
- certidao_predial
- pip_informacao_previa
- parecer_despacho_municipal
- alvara_loteamento
- plano_urbanizacao
- plano_pormenor
- estudo_previo_existente
- projeto_arquitetura_existente
- fotografia_imagem
- documento_juridico_administrativo
- outro

IMPORTÂNCIA:
- base_critica: localização/limites, levantamento topográfico, plantas municipais/PDM relevantes.
- base_util: documento predial, cadastro, PIP, parecer, loteamento etc.
- referencia_output: estudo/projeto já produzido pelo gabinete.
- complementar.

PARA CADA PDF:
- identifica páginas relevantes e o que existe em cada uma;
- extrai texto e valores visíveis mesmo quando estão integrados em desenhos;
- assinala o que NÃO consegues ler com segurança;
- não confundas proposta arquitetónica com regra urbanística.

EXTRAÇÃO TRANSVERSAL:
- morada/local/lugar, freguesia, município, distrito se visível;
- coordenadas e sistema de coordenadas;
- área(s) do terreno e origem de cada área;
- artigo/matriz/referências prediais;
- limites, frentes e vias públicas;
- cotas e topografia;
- classificação/qualificação do solo apenas se explicitamente legível;
- condicionantes e cartas identificadas;
- instrumentos de gestão territorial mencionados e versão/data;
- usos/índices/alturas/afastamentos apenas se o documento os declarar;
- projeto existente: área de implantação, ABC, cave, impermeabilização, pisos, usos, fogos/tipologias, estacionamento.

DEVOLVE APENAS JSON VÁLIDO com esta estrutura:
{
  "documents": [
    {
      "filename": "...",
      "document_type": "...",
      "importance": "...",
      "pages": {"tipo_de_conteudo": [1,2]},
      "location": {},
      "parcel": {},
      "topography": {},
      "planning": {},
      "constraints": [],
      "existing_project": {},
      "warnings": [],
      "confidence": 0
    }
  ],
  "combined": {
    "location_candidates": [],
    "parcel_area_candidates_m2": [],
    "matrices_or_articles": [],
    "coordinate_systems": [],
    "planning_classification_candidates": [],
    "constraints_detected": [],
    "missing_or_uncertain": [],
    "conflicts": []
  }
}
'''
