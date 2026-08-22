from __future__ import annotations
import json
import base64
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium

from core.config import APP_USER, APP_PASSWORD, GEMINI_API_KEY, GEMINI_MODEL
from core.gemini_service import GeminiService
from core.geocode import geocode_location
from core.utils import polygon_area_m2, stable_id
from core.calculations import calculate_capacity
from core.reporting import build_pdf

st.set_page_config(page_title="doisarquitectos | Viabilidade", page_icon=str(Path(__file__).parent / "assets" / "icon_logo.png"), layout="wide")

CSS = """
<style>
:root { --ink:#20252b; --muted:#66737a; --accent:#91b7bf; --panel:#f5f8f9; }
.block-container { padding-top: 1.15rem; max-width: 1500px; }
[data-testid="stImage"] img { object-fit: contain !important; }
.da-brand {display:flex;align-items:center;gap:28px;margin:6px 0 22px 0;overflow:visible!important;min-height:92px;}
.da-brand-logo {flex:0 0 195px;display:flex;align-items:center;justify-content:flex-start;overflow:visible!important;}
.da-brand-logo img {width:195px;height:auto;max-height:82px;object-fit:contain;display:block;overflow:visible!important;}
.da-brand-copy {flex:1;min-width:0;overflow:visible!important;padding:8px 0 10px 0;}
.da-brand-title {font-family:Arial,Helvetica,sans-serif;font-size:2.48rem;font-weight:800;line-height:1.24!important;color:var(--ink);margin:0!important;padding:4px 0 3px 0!important;overflow:visible!important;white-space:normal;}
.da-brand-sub {font-size:1rem;line-height:1.55;color:var(--muted);margin:0;padding:0 0 2px 0;overflow:visible!important;}
.da-login {max-width:560px;margin:2.3rem auto 0 auto;text-align:center;overflow:visible!important;}
.da-login-logo {display:block;width:min(420px,90%);height:auto;max-height:150px;object-fit:contain;margin:0 auto 20px auto;overflow:visible!important;}
.da-login-title {font-family:Arial,Helvetica,sans-serif;font-size:1.95rem;font-weight:800;line-height:1.28!important;margin:0 0 8px 0!important;padding:5px 0!important;overflow:visible!important;color:var(--ink);}
.da-login-sub {font-size:.98rem;color:var(--muted);line-height:1.5;margin-bottom:18px;}
.step {padding:11px 14px;border-radius:10px;background:var(--panel);border:1px solid #dbe6e9;margin-bottom:7px;}
.small-note {font-size:.82rem;color:#68777d;}
.source-box {background:#f7fafb;border-left:4px solid #91b7bf;padding:10px 12px;margin:5px 0;border-radius:4px;}
.status-pill{display:inline-block;padding:4px 9px;border-radius:999px;background:#eef5f6;color:#35515b;font-size:.78rem;border:1px solid #d7e5e8}
.muted-card{background:#f7fafb;border:1px solid #e2eaec;border-radius:12px;padding:12px 14px}
[data-testid="stHeadingWithActionElements"], [data-testid="stHeadingWithActionElements"] * {overflow:visible!important;}
[data-testid="stHeadingWithActionElements"] h1, [data-testid="stHeadingWithActionElements"] h2, [data-testid="stHeadingWithActionElements"] h3 {line-height:1.32!important;padding-top:.18rem!important;padding-bottom:.14rem!important;}
@media (max-width:900px){.da-brand{gap:16px;align-items:flex-start;}.da-brand-logo{flex-basis:145px}.da-brand-logo img{width:145px}.da-brand-title{font-size:1.85rem}.da-brand-sub{font-size:.9rem}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"

def _image_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")

def show_brand(compact: bool = False):
    logo_uri = _image_data_uri(LOGO_PATH)
    logo_html = f'<img src="{logo_uri}" alt="doisarquitectos">' if logo_uri else ''
    st.markdown(f"""<div class="da-brand">
      <div class="da-brand-logo">{logo_html}</div>
      <div class="da-brand-copy">
        <div class="da-brand-title">Estudo Inteligente de Viabilidade</div>
        <div class="da-brand-sub">Da localização às regras urbanísticas, condicionantes e cenários preliminares.</div>
      </div>
    </div>""", unsafe_allow_html=True)



def _area_candidates(document_analysis):
    """Normaliza áreas extraídas pela IA sem assumir que uma delas é a correta."""
    out = []
    combined = (document_analysis or {}).get("combined", {}) if isinstance(document_analysis, dict) else {}
    raw = combined.get("parcel_area_candidates_m2", []) or []
    for item in raw:
        value = None
        source = "Documento fornecido"
        detail = ""
        if isinstance(item, (int, float)):
            value = float(item)
        elif isinstance(item, str):
            import re
            m = re.search(r"([0-9][0-9\s.,]*)", item)
            if m:
                try: value = float(m.group(1).replace(" ", "").replace(".", "").replace(",", "."))
                except Exception: pass
            detail = item
        elif isinstance(item, dict):
            for key in ["value", "area_m2", "area", "m2"]:
                if isinstance(item.get(key), (int, float)):
                    value = float(item[key]); break
            source = str(item.get("source") or item.get("filename") or item.get("origin") or source)
            detail = str(item.get("basis") or item.get("note") or item.get("label") or "")
        if value and value > 0:
            if not any(abs(x["value"] - value) < 0.01 for x in out):
                out.append({"value": value, "source": source, "detail": detail})
    # Complementa com áreas explicitamente presentes no bloco parcel de cada documento.
    for doc in ((document_analysis or {}).get("documents", []) if isinstance(document_analysis, dict) else []):
        parcel = doc.get("parcel") or {}
        if isinstance(parcel, dict):
            for key, val in parcel.items():
                if "area" not in str(key).lower():
                    continue
                vals = val if isinstance(val, list) else [val]
                for v in vals:
                    num = None
                    detail = str(key).replace("_", " ")
                    if isinstance(v, (int, float)):
                        num = float(v)
                    elif isinstance(v, dict):
                        for kk in ["value", "value_m2", "area_m2", "area", "m2"]:
                            if isinstance(v.get(kk), (int, float)):
                                num = float(v[kk]); break
                        detail = str(v.get("basis") or v.get("note") or detail)
                    elif isinstance(v, str):
                        import re
                        m = re.search(r"([0-9]{3,}(?:[\s.,][0-9]+)*)", v)
                        if m:
                            txt=m.group(1).replace(" ", "")
                            try:
                                num=float(txt.replace(".", "").replace(",", "."))
                            except Exception:
                                pass
                            detail = v
                    if num and num > 0 and not any(abs(x["value"]-num)<0.01 for x in out):
                        out.append({"value":num,"source":doc.get("filename") or "Documento fornecido","detail":detail})
    return out

def _rules_valid(rules):
    if not isinstance(rules, dict) or not rules:
        return False
    if rules.get("parse_error") or rules.get("raw_text"):
        return False
    planning = rules.get("planning") or {}
    if not (planning.get("instrument") or (rules.get("identification") or {}).get("municipality")):
        return False
    # Uma matriz não é considerada concluída se for apenas um esqueleto sem qualquer fundamento
    # ou valor regulamentar. Isto evita o falso “✅ concluído” observado nos testes.
    refs = list(planning.get("sources") or [])
    refs += list((rules.get("identification") or {}).get("sources") or [])
    numeric = False
    for v in (rules.get("parameters") or {}).values():
        if isinstance(v, dict):
            if v.get("sources"): refs += list(v.get("sources") or [])
            if v.get("value") not in (None, "", "None"): numeric = True
    return bool(refs or numeric)

def _human_document_details(doc):
    lines = []
    loc = doc.get("location") or {}
    parcel = doc.get("parcel") or {}
    planning = doc.get("planning") or {}
    topo = doc.get("topography") or {}
    if loc:
        vals = [str(v) for v in loc.values() if v not in (None, "", [], {})]
        if vals: lines.append("Localização: " + " · ".join(vals[:4]))
    if parcel:
        vals = []
        for k,v in parcel.items():
            if v not in (None, "", [], {}): vals.append(f"{k.replace('_',' ')}: {v}")
        if vals: lines.append("Terreno: " + " · ".join(vals[:5]))
    if planning:
        vals = [f"{k.replace('_',' ')}: {v}" for k,v in planning.items() if v not in (None, "", [], {})]
        if vals: lines.append("Planeamento: " + " · ".join(vals[:4]))
    if topo:
        vals = [f"{k.replace('_',' ')}: {v}" for k,v in topo.items() if v not in (None, "", [], {})]
        if vals: lines.append("Topografia: " + " · ".join(vals[:4]))
    if doc.get("constraints"):
        lines.append("Condicionantes identificadas: " + " · ".join(map(str, doc.get("constraints")[:6])))
    return lines


PARAM_LABELS = {
    "utilization_index": "Índice de utilização / edificabilidade",
    "occupation_index": "Índice de ocupação / implantação",
    "impermeability_index": "Índice / percentagem de impermeabilização",
    "max_height_m": "Altura / cércea máxima",
    "max_floors_above_ground": "Pisos máximos acima do solo",
    "max_floors_below_ground": "Pisos máximos abaixo do solo",
    "front_setback_m": "Afastamento frontal",
    "side_setback_m": "Afastamento lateral",
    "rear_setback_m": "Afastamento posterior",
    "parking_rule": "Regra de estacionamento",
}

def _infer_parish_from_query(query: str, municipality: str = "") -> str:
    parts = [x.strip() for x in (query or "").split(",") if x.strip()]
    if len(parts) >= 3:
        candidate = parts[-2]
        if candidate and candidate.lower() != (municipality or "").lower() and not any(ch.isdigit() for ch in candidate):
            return candidate
    return ""

def _refs_text(value) -> str:
    if not value:
        return ""
    vals = value if isinstance(value, list) else [value]
    out=[]
    for v in vals:
        if isinstance(v, dict):
            v = v.get("label") or v.get("ref") or v.get("url")
        if isinstance(v, int): v=f"[{v}]"
        txt=str(v)
        if txt.isdigit(): txt=f"[{txt}]"
        if txt and txt not in out: out.append(txt)
    return " ".join(out)

def _parameter_coverage(rules: dict):
    params=(rules or {}).get("parameters",{}) or {}
    keys=list(PARAM_LABELS)
    confirmed=0
    numeric=0
    for k in keys:
        v=params.get(k) or {}
        status=str(v.get("status") or "").lower() if isinstance(v,dict) else ""
        val=v.get("value") if isinstance(v,dict) else None
        if status in ("confirmado","calculado","confirmado_utilizador"):
            confirmed += 1
        if val not in (None, "", "None"):
            numeric += 1
    return confirmed, numeric, len(keys)

def _calc_inputs(rules: dict):
    ci=(rules or {}).get("calculation_inputs",{}) or {}
    return {k:ci.get(k) for k in ["utilization_index","occupation_index","impermeability_index","max_height_m","max_floors"]}

def login():
    if st.session_state.get("authenticated"):
        return True
    logo_uri = _image_data_uri(LOGO_PATH)
    logo_html = f'<img class="da-login-logo" src="{logo_uri}" alt="doisarquitectos">' if logo_uri else ''
    c1,c2,c3 = st.columns([1,1.35,1])
    with c2:
        st.markdown(f"""<div class="da-login">{logo_html}
          <div class="da-login-title">Estudo Inteligente de Viabilidade</div>
          <div class="da-login-sub">Análise preliminar territorial e urbanística assistida por IA</div>
        </div>""", unsafe_allow_html=True)
        with st.form("login"):
            user = st.text_input("Utilizador", value="admin1")
            pwd = st.text_input("Password", type="password")
            ok = st.form_submit_button("Entrar", use_container_width=True)
        if ok:
            if user == APP_USER and pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Credenciais inválidas.")
        st.caption("Credenciais configuráveis em Streamlit Secrets. Altere a password antes de uso real.")
    return False

if not login():
    st.stop()

if "study" not in st.session_state:
    st.session_state.study = {
        "study_ref":"", "client_name":"", "location_text":"", "municipality":"", "parish":"", "district":"",
        "lat":39.65, "lon":-8.00, "polygon_geojson":None, "estimated_area_m2":None,
        "last_geocoded_query":"", "geocode_display_name":"", "geocode_source":"", "geocode_ok":False,
        "objective":"Determinar o melhor aproveitamento admissível",
        "priority":"Equilíbrio entre aproveitamento e risco",
        "documentation_skipped":False, "confirmed_area_m2":None, "confirmed_area_source":"",
        "documents_analysis":{}, "web_research":{}, "rules":{}, "calculations":{}, "scenarios":[]
    }
study = st.session_state.study

with st.sidebar:
    st.markdown("### Estudo")
    labels = [
        ("1", "Localização", bool(study.get("location_text") or study.get("polygon_geojson"))),
        ("2", "Documentação", bool(study.get("documents_analysis") or study.get("documentation_skipped"))),
        ("3", "Pesquisa territorial", _rules_valid(study.get("rules"))),
        ("4", "Regras do jogo", bool(study.get("rules"))),
        ("5", "Cálculos", bool(study.get("calculations"))),
        ("6", "Cenários", bool(study.get("scenarios"))),
        ("7", "Relatório", bool(study.get("rules"))),
    ]
    for n, name, done in labels:
        st.markdown(f"<div class='step'>{'✅' if done else '○'} <b>{n}. {name}</b></div>", unsafe_allow_html=True)
    st.divider()
    page = st.radio("Navegação", ["1 · Localização", "2 · Documentação", "3 · Pesquisa IA", "4 · Regras e condicionantes", "5 · Cálculos", "6 · Cenários", "7 · Relatório"], label_visibility="collapsed")
    st.caption(f"IA principal: {GEMINI_MODEL} · V2.6")
    if st.button("↺ Novo estudo / limpar dados", use_container_width=True):
        for key in ["study", "quick_docs", "all_docs"]:
            st.session_state.pop(key, None)
        st.rerun()
    if not GEMINI_API_KEY:
        st.warning("API Gemini não configurada.")

show_brand()

if page.startswith("1"):
    st.subheader("1. Localização e identificação rápida")
    st.write("O estudo pode começar apenas com uma localização aproximada. Se o cliente trouxer uma planta, documento do SIG, caderneta, levantamento ou outro PDF, pode anexá-lo já nesta etapa ou na etapa seguinte.")
    c1,c2,c3 = st.columns([1.1,1,1])
    with c1:
        study["client_name"] = st.text_input("Cliente / potencial cliente", value=study.get("client_name", ""), placeholder="Opcional")
    with c2:
        loc = st.text_input("Morada / lugar / referência", value=study.get("location_text", ""), placeholder="Ex.: Alameda Silva Rocha, Aveiro")
        study["location_text"] = loc
    with c3:
        if st.button("🔎 Localizar", use_container_width=True):
            # Uma nova morada nunca pode herdar o polígono/área do estudo anterior.
            if loc.strip() != (study.get("last_geocoded_query") or "").strip():
                study["polygon_geojson"] = None
                study["estimated_area_m2"] = None
                study["documents_analysis"] = {}
                study["documentation_skipped"] = False
                study["confirmed_area_m2"] = None
                study["confirmed_area_source"] = ""
                study["web_research"] = {}
                study["rules"] = {}
                study["calculations"] = {}
                study["scenarios"] = []
            try:
                results = geocode_location(loc)
                if results:
                    r = results[0]
                    study["lat"], study["lon"] = float(r["lat"]), float(r["lon"])
                    ad = r.get("address", {})
                    study["municipality"] = ad.get("municipality") or ad.get("city") or ad.get("town") or ""
                    study["parish"] = (ad.get("suburb") or ad.get("village") or ad.get("city_district") or ad.get("neighbourhood") or ad.get("quarter") or "")
                    if not study["parish"]:
                        study["parish"] = _infer_parish_from_query(loc, study["municipality"])
                    study["district"] = ad.get("state") or ""
                    study["last_geocoded_query"] = loc.strip()
                    study["geocode_display_name"] = r.get("display_name", loc)
                    study["geocode_source"] = r.get("source", "geocodificador")
                    study["geocode_ok"] = True
                    st.success(f"Localização encontrada: {study['geocode_display_name']}")
                else:
                    study["geocode_ok"] = False
                    study["lat"], study["lon"] = 39.65, -8.00
                    study["municipality"], study["parish"], study["district"] = "", "", ""
                    st.warning("Não foi possível localizar automaticamente esta referência. Tente acrescentar código postal/concelho ou indique o ponto no mapa.")
            except Exception as e:
                study["geocode_ok"] = False
                study["lat"], study["lon"] = 39.65, -8.00
                st.warning(f"Pesquisa de morada temporariamente indisponível: {e}")

    if study.get("geocode_ok"):
        st.caption(f"Fonte da localização: {study.get('geocode_source','')} · {study.get('geocode_display_name','')}")

    m = folium.Map(location=[study.get("lat",39.65), study.get("lon",-8.00)], zoom_start=17 if study.get("geocode_ok") else 7, control_scale=True, tiles="OpenStreetMap")
    if study.get("geocode_ok"):
        folium.Marker([study["lat"], study["lon"]], tooltip="Localização encontrada", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)
    Draw(export=False, draw_options={"polyline":False,"rectangle":True,"circle":False,"circlemarker":False,"marker":True,"polygon":True}, edit_options={"edit":True,"remove":True}).add_to(m)
    map_data = st_folium(m, height=520, use_container_width=True, returned_objects=["all_drawings","last_clicked"])
    drawings = (map_data or {}).get("all_drawings") or []
    polygons = [d for d in drawings if d.get("geometry",{}).get("type") in ("Polygon","Rectangle")]
    if polygons:
        poly = polygons[-1]
        study["polygon_geojson"] = poly
        coords = poly["geometry"]["coordinates"][0]
        latlon = [(c[1], c[0]) for c in coords[:-1] if len(c)>=2]
        area = polygon_area_m2(latlon)
        study["estimated_area_m2"] = round(area,1) if area else None
        if area:
            st.info(f"Área cartográfica aproximada: **{area:,.1f} m²**. Este valor é indicativo e deve ser substituído/confirmado por levantamento ou documento predial quando disponível.")

    c_mun, c_par, c_dis = st.columns(3)
    with c_mun:
        study["municipality"] = st.text_input("Município (confirmar/corrigir)", value=study.get("municipality", ""))
    with c_par:
        study["parish"] = st.text_input("Freguesia (confirmar/corrigir)", value=study.get("parish", ""))
    with c_dis:
        study["district"] = st.text_input("Distrito (opcional)", value=study.get("district", ""))

    study["study_ref"] = study.get("study_ref") or stable_id((study.get("location_text") or "novo") + str(datetime.now().date()))
    st.markdown("#### Documento rápido do cliente — opcional")
    quick = st.file_uploader("Pode anexar aqui a planta/SIG/levantamento/caderneta/PIP que o cliente trouxe. Será analisado juntamente com os restantes ficheiros.", type=["pdf","png","jpg","jpeg"], accept_multiple_files=True, key="quick_docs")
    if quick:
        st.session_state.quick_docs = quick
        st.success(f"{len(quick)} ficheiro(s) guardados para análise na etapa 2.")

elif page.startswith("2"):
    st.subheader("2. Documentação disponível — opcional")
    st.write("Pode avançar sem documentos. Se existirem, a IA usa-os para aumentar a precisão; se não existirem, a análise continua a partir da localização/polígono e das fontes oficiais pesquisadas automaticamente.")
    docs = st.file_uploader("Arraste quaisquer documentos disponíveis", type=["pdf","png","jpg","jpeg"], accept_multiple_files=True, key="all_docs")
    quick = st.session_state.get("quick_docs", [])
    all_docs = list(quick) + list(docs or [])
    if all_docs:
        study["documentation_skipped"] = False
        df = pd.DataFrame([{"Ficheiro":f.name,"Tipo":getattr(f,"type",""),"Tamanho (MB)":round(len(f.getvalue())/1024/1024,2)} for f in all_docs])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("##### O classificador procura, entre outros:")
        st.caption("Levantamento topográfico · planta de localização/cartografia · plantas SIG · PDM ordenamento · PDM condicionantes · REN · RAN · incêndio · ruído · recursos hídricos · património · servidões · cadastro · caderneta · certidão · PIP · parecer/despacho · alvará/loteamento · PU/PP · estudo/projeto existente.")
        if st.button("🧠 Analisar e classificar documentação", type="primary"):
            status = st.status("A analisar documentação com IA…", expanded=True)
            try:
                status.write("Leitura dos PDFs/imagens e classificação técnica.")
                svc = GeminiService()
                study["documents_analysis"] = svc.analyze_documents(all_docs)
                used = study["documents_analysis"].get("_model_used", "") if isinstance(study["documents_analysis"], dict) else ""
                status.update(label=f"Análise documental concluída{f' · {used}' if used else ''}", state="complete", expanded=False)
                st.success("Documentação analisada. Confirme os dados extraídos antes de prosseguir.")
            except Exception as e:
                status.update(label="Não foi possível concluir a análise agora", state="error", expanded=True)
                st.error(str(e))
    else:
        st.info("Não recebeu documentação? Pode continuar. A Etapa 3 pesquisará PDM, IGT, condicionantes e legislação com base na localização identificada.")
        can_skip = bool(study.get("location_text") or study.get("polygon_geojson") or study.get("municipality"))
        if st.button("Continuar sem documentação →", type="primary", disabled=not can_skip):
            study["documentation_skipped"] = True
            study["documents_analysis"] = {}
            st.success("Etapa documental assinalada como opcional. Pode avançar para a Pesquisa Territorial.")
        if not can_skip:
            st.caption("Identifique primeiro o terreno na Etapa 1.")

    if study.get("documents_analysis"):
        data = study["documents_analysis"]
        rows = []
        for d in data.get("documents",[]):
            rows.append({"Ficheiro":d.get("filename"),"Tipo identificado":d.get("document_type"),"Importância":d.get("importance"),"Confiança":d.get("confidence")})
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown("#### Informação técnica extraída")
        for d in data.get("documents", []):
            title = d.get("filename") or "Documento"
            dtype = (d.get("document_type") or "outro").replace("_", " ")
            conf = d.get("confidence")
            with st.expander(f"{title} · {dtype}"):
                st.write(f"**Importância:** {(d.get('importance') or 'complementar').replace('_',' ')}")
                if conf is not None: st.write(f"**Confiança da classificação:** {conf}")
                details = _human_document_details(d)
                if details:
                    for line in details: st.write("• " + line)
                else:
                    st.caption("Sem outros elementos suficientemente seguros para apresentação resumida.")
                if d.get("warnings"):
                    st.warning(" · ".join(map(str, d.get("warnings"))))
        candidates = _area_candidates(data)
        if candidates:
            st.markdown("#### Áreas identificadas nos documentos")
            for c in candidates:
                st.write(f"• **{c['value']:,.0f} m²** — {c['source']}{(' · '+c['detail']) if c['detail'] else ''}")
            if len(candidates) > 1:
                st.warning("Foram encontrados valores diferentes. A área será confirmada/editada pelo utilizador antes da pesquisa/cálculos.")

elif page.startswith("3"):
    st.subheader("3. Pesquisa territorial e regulamentar")
    st.write("A aplicação cruza a morada/rua, freguesia/localidade, município, coordenadas, polígono e, quando existam, os documentos analisados com fontes oficiais atuais.")

    st.markdown("#### Localização efetivamente pesquisada")
    c0,c1,c2 = st.columns([1.45,1,1])
    with c0:
        st.text_input("Rua / lugar / referência", value=study.get("location_text") or "", disabled=True)
    with c1:
        study["municipality"] = st.text_input("Município", value=study.get("municipality") or "")
    with c2:
        inferred_parish = study.get("parish") or _infer_parish_from_query(study.get("location_text",""), study.get("municipality",""))
        study["parish"] = st.text_input("Freguesia / localidade", value=inferred_parish, placeholder="Será resolvida automaticamente se possível")
    if study.get("lat") and study.get("lon"):
        st.caption(f"Coordenadas usadas na pesquisa: {study['lat']:.6f}, {study['lon']:.6f}")

    candidates = _area_candidates(study.get("documents_analysis",{}))
    if study.get("estimated_area_m2"):
        candidates.append({"value":float(study["estimated_area_m2"]),"source":"Polígono desenhado no mapa","detail":"área cartográfica aproximada"})
    unique=[]
    for c in candidates:
        if not any(abs(x["value"]-c["value"])<0.01 for x in unique): unique.append(c)
    candidates=unique

    st.markdown("#### Área do terreno")
    if candidates:
        if len(candidates)>1:
            st.warning("Foram identificadas áreas diferentes: " + " · ".join(f"{c['value']:,.0f} m² ({c['source']})" for c in candidates) + ". Escolha a referência correta ou edite manualmente.")
        options=[f"{c['value']:,.0f} m² — {c['source']}" for c in candidates]+["Introduzir/editar manualmente"]
        current=study.get("confirmed_area_source") or options[0]
        idx=options.index(current) if current in options else 0
        source_choice=st.selectbox("Referência de área",options,index=idx)
        chosen=candidates[options.index(source_choice)]["value"] if source_choice!="Introduzir/editar manualmente" else float(study.get("confirmed_area_m2") or candidates[0]["value"])
    else:
        st.info("Não foi encontrada uma área segura. Pode introduzi-la agora se a souber; a pesquisa territorial pode avançar mesmo sem área confirmada.")
        source_choice="Introduzir/editar manualmente"; chosen=float(study.get("confirmed_area_m2") or 0.0)
    area_input=st.number_input("Área do terreno a considerar (m²)",min_value=0.0,value=float(chosen),step=1.0)
    confirm_area=st.checkbox("Confirmo esta área para os cálculos",value=bool(study.get("confirmed_area_m2") and abs(float(study.get("confirmed_area_m2"))-area_input)<0.01))
    if confirm_area and area_input>0:
        study["confirmed_area_m2"]=float(area_input); study["confirmed_area_source"]=source_choice
        st.success(f"Área confirmada: {area_input:,.0f} m².")

    can_search=bool(study.get("location_text") or study.get("municipality") or study.get("polygon_geojson"))
    if st.button("🌐 Executar estudo urbanístico automático",type="primary",disabled=not can_search):
        study["rules"]={}; study["calculations"]={}; study["scenarios"]=[]
        status=st.status("A iniciar estudo urbanístico…",expanded=True)
        ctx={k:study.get(k) for k in ["study_ref","location_text","municipality","parish","district","lat","lon","polygon_geojson","estimated_area_m2","confirmed_area_m2","confirmed_area_source","objective","priority"]}
        try:
            status.write("1/3 · A confirmar localização administrativa e instrumento territorial aplicável.")
            svc=GeminiService()
            status.write("2/3 · A cruzar PDM/PP/PU, regras de edificabilidade e condicionantes com fontes oficiais.")
            result=svc.research_rules(ctx,study.get("documents_analysis",{}),force_deep=True)
            rules=result.get("rules") or {}
            if not rules or not (rules.get("planning") or {}).get("instrument"):
                raise RuntimeError("Não foi possível identificar um instrumento territorial aplicável com segurança.")
            study["rules"]=rules
            study["web_research"]={"citations":result.get("citations") or [],"queries":result.get("queries") or [],"model_used":result.get("model_used")}
            ident=rules.get("identification") or {}
            if ident.get("municipality"): study["municipality"]=ident["municipality"]
            if ident.get("parish"): study["parish"]=ident["parish"]
            status.write("3/3 · A calcular grau de confiança e preparar a ficha urbanística.")
            score=(rules.get("overall_readiness") or {}).get("score",0)
            status.update(label=f"Estudo territorial concluído · confiança técnica {score}%",state="complete",expanded=False)
            st.success("A ficha urbanística foi construída. Reveja a Etapa 4 antes de calcular capacidade.")
        except Exception as e:
            status.update(label="Não foi possível concluir automaticamente o estudo",state="error",expanded=True)
            st.error(str(e))
            st.info("A localização, área e documentos permanecem guardados. Não são geradas conclusões falsas quando faltam dados oficiais.")

    rules=study.get("rules") or {}
    if rules:
        ident=rules.get("identification") or {}; planning=rules.get("planning") or {}; viability=rules.get("viability") or {}; ready=rules.get("overall_readiness") or {}
        st.markdown("#### Resultado rápido")
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Município",ident.get("municipality") or study.get("municipality") or "A confirmar")
        c2.metric("Freguesia/localidade",ident.get("parish") or study.get("parish") or "A confirmar")
        c3.metric("Categoria",planning.get("subcategory") or planning.get("category") or "A confirmar")
        c4.metric("Confiança",f"{int(ready.get('score') or 0)}%")
        status_label=(viability.get("status") or "inconclusiva").replace("_"," ").title()
        st.info(f"**Viabilidade preliminar:** {status_label}. {viability.get('summary') or ''}")
        params=rules.get("parameters") or {}
        found=[]
        for k,label in PARAM_LABELS.items():
            v=params.get(k) or {}
            if v.get("value") not in (None,"","None") or v.get("value_text"):
                val=v.get("value") if v.get("value") not in (None,"","None") else v.get("value_text")
                found.append({"Regra":label,"Resultado":val,"Artigo":v.get("article") or "","Confiança":f"{int(v.get('confidence') or 0)}%","Ref.":_refs_text(v.get("sources"))})
        if found:
            st.dataframe(pd.DataFrame(found),use_container_width=True,hide_index=True)
        else:
            st.warning("O instrumento foi identificado, mas ainda não foi possível extrair parâmetros concretos. A Etapa 4 permite uma verificação aprofundada automática.")

elif page.startswith("4"):
    st.subheader("4. Regras do jogo e condicionantes")
    rules = study.get("rules") or {}
    if not rules:
        st.info("Execute primeiro a pesquisa territorial da Etapa 3.")
    else:
        confirmed, numeric, total = _parameter_coverage(rules)
        p = rules.get("planning",{}) or {}
        ident = rules.get("identification",{}) or {}
        refs = (study.get("web_research",{}) or {}).get("citations",[]) or []

        st.markdown("#### Identificação territorial")
        c1,c2,c3 = st.columns(3)
        c1.metric("Rua / local", ident.get("street_or_place") or study.get("location_text") or "A confirmar")
        c2.metric("Município", ident.get("municipality") or study.get("municipality") or "A confirmar")
        c3.metric("Freguesia / localidade", ident.get("parish") or study.get("parish") or "A confirmar")

        st.markdown("#### Enquadramento")
        instrument = p.get("instrument") or "A confirmar"
        classification = " / ".join(x for x in [p.get("soil_class"), p.get("category"), p.get("subcategory")] if x) or "A confirmar"
        st.write(f"**Instrumento:** {instrument} {_refs_text(p.get('sources'))}")
        st.write(f"**Classificação:** {classification}")
        st.write(f"**Estado:** {(p.get('status') or 'a_confirmar').replace('_',' ')}")
        if p.get("basis"):
            st.caption(str(p.get("basis")))

        ready=rules.get("overall_readiness") or {}
        cscore,cstat=st.columns([1,3])
        cscore.metric("Confiança técnica",f"{int(ready.get('score') or 0)}%")
        cstat.write(f"**Estado:** {(ready.get('label') or 'insuficiente').replace('_',' ').title()}")
        cstat.caption(ready.get("reason") or "")
        if numeric == 0:
            st.warning("O instrumento territorial foi identificado, mas faltam valores quantitativos confirmados. A aplicação pode fazer uma verificação aprofundada automática dos artigos/regulamentos antes de desistir.")
            if st.button("🔎 Aprofundar automaticamente parâmetros em falta",type="primary"):
                with st.spinner("A procurar os artigos e parâmetros concretos nas fontes oficiais…"):
                    try:
                        svc=GeminiService()
                        ctx={k:study.get(k) for k in ["location_text","municipality","parish","district","lat","lon","confirmed_area_m2","confirmed_area_source"]}
                        rr=svc.deepen_missing_parameters(ctx,rules)
                        newrules=rr.get("rules") or rules
                        # incorporar novas citações e renumerar
                        citations=list((study.get("web_research") or {}).get("citations") or [])
                        for src in rr.get("citations") or []:
                            if src.get("url") and not any(x.get("url")==src.get("url") for x in citations):
                                src=dict(src); src["ref"]=len(citations)+1; src["label"]=f"[{len(citations)+1}]"; citations.append(src)
                        study.setdefault("web_research",{})["citations"]=citations
                        study["rules"]=newrules; study["calculations"]={}; study["scenarios"]=[]
                        st.success("Verificação aprofundada concluída.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível aprofundar automaticamente agora: {e}")
        else:
            st.success(f"Foram encontrados valores em {numeric}/{total} parâmetros urbanísticos principais.")

        st.markdown("#### Usos admissíveis")
        uses=[]
        for u in rules.get("uses",[]) or []:
            uses.append({
                "Uso": u.get("use"),
                "Admissibilidade": (u.get("admissibility") or "a confirmar").replace("_"," "),
                "Fundamento": u.get("basis") or "",
                "Ref.": _refs_text(u.get("sources")),
            })
        if uses:
            st.dataframe(pd.DataFrame(uses), use_container_width=True, hide_index=True)
        else:
            st.info("Usos ainda não determinados.")

        st.markdown("#### Parâmetros urbanísticos")
        rows=[]
        for k in PARAM_LABELS:
            v=(rules.get("parameters",{}) or {}).get(k) or {}
            val=v.get("value"); txt=v.get("value_text") or ""
            unit=v.get("unit") or ""
            display=(f"{val} {unit}".strip() if val not in (None,"","None") else (txt or "A confirmar"))
            rows.append({
                "Parâmetro":PARAM_LABELS[k], "Valor / regra":display,
                "Estado":(v.get("status") or "a_confirmar").replace("_"," "),
                "Artigo":v.get("article") or "",
                "Confiança":f"{int(v.get('confidence') or 0)}%",
                "Fundamento":v.get("basis") or "", "Ref.":_refs_text(v.get("sources"))
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with st.expander("✏️ Revisão técnica — confirmar/corrigir parâmetros", expanded=False):
            st.caption("Use apenas quando o arquiteto dispõe de um valor confirmado em regulamento, parecer, PIP ou outra fonte técnica. As correções ficam marcadas como confirmação do utilizador.")
            params = rules.setdefault("parameters", {})
            fields = [
                ("utilization_index","Índice de utilização / edificabilidade",0.0,10.0,0.01),
                ("occupation_index","Índice de ocupação / implantação",0.0,100.0,0.01),
                ("impermeability_index","Impermeabilização",0.0,100.0,0.01),
                ("max_height_m","Altura / cércea máxima (m)",0.0,200.0,0.1),
                ("max_floors_above_ground","Pisos máximos acima do solo",0.0,50.0,1.0),
                ("max_floors_below_ground","Pisos máximos abaixo do solo",0.0,20.0,1.0),
                ("front_setback_m","Afastamento frontal (m)",0.0,100.0,0.1),
                ("side_setback_m","Afastamento lateral (m)",0.0,100.0,0.1),
                ("rear_setback_m","Afastamento posterior (m)",0.0,100.0,0.1),
            ]
            edited={}
            cols=st.columns(3)
            for i,(key,label,mn,mx,step) in enumerate(fields):
                current=(params.get(key) or {}).get("value")
                value=float(current) if isinstance(current,(int,float)) else 0.0
                with cols[i%3]:
                    edited[key]=st.number_input(label,min_value=mn,max_value=mx,value=value,step=step,key=f"edit_{key}")
            parking=st.text_input("Regra de estacionamento confirmada", value=str((params.get("parking_rule") or {}).get("value") or ""))
            basis=st.text_input("Fonte / artigo da correção (recomendado)", placeholder="Ex.: RPDM, art. 72.º, n.º 3")
            if st.button("Guardar confirmações técnicas"):
                for key,val in edited.items():
                    if val>0:
                        item=params.setdefault(key,{})
                        item.update({"value":val,"status":"confirmado_utilizador","basis":basis or item.get("basis","")})
                if parking.strip():
                    item=params.setdefault("parking_rule",{})
                    item.update({"value":parking.strip(),"status":"confirmado_utilizador","basis":basis or item.get("basis","")})
                ci=rules.setdefault("calculation_inputs",{})
                for src,dst in [("utilization_index","utilization_index"),("occupation_index","occupation_index"),("impermeability_index","impermeability_index"),("max_height_m","max_height_m"),("max_floors_above_ground","max_floors")]:
                    val=(params.get(src) or {}).get("value")
                    if val not in (None,""): ci[dst]=val
                study["rules"]=rules
                study["calculations"]={}
                study["scenarios"]=[]
                st.success("Parâmetros técnicos atualizados. Os cálculos seguintes usarão estes valores.")
                st.rerun()

        st.markdown("#### Condicionantes")
        cons=[]
        for c in rules.get("constraints",[]) or []:
            cons.append({"Condicionante":c.get("name"),"Estado":(c.get("status") or "a confirmar").replace("_"," "),"Impacto":c.get("impact") or "","Fundamento":c.get("basis") or "","Ref.":_refs_text(c.get("sources"))})
        if cons:
            st.dataframe(pd.DataFrame(cons), use_container_width=True, hide_index=True)
        else:
            st.info("Não existem condicionantes confirmadas na informação disponível.")

        if rules.get("conflicts"):
            st.error("Existem conflitos que devem ser resolvidos antes de confiar em cenários quantitativos.")
            for conflict in rules.get("conflicts", []):
                st.write("• " + (" · ".join(f"{k.replace('_',' ')}: {v}" for k,v in conflict.items() if v not in (None,"",[],{})) if isinstance(conflict,dict) else str(conflict)))
        if rules.get("critical_questions"):
            st.warning("**Pontos a confirmar**\n\n" + "\n".join(f"- {x}" for x in rules.get("critical_questions",[])))

        if refs:
            st.markdown("#### Fontes oficiais")
            for src in refs[:30]:
                st.markdown(f"**[{src.get('ref')}]** [{src.get('title') or src.get('url')}]({src.get('url')})")

elif page.startswith("5"):
    st.subheader("5. Cálculos de capacidade urbanística")
    rules = study.get("rules") or {}
    if not rules:
        st.info("Valide primeiro as regras e condicionantes na Etapa 4.")
    else:
        confirmed_area=float(study.get("confirmed_area_m2") or 0.0)
        st.write("Os cálculos são executados pelo motor matemático da aplicação. A IA apenas fornece parâmetros quando estes têm suporte regulamentar/documental.")
        c1,c2 = st.columns(2)
        c1.metric("Área confirmada", f"{confirmed_area:,.1f} m²" if confirmed_area else "A confirmar")
        numeric_inputs=_calc_inputs(rules)
        available={k:v for k,v in numeric_inputs.items() if v not in (None,"","None")}
        c2.metric("Parâmetros de cálculo disponíveis", f"{len(available)}/{len(numeric_inputs)}")

        if confirmed_area<=0:
            st.warning("Confirme a área do terreno na Etapa 3.")
        if not available:
            st.error("Ainda não existem parâmetros regulamentares quantitativos para calcular capacidade. Volte à Etapa 3 para aprofundar a pesquisa ou confirme/corrija parâmetros na Etapa 4 com base numa fonte técnica.")

        if available:
            inrows=[]
            labels={"utilization_index":"Índice de utilização","occupation_index":"Índice de ocupação","impermeability_index":"Impermeabilização","max_height_m":"Altura máxima","max_floors":"Pisos máximos"}
            for k,v in available.items(): inrows.append({"Entrada de cálculo":labels.get(k,k),"Valor":v})
            st.dataframe(pd.DataFrame(inrows), use_container_width=True, hide_index=True)

        if st.button("🧮 Executar cálculos determinísticos", type="primary", disabled=(confirmed_area<=0 or not available)):
            study["calculations"] = calculate_capacity(rules, confirmed_area)
            st.success("Cálculos concluídos.")

        calc=study.get("calculations") or {}
        derived=calc.get("derived",{}) or {}
        if derived:
            labels={
                "max_above_ground_gfa_by_utilization_m2":"ABC máxima pelo índice de utilização",
                "max_footprint_by_occupation_m2":"Área máxima de implantação",
                "max_impermeable_area_m2":"Área máxima impermeabilizada",
                "simple_volume_ceiling_m2":"Teto geométrico simples por pisos",
            }
            rows=[{"Indicador":labels.get(k,k.replace('_',' ')),"Resultado":f"{v:,.1f} m²" if isinstance(v,(int,float)) else v} for k,v in derived.items()]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            for note in calc.get("notes",[]) or []:
                st.caption(note)
        elif calc:
            st.warning("Não foi possível obter resultados derivados com os parâmetros atualmente confirmados.")

elif page.startswith("6"):
    st.subheader("6. Objetivo do cliente e cenários")
    study["objective"] = st.selectbox("Objetivo", [
        "Determinar o melhor aproveitamento admissível", "Maximizar potencial do terreno", "Habitação multifamiliar",
        "Habitação unifamiliar", "Habitação bifamiliar", "Moradias em banda", "Comércio", "Serviços", "Uso misto habitação + comércio/serviços", "Turismo", "Outro"
    ], index=0)
    study["priority"] = st.selectbox("Prioridade", ["Equilíbrio entre aproveitamento e risco","Máxima área construída","Maior número de frações","Menor risco urbanístico","Maior qualidade de espaços exteriores"])

    calc=study.get("calculations") or {}
    derived=calc.get("derived",{}) or {}
    if not derived:
        st.error("Ainda não existe base quantitativa suficiente para gerar cenários úteis. Complete a Etapa 5. A aplicação não irá apresentar cartões com valores vazios ou 'None'.")
    if st.button("🏗️ Gerar 3 cenários preliminares", type="primary", disabled=not bool(study.get("rules") and derived)):
        with st.spinner("A estruturar alternativas de aproveitamento..."):
            try:
                svc = GeminiService()
                study["scenarios"] = svc.generate_scenarios(study["objective"], study["priority"], study["rules"], study["calculations"])
            except Exception as e:
                st.error(f"Não foi possível gerar cenários agora: {e}")

    if study.get("scenarios"):
        cols = st.columns(3)
        for col,s in zip(cols, study["scenarios"][:3]):
            with col:
                st.markdown(f"### {s.get('code','')} · {s.get('name','')}")
                def val(v, suffix=""):
                    return "A confirmar" if v in (None,"","None") else f"{v}{suffix}"
                if s.get("above_ground_gfa_m2") is not None: st.metric("ABC acima do solo", val(s.get("above_ground_gfa_m2")," m²"))
                if s.get("implantation_m2") is not None: st.metric("Implantação", val(s.get("implantation_m2")," m²"))
                if s.get("floors_above_ground") is not None: st.write(f"**Pisos:** {val(s.get('floors_above_ground'))}")
                if s.get("indicative_units") is not None: st.write(f"**Fogos indicativos:** {val(s.get('indicative_units'))}")
                st.write(f"**Risco:** {s.get('risk','condicionado')}")
                st.write(s.get("concept", ""))
                if s.get("references"): st.caption("Referências: " + _refs_text(s.get("references")))
                if s.get("missing_inputs"): st.info("Falta confirmar: " + " · ".join(map(str,s.get("missing_inputs"))))
                if s.get("warnings"): st.warning(" · ".join(s["warnings"]))

elif page.startswith("7"):
    st.subheader("7. Relatório e exportação")
    if not study.get("rules"):
        st.info("Execute pelo menos a pesquisa territorial para gerar um relatório preliminar.")
    else:
        score=((study.get("rules") or {}).get("overall_readiness") or {}).get("score",0)
        if study.get("scenarios"):
            st.success(f"Relatório completo disponível · confiança técnica {score}%.")
        else:
            st.warning(f"Relatório preliminar disponível · confiança técnica {score}%. Os capítulos de cálculo/cenários indicarão explicitamente o que ainda falta confirmar.")
        pdf=build_pdf(dict(study))
        st.download_button("📄 Descarregar relatório PDF",data=pdf,file_name=f"{study.get('study_ref','ESTUDO')}_viabilidade.pdf",mime="application/pdf",use_container_width=True)
        st.caption("O PDF contém referências numeradas [1], [2], … e nunca inclui JSON técnico.")
        st.markdown("#### Fontes")
        for src in (study.get("web_research",{}) or {}).get("citations",[]):
            st.markdown(f"**[{src.get('ref')}]** [{src.get('title') or src.get('url')}]({src.get('url')})")

with st.sidebar:
    st.divider()
    if st.button("Sair"):
        st.session_state.authenticated = False
        st.rerun()
