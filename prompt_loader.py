from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_master_prompt() -> str:
    return (ROOT / "prompts" / "master_prompt.txt").read_text(encoding="utf-8")

def build_prompt(location: str, municipality: str = "", parish: str = "", locality: str = "", article: str = "", known_area: str = "", geo_lat=None, geo_lon=None, geo_display_name: str = "", has_documents: bool = False, parcel_polygon_coords=None) -> str:
    context = f"""
CONTEXTO DO ESTUDO ATUAL
Localização introduzida: {location or 'NÃO INDICADA'}
Município: {municipality or 'NÃO INDICADO'}
Freguesia: {parish or 'NÃO INDICADA'}
Localidade: {locality or 'NÃO INDICADA'}
Artigo matricial indicado: {article or 'NÃO INDICADO'}
Área indicada pelo utilizador: {known_area or 'NÃO INDICADA'}
Geocodificação auxiliar: {geo_display_name or 'NÃO DISPONÍVEL'}
Coordenadas auxiliares: {f'{geo_lat:.6f}, {geo_lon:.6f}' if geo_lat is not None and geo_lon is not None else 'NÃO DISPONÍVEIS'}
Documentos anexados: {'SIM' if has_documents else 'NÃO'}
Perímetro desenhado no mapa: {parcel_polygon_coords if parcel_polygon_coords else 'NÃO DESENHADO'}

O ponto/geocodificação e o perímetro desenhado são apenas auxiliares espaciais; não substituem cadastro, levantamento ou área jurídica.
Os documentos anexados têm prioridade para identificar o processo e a proposta.
"""
    return load_master_prompt().rstrip() + "\n\n" + context.strip() + "\n"
