from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_master_prompt() -> str:
    return (ROOT / "prompts" / "master_prompt.txt").read_text(encoding="utf-8")

def load_source_addendum() -> str:
    return (ROOT / "prompts" / "source_addendum.txt").read_text(encoding="utf-8")

def build_prompt(location: str, municipality: str = "", parish: str = "", locality: str = "", article: str = "", known_area: str = "") -> str:
    master = load_master_prompt()
    addendum = load_source_addendum()

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

A informação contida nos documentos anexados tem prioridade para confirmar, corrigir ou colocar em conflito estes dados.
============================================================
"""
    return master.rstrip() + "\n\n" + context.strip() + "\n\n" + addendum.rstrip() + "\n"
