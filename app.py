from __future__ import annotations
import json
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

st.set_page_config(page_title="doisarquitectos | Viabilidade", page_icon="🏗️", layout="wide")

CSS = """
<style>
:root { --ink:#1f2d33; --muted:#62727a; --accent:#91b7bf; --panel:#f5f8f9; }
.block-container { padding-top: 1.5rem; max-width: 1500px; }
.da-title {font-size:2rem;font-weight:750;letter-spacing:-.02em;color:var(--ink);line-height:1.25;padding-top:.18rem;overflow:visible;margin:0;}
.da-sub {color:var(--muted);margin-top:2px;margin-bottom:18px;line-height:1.35;}
.step {padding:11px 14px;border-radius:10px;background:var(--panel);border:1px solid #dbe6e9;margin-bottom:7px;}
.kpi {border:1px solid #dde6e8;border-radius:12px;padding:14px;background:white;min-height:94px;}
.kpi .v {font-size:1.55rem;font-weight:750;color:var(--ink)}
.kpi .l {font-size:.83rem;color:var(--muted)}
.small-note {font-size:.82rem;color:#68777d;}
.source-box {background:#f7fafb;border-left:4px solid #91b7bf;padding:10px 12px;margin:5px 0;border-radius:4px;}
.brand-wrap{display:flex;align-items:center;gap:18px;margin-bottom:8px}.brand-logo img{max-height:76px;object-fit:contain}.status-pill{display:inline-block;padding:4px 9px;border-radius:999px;background:#eef5f6;color:#35515b;font-size:.78rem;border:1px solid #d7e5e8}.muted-card{background:#f7fafb;border:1px solid #e2eaec;border-radius:12px;padding:12px 14px}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"

def show_brand(compact: bool = False):
    c1, c2 = st.columns([0.34 if compact else 0.28, 1.72], vertical_alignment="center")
    with c1:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)
    with c2:
        st.markdown("<div class='da-title'>Estudo Inteligente de Viabilidade</div><div class='da-sub'>Da localização às regras urbanísticas, condicionantes e cenários preliminares.</div>", unsafe_allow_html=True)


def login():
    if st.session_state.get("authenticated"):
        return True
    c1,c2,c3 = st.columns([1,1.2,1])
    with c2:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)
        st.markdown("<div class='da-title' style='text-align:center'>Estudo Inteligente de Viabilidade</div><div class='da-sub' style='text-align:center'>Análise preliminar territorial e urbanística assistida por IA</div>", unsafe_allow_html=True)
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
        "documents_analysis":{}, "web_research":{}, "rules":{}, "calculations":{}, "scenarios":[]
    }
study = st.session_state.study

with st.sidebar:
    st.markdown("### Estudo")
    labels = [
        ("1", "Localização", bool(study.get("location_text") or study.get("polygon_geojson"))),
        ("2", "Documentação", bool(study.get("documents_analysis"))),
        ("3", "Pesquisa territorial", bool(study.get("web_research"))),
        ("4", "Regras do jogo", bool(study.get("rules"))),
        ("5", "Cálculos", bool(study.get("calculations"))),
        ("6", "Cenários", bool(study.get("scenarios"))),
        ("7", "Relatório", bool(study.get("rules") and study.get("scenarios"))),
    ]
    for n, name, done in labels:
        st.markdown(f"<div class='step'>{'✅' if done else '○'} <b>{n}. {name}</b></div>", unsafe_allow_html=True)
    st.divider()
    page = st.radio("Navegação", ["1 · Localização", "2 · Documentação", "3 · Pesquisa IA", "4 · Regras e condicionantes", "5 · Cenários", "6 · Relatório"], label_visibility="collapsed")
    st.caption(f"IA principal: {GEMINI_MODEL}")
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
    st.subheader("2. Documentação disponível")
    st.write("Não é necessário reunir previamente PDM, REN, RAN ou legislação. A IA procurará essas fontes. Aqui entram sobretudo documentos que o cliente já possui ou que o gabinete consegue obter rapidamente.")
    docs = st.file_uploader("Arraste quaisquer documentos disponíveis", type=["pdf","png","jpg","jpeg"], accept_multiple_files=True, key="all_docs")
    quick = st.session_state.get("quick_docs", [])
    all_docs = list(quick) + list(docs or [])
    if all_docs:
        df = pd.DataFrame([{"Ficheiro":f.name,"Tipo":getattr(f,"type",""),"Tamanho (MB)":round(len(f.getvalue())/1024/1024,2)} for f in all_docs])
        st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown("##### O classificador procura, entre outros:")
    st.caption("Levantamento topográfico · planta de localização/cartografia · plantas SIG · PDM ordenamento · PDM condicionantes · REN · RAN · incêndio · ruído · recursos hídricos · património · servidões · cadastro · caderneta · certidão · PIP · parecer/despacho · alvará/loteamento · PU/PP · estudo/projeto existente.")
    if st.button("🧠 Analisar e classificar documentação", type="primary", disabled=not all_docs):
        status = st.status("A analisar documentação com IA…", expanded=True)
        try:
            status.write("Leitura dos PDFs/imagens e classificação técnica.")
            status.write("Se o modelo principal estiver ocupado, a aplicação muda automaticamente para um modelo alternativo.")
            svc = GeminiService()
            study["documents_analysis"] = svc.analyze_documents(all_docs)
            used = study["documents_analysis"].get("_model_used", "") if isinstance(study["documents_analysis"], dict) else ""
            status.update(label=f"Análise documental concluída{f' · {used}' if used else ''}", state="complete", expanded=False)
            st.success("Documentação analisada. Confirme os dados extraídos antes de prosseguir.")
        except Exception as e:
            status.update(label="Não foi possível concluir a análise agora", state="error", expanded=True)
            st.error(str(e))
            st.info("Os ficheiros continuam carregados. Pode repetir sem voltar a anexá-los.")
    if study.get("documents_analysis"):
        data = study["documents_analysis"]
        rows = []
        for d in data.get("documents",[]):
            rows.append({"Ficheiro":d.get("filename"),"Tipo identificado":d.get("document_type"),"Importância":d.get("importance"),"Confiança":d.get("confidence")})
        if rows: st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        with st.expander("Ver extração técnica completa"):
            st.json(data)

elif page.startswith("3"):
    st.subheader("3. Pesquisa territorial e regulamentar pela IA")
    st.write("A IA procura fontes oficiais atuais: SIG/geoportal, PDM e alterações, Diário da República, DGT/SNIT e regimes especiais relevantes. O objetivo é descobrir as regras; não exigir que o arquiteto as anexe.")
    c1,c2,c3 = st.columns(3)
    c1.metric("Município", study.get("municipality") or "A confirmar")
    c2.metric("Freguesia", study.get("parish") or "A confirmar")
    c3.metric("Área aprox.", f"{study.get('estimated_area_m2'):,.0f} m²" if study.get("estimated_area_m2") else "A confirmar")
    if st.button("🌐 Pesquisar PDM, SIG, legislação e condicionantes", type="primary"):
        status = st.status("A pesquisar fontes territoriais e regulamentares…", expanded=True)
        try:
            status.write("A procurar PDM/SIG, Diário da República e restantes fontes oficiais relevantes.")
            svc = GeminiService()
            ctx = {k:study.get(k) for k in ["study_ref","location_text","municipality","parish","district","lat","lon","estimated_area_m2","objective","priority"]}
            study["web_research"] = svc.web_research(ctx, study.get("documents_analysis",{}))
            used = study["web_research"].get("model_used", "")
            status.update(label=f"Pesquisa concluída{f' · {used}' if used else ''}", state="complete", expanded=False)
            st.success("Pesquisa concluída. Reveja as fontes antes de validar.")
        except Exception as e:
            status.update(label="Pesquisa não concluída", state="error", expanded=True)
            st.error(str(e))
    if study.get("web_research"):
        st.markdown(study["web_research"].get("text", ""))
        if study["web_research"].get("citations"):
            st.markdown("#### Fontes recuperadas")
            for src in study["web_research"]["citations"]:
                st.markdown(f"- [{src.get('title') or src.get('url')}]({src.get('url')})")
        if st.button("✅ Cruzar documentos + fontes e construir regras do jogo"):
            with st.spinner("A validar e estruturar parâmetros..."):
                try:
                    svc = GeminiService()
                    ctx = {k:study.get(k) for k in ["study_ref","location_text","municipality","parish","district","lat","lon","estimated_area_m2","objective","priority"]}
                    study["rules"] = svc.synthesize_rules(ctx, study.get("documents_analysis",{}), study.get("web_research",{}))
                    st.success("Matriz técnica criada.")
                except Exception as e:
                    st.error(f"Erro: {e}")

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
            st.json(rules["conflicts"])
        if rules.get("critical_questions"):
            st.warning("Pontos a confirmar: " + " · ".join(map(str,rules["critical_questions"])))
        if st.button("🧮 Validar e calcular capacidade", type="primary"):
            study["calculations"] = calculate_capacity(rules, study.get("estimated_area_m2"))
            st.success("Cálculos executados em Python.")
        if study.get("calculations"):
            st.json(study["calculations"])

elif page.startswith("5"):
    st.subheader("5. Objetivo do cliente e cenários")
    study["objective"] = st.selectbox("Objetivo", [
        "Determinar o melhor aproveitamento admissível", "Maximizar potencial do terreno", "Habitação multifamiliar",
        "Habitação unifamiliar", "Habitação bifamiliar", "Moradias em banda", "Comércio", "Serviços", "Uso misto habitação + comércio/serviços", "Turismo", "Outro"
    ], index=0)
    study["priority"] = st.selectbox("Prioridade", ["Equilíbrio entre aproveitamento e risco","Máxima área construída","Maior número de frações","Menor risco urbanístico","Maior qualidade de espaços exteriores"])
    if st.button("🏗️ Gerar 3 cenários preliminares", type="primary", disabled=not bool(study.get("rules"))):
        if not study.get("calculations"):
            study["calculations"] = calculate_capacity(study.get("rules",{}), study.get("estimated_area_m2"))
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

elif page.startswith("6"):
    st.subheader("6. Relatório e exportação")
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
