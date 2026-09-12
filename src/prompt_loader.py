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
    hard_final = r"""
============================================================
REGRAS FINAIS DE EXECUÇÃO — ÚLTIMA PRIORIDADE
============================================================
1. Avalia SEMPRE Habitação Multifamiliar na matriz de usos. Nunca a omitas.
2. Se a multifamiliar não estiver expressamente proibida por norma diretamente aplicável, não a elimines por simples prudência; considera-a no cenário de máximo potencial quando puder representar maior aproveitamento, assinalando PIP/validação quando necessário.
3. Se a área real da parcela não estiver comprovada, é PROIBIDO criar qualquer área hipotética/de referência para gerar m² absolutos. Usa somente fórmulas paramétricas.
4. Não inventes número de fogos. Se faltar base: A CONFIRMAR.
5. Os três cenários são sempre: A Conservador; B Equilibrado/Recomendado; C Máximo Potencial Tecnicamente Defensável.
6. Antes de concluir, verifica coerência entre matriz de usos, cenários e conclusão.
7. PARÂMETROS REGULAMENTARES NUMÉRICOS: para implantação, pisos, cércea/altura, índices e impermeabilização, devolve o MÁXIMO EXATO definido pela norma aplicável. É PROIBIDO transformar um máximo regulamentar num intervalo de prudência ou cenário. Ex.: se a norma fixa máximo 6 pisos, escreve "6 pisos", nunca "3 a 5" ou "4 a 6".
8. Só uses um intervalo num parâmetro regulamentar se o próprio artigo/norma aplicável definir explicitamente esse intervalo; identifica nesse caso a fonte concreta.
9. Se não encontrares artigo/fonte concreta que sustente um valor regulamentar, escreve A CONFIRMAR / NÃO DETERMINADO. Nunca preenchas por plausibilidade.
10. A decisão preliminar, a matriz final, os cenários e a conclusão devem repetir exatamente os mesmos máximos regulamentares. Não podem existir valores diferentes para implantação/pisos em secções distintas.
11. CARTOGRAFIA: setas, círculos, marcações, cores ou anotações acrescentadas pelo utilizador a uma planta NÃO fazem parte da legenda oficial e não podem ser interpretadas como classificação urbanística. Uma leitura visual de planta sem correspondência inequívoca com legenda/fonte georreferenciada deve ficar A VALIDAR.
12. HIERARQUIA DE EVIDÊNCIA: regulamento/artigo oficial > cartografia oficial georreferenciada > outros documentos oficiais > documento/planta fornecida > interpretação visual da IA. Uma fonte inferior não pode contrariar silenciosamente uma fonte superior.
13. Não confies numa pesquisa livre para "adivinhar" plantas PDM. Quando possível, procura recursos oficiais do município/DGT/SNIT e identifica exatamente o documento/camada consultado; quando não for possível confirmar, assinala A VALIDAR.
============================================================
"""
    return master.rstrip() + "\n\n" + context.strip() + "\n\n" + reliability.rstrip() + "\n\n" + addendum.rstrip() + "\n\n" + hard_final.strip() + "\n"
