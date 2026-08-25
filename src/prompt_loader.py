from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_master_prompt() -> str:
    return (ROOT / "prompts" / "master_prompt.txt").read_text(encoding="utf-8")

def load_source_addendum() -> str:
    return (ROOT / "prompts" / "source_addendum.txt").read_text(encoding="utf-8")

def load_reliability_addendum() -> str:
    return (ROOT / "prompts" / "reliability_addendum.txt").read_text(encoding="utf-8")

def build_prompt(location: str, municipality: str = "", parish: str = "", locality: str = "", article: str = "", known_area: str = "", geo_lat=None, geo_lon=None, geo_display_name: str = "", has_documents: bool = False, parcel_polygon_coords=None) -> str:
    master = load_master_prompt()
    addendum = load_source_addendum()
    reliability = load_reliability_addendum()

    # O master prompt fica integral e inalterado. Este bloco só informa ao motor
    # os dados do estudo atual e prevalece sobre o exemplo de caso de estudo
    # existente no texto-base.
    context = f"""
============================================================
CONTEXTO DINÂMICO DO ESTUDO ATUAL — V4
============================================================

IMPORTANTE:
O texto do MASTER PROMPT contém um caso de estudo de referência.
Para esta execução, substitui APENAS os dados de localização/caso pelos valores abaixo.
Todas as restantes regras, fases, critérios e exigências do MASTER PROMPT mantêm-se integralmente.

Localização introduzida pelo utilizador: {location or "NÃO INDICADA"}
Município indicado pelo utilizador: {municipality or "NÃO INDICADO"}
Freguesia indicada pelo utilizador: {parish or "NÃO INDICADA"}
Localidade indicada pelo utilizador: {locality or "NÃO INDICADA"}
Artigo matricial indicado: {article or "NÃO INDICADO"}
Área conhecida/indicada: {known_area or "NÃO INDICADA"}
Geocodificação auxiliar: {geo_display_name or "NÃO DISPONÍVEL"}
Coordenadas auxiliares: {f"{geo_lat:.6f}, {geo_lon:.6f}" if geo_lat is not None and geo_lon is not None else "NÃO DISPONÍVEIS"}
Documentos específicos da parcela anexados: {"SIM" if has_documents else "NÃO"}
Perímetro aproximado desenhado pelo utilizador: {parcel_polygon_coords if parcel_polygon_coords else "NÃO DESENHADO"}

REGRA SOBRE O PERÍMETRO DESENHADO:
Se existirem coordenadas do perímetro desenhado, utiliza-as apenas como referência espacial para compreender a posição e a forma aproximada do terreno.
Não trates este desenho como limite cadastral, levantamento topográfico ou área jurídica confirmada.
Quando útil, usa-o para orientar a pesquisa territorial e a leitura das condicionantes, mantendo sempre a indicação de que é um perímetro aproximado.

REGRA ESPECIAL QUANDO NÃO EXISTIREM DOCUMENTOS:
Se não existirem documentos anexados, NÃO interrompas o estudo. Produz na mesma um ESTUDO PRELIMINAR DE LOCALIZAÇÃO E VIABILIDADE com base na localização fornecida, geocodificação apenas como ponto de partida e pesquisa externa obrigatória em fontes oficiais.
Nesse caso:
- declara explicitamente que os limites cadastrais, área jurídica, artigo matricial e geometria da parcela NÃO estão confirmados;
- não inventes área nem uses o ponto geocodificado para inferir limites;
- procura PDM, regulamento, ordenamento, condicionantes, REN, RAN, ruído, incêndio, património, recursos hídricos, servidões e instrumentos territoriais aplicáveis à zona;
- apresenta aquilo que pode ser determinado ao nível da localização/zona;
- marca como A CONFIRMAR tudo o que dependa do polígono exato da parcela;
- ainda assim produz uma conclusão útil e um relatório preliminar, indicando claramente quais documentos o utilizador deverá obter para elevar a confiança.

A informação contida nos documentos anexados tem prioridade para confirmar, corrigir ou colocar em conflito estes dados.
============================================================
"""
    return master.rstrip() + "\n\n" + context.strip() + "\n\n" + reliability.rstrip() + "\n\n" + addendum.rstrip() + "\n"
