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
    return any(k in rules for k in ["planning", "identification", "parameters", "constraints", "overall_readiness"])

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
        ("7", "Relatório", bool(study.get("rules") and study.get("scenarios"))),
    ]
    for n, name, done in labels:
        st.markdown(f"<div class='step'>{'✅' if done else '○'} <b>{n}. {name}</b></div>", unsafe_allow_html=True)
    st.divider()
    page = st.radio("Navegação", ["1 · Localização", "2 · Documentação", "3 · Pesquisa IA", "4 · Regras e condicionantes", "5 · Cálculos", "6 · Cenários", "7 · Relatório"], label_visibility="collapsed")
    st.caption(f"IA principal: {GEMINI_MODEL} · V2.4")
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
                    study["parish"] = ad.get("suburb") or ad.get("village") or ad.get("city_district") or ""
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
    st.write("A aplicação cruza a localização e, quando existam, os documentos analisados com fontes oficiais atuais. A documentação não é obrigatória.")
    c1,c2 = st.columns(2)
    c1.metric("Município", study.get("municipality") or "A confirmar")
    c2.metric("Freguesia", study.get("parish") or "A confirmar")

    candidates = _area_candidates(study.get("documents_analysis",{}))
    if study.get("estimated_area_m2"):
        candidates.append({"value":float(study["estimated_area_m2"]),"source":"Polígono desenhado no mapa","detail":"área cartográfica aproximada"})
    # remove duplicados
    unique=[]
    for c in candidates:
        if not any(abs(x["value"]-c["value"])<0.01 for x in unique): unique.append(c)
    candidates=unique

    st.markdown("#### Área do terreno")
    if candidates:
        if len(candidates) > 1:
            vals = " · ".join(f"{c['value']:,.0f} m² ({c['source']})" for c in candidates)
            st.warning("Foram identificadas áreas diferentes: " + vals + ". Escolha uma referência ou edite manualmente.")
        options = [f"{c['value']:,.0f} m² — {c['source']}" for c in candidates] + ["Introduzir/editar manualmente"]
        current_source = study.get("confirmed_area_source") or options[0]
        idx = options.index(current_source) if current_source in options else 0
        source_choice = st.selectbox("Referência de área", options, index=idx)
        if source_choice != "Introduzir/editar manualmente":
            chosen = candidates[options.index(source_choice)]["value"]
        else:
            chosen = float(study.get("confirmed_area_m2") or (candidates[0]["value"] if candidates else 0.0))
    else:
        st.info("Não foi encontrada uma área segura. Pode introduzi-la agora se a souber, ou continuar a pesquisa sem área confirmada.")
        source_choice = "Introduzir/editar manualmente"
        chosen = float(study.get("confirmed_area_m2") or 0.0)

    area_input = st.number_input("Área do terreno a considerar (m²)", min_value=0.0, value=float(chosen), step=1.0, help="Campo editável. A confirmação é necessária para os cálculos, mas não para pesquisar o PDM e condicionantes.")
    confirm_area = st.checkbox("Confirmo esta área para os cálculos", value=bool(study.get("confirmed_area_m2") and abs(float(study.get("confirmed_area_m2"))-area_input)<0.01))
    if confirm_area and area_input > 0:
        study["confirmed_area_m2"] = float(area_input)
        study["confirmed_area_source"] = source_choice
        st.success(f"Área confirmada: {area_input:,.0f} m².")
    elif area_input > 0:
        st.caption("Área preenchida mas ainda não confirmada para cálculos.")

    can_search = bool(study.get("municipality") or study.get("location_text") or study.get("polygon_geojson"))
    if st.button("🌐 Pesquisar e construir matriz urbanística", type="primary", disabled=not can_search):
        # Só uma nova matriz válida marca a etapa como concluída.
        study["rules"] = {}
        status = st.status("A preparar pesquisa territorial…", expanded=True)
        ctx = {k:study.get(k) for k in ["study_ref","location_text","municipality","parish","district","lat","lon","estimated_area_m2","confirmed_area_m2","confirmed_area_source","objective","priority"]}
        try:
            status.write("1/4 · A preparar contexto do terreno e documentos relevantes.")
            svc = GeminiService()
            status.write("2/4 · A procurar PDM/IGT e fontes oficiais prioritárias.")
            study["web_research"] = svc.web_research(ctx, study.get("documents_analysis",{}))
            status.write("3/4 · A recolher referências e fundamentos rastreáveis.")
            status.write("4/4 · A cruzar documentos + fontes e estruturar regras do jogo.")
            candidate_rules = svc.synthesize_rules(ctx, study.get("documents_analysis",{}), study.get("web_research",{}))
            if not _rules_valid(candidate_rules):
                raise RuntimeError("A síntese recebida não contém uma matriz urbanística válida.")
            study["rules"] = candidate_rules
            used = study["web_research"].get("model_used", "")
            status.update(label=f"Pesquisa e matriz concluídas{f' · {used}' if used else ''}", state="complete", expanded=False)
            st.success("Pesquisa concluída. A matriz urbanística está pronta para revisão na Etapa 4.")
        except Exception as e:
            status.update(label="Pesquisa online incompleta", state="error", expanded=True)
            study["web_research"] = study.get("web_research") or {"text":"", "citations":[], "queries":[], "error":str(e)}
            try:
                status.write("A tentar construir uma matriz provisória com a localização e documentação disponível.")
                svc2 = GeminiService()
                candidate_rules = svc2.synthesize_rules(ctx, study.get("documents_analysis",{}), study.get("web_research",{}))
                if _rules_valid(candidate_rules):
                    study["rules"] = candidate_rules
                    st.warning("Pesquisa online incompleta, mas foi criada uma matriz provisória. Parâmetros sem fonte confirmada ficam A CONFIRMAR.")
                else:
                    raise RuntimeError("Não foi possível estruturar uma matriz provisória válida.")
            except Exception as e2:
                study["rules"] = {}
                st.error(f"Não foi possível concluir a matriz urbanística: {e2}")
                st.info("Pode repetir apenas esta pesquisa mais tarde; a localização e a documentação permanecem guardadas.")

    wr = study.get("web_research") or {}
    if wr.get("text"):
        st.markdown("#### Síntese da pesquisa")
        clean = str(wr.get("text",""))
        clean = clean.replace("```python", "").replace("```json", "").replace("```", "")
        st.write(clean[:12000])
    if wr.get("citations"):
        st.markdown("#### Fontes oficiais/localizadas")
        for src in wr["citations"][:25]:
            title = src.get("title") or src.get("url")
            st.markdown(f"- [{title}]({src.get('url')})")
    if _rules_valid(study.get("rules")):
        st.success("✅ Matriz urbanística válida. Pode avançar para **4. Regras do jogo**.")

elif page.startswith("4"):
    st.subheader("4. Regras do jogo e condicionantes")
    rules = study.get("rules") or {}
    if not rules:
        st.info("Execute primeiro a pesquisa e a síntese da etapa 3.")
    else:
        ready = rules.get("overall_readiness",{})
        st.metric("Qualidade da base para análise", f"{ready.get('score',0)}/100", ready.get("label",""))
        p = rules.get("planning",{})
        st.markdown(f"**Instrumento:** {p.get('instrument','A confirmar')}  \n**Classificação:** {p.get('soil_class','')} / {p.get('category','')} / {p.get('subcategory','')}  \n**Estado:** `{p.get('status','a_confirmar')}`")
        st.markdown("#### Usos")
        if rules.get("uses"): st.dataframe(pd.DataFrame(rules["uses"]), use_container_width=True, hide_index=True)
        st.markdown("#### Parâmetros")
        rows=[]
        for k,v in (rules.get("parameters",{}) or {}).items():
            if isinstance(v,dict): rows.append({"Parâmetro":k,"Valor":v.get("value"),"Estado":v.get("status"),"Fundamento":v.get("basis")})
        if rows: st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown("#### Condicionantes")
        if rules.get("constraints"): st.dataframe(pd.DataFrame(rules["constraints"]), use_container_width=True, hide_index=True)
        if rules.get("conflicts"):
            st.error("Foram identificados conflitos que devem ser resolvidos antes de confiar nos cenários.")
            for conflict in rules.get("conflicts", []):
                if isinstance(conflict, dict):
                    st.write("• " + " · ".join(f"{k.replace('_',' ')}: {v}" for k,v in conflict.items() if v not in (None,"",[],{})))
                else:
                    st.write("• " + str(conflict))
        if rules.get("critical_questions"):
            st.warning("Pontos a confirmar: " + " · ".join(map(str,rules["critical_questions"])))

elif page.startswith("5"):
    st.subheader("5. Cálculos de capacidade urbanística")
    rules = study.get("rules") or {}
    if not rules:
        st.info("Valide primeiro as regras e condicionantes na etapa 4.")
    else:
        area_doc = ((rules.get("identification") or {}).get("area_m2"))
        area_map = study.get("estimated_area_m2")
        st.write("Os cálculos são executados em Python a partir de parâmetros confirmados. A IA não inventa valores numéricos em falta.")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Área do levantamento/documento", f"{area_doc:,.1f} m²" if isinstance(area_doc,(int,float)) else "A confirmar")
        with c2:
            st.metric("Área cartográfica aproximada", f"{area_map:,.1f} m²" if isinstance(area_map,(int,float)) else "A confirmar")
        area_default = float(study.get("confirmed_area_m2") or 0.0)
        confirmed_area = st.number_input("Área confirmada para cálculos (m²)", min_value=0.0, value=area_default, step=1.0, disabled=True, help="A área é escolhida/editada e confirmada na Etapa 3.")
        if confirmed_area <= 0:
            st.warning("Confirme primeiro a área do terreno na Etapa 3. A pesquisa territorial pode existir sem área, mas os cálculos não.")
        if st.button("🧮 Executar cálculos determinísticos", type="primary", disabled=confirmed_area <= 0):
            study["calculations"] = calculate_capacity(rules, confirmed_area)
            st.success("Cálculos executados em Python.")
        if study.get("calculations"):
            derived=(study["calculations"] or {}).get("derived",{})
            if derived:
                cols=st.columns(min(4,max(1,len(derived))))
                for i,(k,v) in enumerate(derived.items()):
                    with cols[i % len(cols)]:
                        st.metric(k.replace("_"," ").title(), v)
            with st.expander("Ver cálculo técnico completo"):
                st.json(study["calculations"])

elif page.startswith("6"):
    st.subheader("6. Objetivo do cliente e cenários")
    study["objective"] = st.selectbox("Objetivo", [
        "Determinar o melhor aproveitamento admissível", "Maximizar potencial do terreno", "Habitação multifamiliar",
        "Habitação unifamiliar", "Habitação bifamiliar", "Moradias em banda", "Comércio", "Serviços", "Uso misto habitação + comércio/serviços", "Turismo", "Outro"
    ], index=0)
    study["priority"] = st.selectbox("Prioridade", ["Equilíbrio entre aproveitamento e risco","Máxima área construída","Maior número de frações","Menor risco urbanístico","Maior qualidade de espaços exteriores"])
    if not study.get("calculations"):
        st.info("Execute primeiro a Etapa 5. Os cenários só usam cálculos baseados numa área confirmada.")
    if st.button("🏗️ Gerar 3 cenários preliminares", type="primary", disabled=not bool(study.get("rules") and study.get("calculations"))):
        with st.spinner("A estruturar alternativas de aproveitamento..."):
            try:
                svc = GeminiService()
                study["scenarios"] = svc.generate_scenarios(study["objective"], study["priority"], study["rules"], study["calculations"])
            except Exception as e:
                st.error(f"Erro: {e}")
    if study.get("scenarios"):
        cols = st.columns(3)
        for col,s in zip(cols, study["scenarios"][:3]):
            with col:
                st.markdown(f"### {s.get('code')} · {s.get('name')}")
                st.metric("ABC acima do solo", f"{s.get('above_ground_gfa_m2','-')} m²")
                st.metric("Implantação", f"{s.get('implantation_m2','-')} m²")
                st.write(f"**Pisos:** {s.get('floors_above_ground','-')}  ")
                st.write(f"**Fogos indicativos:** {s.get('indicative_units','-')}  ")
                st.write(f"**Risco:** {s.get('risk','-')}")
                st.write(s.get("concept", ""))
                if s.get("warnings"): st.warning(" · ".join(s["warnings"]))

elif page.startswith("7"):
    st.subheader("7. Relatório e exportação")
    if not (study.get("rules") and study.get("scenarios")):
        st.info("Complete pelo menos as regras e os cenários.")
    else:
        st.success("Estudo pronto para apresentação preliminar.")
        export = dict(study)
        pdf = build_pdf(export)
        st.download_button("📄 Descarregar relatório PDF", data=pdf, file_name=f"{study.get('study_ref','ESTUDO')}_viabilidade.pdf", mime="application/pdf", use_container_width=True)
        st.download_button("🧾 Descarregar JSON técnico", data=json.dumps(export, ensure_ascii=False, indent=2), file_name=f"{study.get('study_ref','ESTUDO')}_dados.json", mime="application/json", use_container_width=True)
        st.markdown("#### Fontes")
        for src in (study.get("web_research",{}) or {}).get("citations",[]):
            st.markdown(f"- [{src.get('title') or src.get('url')}]({src.get('url')})")

with st.sidebar:
    st.divider()
    if st.button("Sair"):
        st.session_state.authenticated = False
        st.rerun()
