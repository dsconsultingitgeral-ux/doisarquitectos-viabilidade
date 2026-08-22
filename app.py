from pathlib import Path
import streamlit as st

from src.auth import login_required, logout_button
from src.state import init_state, go
from src.prompt_loader import build_prompt
from src.gemini_engine import run_full_analysis
from src.report import build_pdf
from src.ui import inject_css, header, steps, metric_card, extract_highlight, source_cards, brand_logo
from src.location import geocode_location, reverse_geocode, inferred_fields
import folium
from folium.plugins import Fullscreen, Draw
from streamlit_folium import st_folium


def extract_label(text: str, labels: list[str], fallback: str = "—") -> str:
    """Extract an executive one-line value from a Markdown report."""
    import re
    lines = text.splitlines()
    targets = [x.upper().strip(": ") for x in labels]

    def clean(value: str) -> str:
        s = value or ""
        s = re.sub(r'[*#`>-]', '', s)
        s = re.sub(r'\$+', '', s)
        s = re.sub(r'\\text\{([^}]*)\}', r'\1', s)
        s = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', s)
        s = re.sub(r'\\(?:,|;|!|quad|qquad)', ' ', s)
        s = s.replace(r'\%', '%')
        s = re.sub(r'\^\{([^}]*)\}', r'\1', s)
        s = re.sub(r'_\{([^}]*)\}', r'\1', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    for i, raw in enumerate(lines):
        line = clean(raw)
        upper = line.upper()
        for label in targets:
            if upper.startswith(label + ":"):
                value = clean(line.split(":", 1)[1])
                if value:
                    return value
                for nxt in lines[i+1:i+5]:
                    value = clean(nxt)
                    if value:
                        return value
            if upper == label:
                for nxt in lines[i+1:i+5]:
                    value = clean(nxt)
                    if value:
                        return value
    return fallback


st.set_page_config(
    page_title="doisarquitetos · Pré-Viabilidade",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
init_state()

if not login_required():
    st.stop()

with st.sidebar:
    brand_logo(sidebar=True)
    st.markdown("### doisarquitetos")
    st.caption("Pré-Viabilidade Urbanística · V4.2 Plus")
    st.divider()
    if st.button("01 · Localização", use_container_width=True): go(1)
    if st.button("02 · Documentos", use_container_width=True): go(2)
    if st.button("03 · Análise IA", use_container_width=True): go(3)
    if st.button("04 · Potencial", use_container_width=True): go(4)
    st.divider()
    logout_button()

step = st.session_state.step
steps(step)

# ------------------------------------------------------------
# 01 — LOCALIZAÇÃO
# ------------------------------------------------------------
if step == 1:
    header(
        "Localizar o terreno",
        "Pesquise pela morada, clique diretamente no mapa ou desenhe o perímetro aproximado do terreno."
    )

    st.markdown("""
    <div class="da-hero">
      <div class="big">Onde fica o terreno?</div>
      <div class="small">
        Comece por uma rua, morada, localidade ou coordenadas. Também pode clicar no mapa
        para identificar automaticamente o local e desenhar um polígono aproximado da parcela.
        Sem documentos, a aplicação continua e produz uma pré-análise com base nas fontes oficiais disponíveis.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # IMPORTANT: apply pending values BEFORE the widget is instantiated.
    pending_search = st.session_state.pop("_pending_location_search", None)
    if pending_search is not None:
        st.session_state["location_search_v43"] = pending_search

    if "location_search_v43" not in st.session_state:
        st.session_state["location_search_v43"] = st.session_state.location or ""

    # --- Pesquisa
    search_col, action_col = st.columns([5, 1.35], gap="small")
    with search_col:
        query = st.text_input(
            "Pesquisar localização",
            key="location_search_v43",
            placeholder="Ex.: Alameda Silva Rocha, Aveiro"
        )
    with action_col:
        st.write("")
        st.write("")
        locate = st.button("Localizar", type="primary", use_container_width=True)

    if locate:
        if not query.strip():
            st.warning("Escreva uma morada, rua, localidade ou coordenadas.")
        else:
            try:
                with st.spinner("A localizar…"):
                    geo = geocode_location(query)
                if geo:
                    st.session_state.location = query.strip()
                    st.session_state.geo_lat = geo.lat
                    st.session_state.geo_lon = geo.lon
                    st.session_state.geo_display_name = geo.display_name
                    st.session_state.geo_source_url = geo.source_url

                    inf = inferred_fields(geo)
                    st.session_state.municipality = inf["municipality"]
                    st.session_state.parish = inf["parish"]
                    st.session_state.locality = inf["locality"]

                    # Synchronize text widgets only on the NEXT run.
                    st.session_state["_pending_municipality"] = inf["municipality"]
                    st.session_state["_pending_parish"] = inf["parish"]
                    st.session_state["_pending_locality"] = inf["locality"]
                    st.session_state["last_map_click"] = None
                    st.rerun()
                else:
                    st.warning("Não encontrei uma localização inequívoca. Clique diretamente no mapa.")
            except Exception as exc:
                st.warning("Não foi possível concluir a pesquisa de localização.")
                st.caption(str(exc))

    # --- Mapa sempre visível
    lat = st.session_state.geo_lat if st.session_state.geo_lat is not None else 40.2056
    lon = st.session_state.geo_lon if st.session_state.geo_lon is not None else -8.4196
    zoom = 17 if st.session_state.geo_lat is not None else 7

    st.markdown("### Mapa")
    st.caption(
        "Clique num ponto para obter a rua/localização. "
        "Use a ferramenta de desenho no canto do mapa para marcar o perímetro aproximado do terreno."
    )

    fmap = folium.Map(
        location=[lat, lon],
        zoom_start=zoom,
        control_scale=True,
        tiles="OpenStreetMap",
    )
    Fullscreen(position="topright", title="Ecrã inteiro", title_cancel="Sair").add_to(fmap)

    # Drawing tools: polygon and rectangle are enough for an approximate parcel.
    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": False,
            "polygon": {
                "allowIntersection": False,
                "showArea": True,
                "shapeOptions": {"color": "#1C2638", "weight": 3, "fillOpacity": 0.10},
            },
            "rectangle": {
                "shapeOptions": {"color": "#1C2638", "weight": 3, "fillOpacity": 0.10},
            },
            "circle": False,
            "marker": False,
            "circlemarker": False,
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(fmap)

    if st.session_state.geo_lat is not None and st.session_state.geo_lon is not None:
        folium.Marker(
            [st.session_state.geo_lat, st.session_state.geo_lon],
            tooltip="Localização selecionada",
            icon=folium.Icon(color="darkblue", icon="map-marker")
        ).add_to(fmap)

    map_data = st_folium(
        fmap,
        width=None,
        height=470,
        returned_objects=["last_clicked", "all_drawings"],
        use_container_width=True,
        key="terrain_map_v44",
    )

    # --- Clique no mapa -> reverse geocoding
    clicked = (map_data or {}).get("last_clicked")
    if clicked:
        click_key = f'{clicked.get("lat", 0):.6f},{clicked.get("lng", 0):.6f}'
        if click_key != st.session_state.get("last_map_click"):
            st.session_state["last_map_click"] = click_key
            try:
                with st.spinner("A identificar o local selecionado…"):
                    geo = reverse_geocode(float(clicked["lat"]), float(clicked["lng"]))
                if geo:
                    inf = inferred_fields(geo)
                    st.session_state.geo_lat = geo.lat
                    st.session_state.geo_lon = geo.lon
                    st.session_state.geo_display_name = geo.display_name
                    st.session_state.geo_source_url = geo.source_url
                    st.session_state.location = inf["concise"]
                    st.session_state.municipality = inf["municipality"]
                    st.session_state.parish = inf["parish"]
                    st.session_state.locality = inf["locality"]

                    # Safe widget updates on next run.
                    st.session_state["_pending_location_search"] = inf["concise"]
                    st.session_state["_pending_municipality"] = inf["municipality"]
                    st.session_state["_pending_parish"] = inf["parish"]
                    st.session_state["_pending_locality"] = inf["locality"]
                    st.rerun()
            except Exception as exc:
                st.warning("O ponto foi selecionado, mas não foi possível obter automaticamente a morada.")
                st.caption(str(exc))

    # --- Drawing / polygon capture
    drawings = (map_data or {}).get("all_drawings") or []
    polygon_coords = []
    if drawings:
        # Use the most recent polygon/rectangle.
        geom = drawings[-1].get("geometry", {})
        gtype = geom.get("type")
        coords = geom.get("coordinates", [])
        if gtype == "Polygon" and coords:
            polygon_coords = coords[0]
            st.session_state["parcel_polygon_geojson"] = geom
            st.session_state["parcel_polygon_coords"] = polygon_coords

    if polygon_coords:
        st.success(
            f"Perímetro aproximado desenhado com {max(len(polygon_coords)-1, 0)} vértices. "
            "Será tratado apenas como referência gráfica, não como limite cadastral confirmado."
        )

    if st.session_state.geo_lat is not None and st.session_state.geo_lon is not None:
        st.markdown(
            f"""
            <div class="da-card" style="margin-top:10px">
              <div class="da-card-label">LOCALIZAÇÃO SELECIONADA</div>
              <div class="da-card-value" style="font-size:18px">{st.session_state.geo_display_name or st.session_state.location}</div>
              <div class="da-card-note">
                Coordenadas: {st.session_state.geo_lat:.6f}, {st.session_state.geo_lon:.6f}
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Apply pending values BEFORE each widget creation.
    for pending_key, widget_key in [
        ("_pending_municipality", "municipality_v43"),
        ("_pending_parish", "parish_v43"),
        ("_pending_locality", "locality_v43"),
    ]:
        pending_value = st.session_state.pop(pending_key, None)
        if pending_value is not None:
            st.session_state[widget_key] = pending_value

    if "municipality_v43" not in st.session_state:
        st.session_state["municipality_v43"] = st.session_state.municipality or ""
    if "parish_v43" not in st.session_state:
        st.session_state["parish_v43"] = st.session_state.parish or ""
    if "locality_v43" not in st.session_state:
        st.session_state["locality_v43"] = st.session_state.locality or ""

    st.write("")
    st.markdown("### Dados do terreno")
    d1, d2, d3 = st.columns(3, gap="small")
    with d1:
        municipality_value = st.text_input("Município", key="municipality_v43")
        st.session_state.municipality = municipality_value
    with d2:
        parish_value = st.text_input("Freguesia", key="parish_v43")
        st.session_state.parish = parish_value
    with d3:
        locality_value = st.text_input("Localidade", key="locality_v43")
        st.session_state.locality = locality_value

    if "article_v43" not in st.session_state:
        st.session_state["article_v43"] = st.session_state.article or ""
    if "known_area_v43" not in st.session_state:
        st.session_state["known_area_v43"] = st.session_state.known_area or ""

    d4, d5 = st.columns(2, gap="small")
    with d4:
        article_value = st.text_input("Artigo matricial, se conhecido", key="article_v43")
        st.session_state.article = article_value
    with d5:
        known_area_value = st.text_input(
            "Área conhecida, se disponível",
            placeholder="Ex.: 2.974 m²",
            key="known_area_v43"
        )
        st.session_state.known_area = known_area_value

    st.markdown("""
    <div class="da-status-warn" style="margin-top:8px">
      <b>Nota técnica.</b> O ponto e o perímetro desenhado no mapa são referências de localização.
      Área jurídica, limites cadastrais e incidências exatas só são dadas como confirmadas quando suportadas
      por documento, cadastro, polígono oficial ou outra fonte competente.
    </div>
    """, unsafe_allow_html=True)

    if "location_confirmed_v43" not in st.session_state:
        st.session_state["location_confirmed_v43"] = st.session_state.location_confirmed

    confirmed = st.checkbox(
        "Confirmo que esta é a localização do terreno que pretendo analisar.",
        key="location_confirmed_v43"
    )
    st.session_state.location_confirmed = confirmed

    if st.button("Continuar para documentos →", type="primary", use_container_width=True):
        if not st.session_state.location.strip() and st.session_state.geo_lat is None:
            st.error("Selecione primeiro a localização do terreno.")
        elif not st.session_state.location_confirmed:
            st.error("Confirme a localização antes de continuar.")
        else:
            go(2)

# ------------------------------------------------------------
# 02 — DOCUMENTOS
# ------------------------------------------------------------
elif step == 2:
    header("Documentos", "Anexe o que existir. Se não houver documentos, a V4.2 Plus avança na mesma com um estudo preliminar baseado na localização e em fontes oficiais.")

    uploaded = st.file_uploader(
        "Documentos do terreno",
        type=["pdf", "png", "jpg", "jpeg", "txt", "docx"],
        accept_multiple_files=True,
        help="Levantamento topográfico, planta de localização, plantas PDM, certidões, cadernetas, PIP, informação municipal, etc."
    )
    if uploaded:
        st.session_state.uploaded_files = uploaded

    files = st.session_state.uploaded_files
    if files:
        st.success(f"{len(files)} documento(s) pronto(s) para análise.")
        rows = []
        for f in files:
            ext = Path(f.name).suffix.lower().replace(".", "").upper() or "FICHEIRO"
            size_mb = len(f.getvalue()) / (1024 * 1024)
            rows.append({"Documento": f.name, "Tipo": ext, "Tamanho": f"{size_mb:.2f} MB", "Estado": "✅ Fornecido"})
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.markdown("""
        <div class="da-status-warn">
          <b>Sem documentos? Pode avançar.</b><br>
          A V4.2 Plus cria um estudo preliminar com base na localização confirmada e pesquisa oficial. Nesse modo, não inventa a área nem os limites do terreno e marca como <b>A CONFIRMAR</b> tudo o que depende do polígono exato da parcela.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### Checklist que o motor irá procurar")
    check = [
        "PDM em vigor e regulamento", "Planta de Ordenamento", "Planta de Condicionantes",
        "REN", "RAN", "Recursos hídricos / cheias", "Incêndio e riscos",
        "Património / arqueologia", "Carta de ruído", "Servidões e infraestruturas",
        "Sistema viário / acessos", "Cadastro / informação predial",
        "PU / PP / loteamentos / unidades de execução / medidas preventivas"
    ]
    cols = st.columns(2)
    for i, item in enumerate(check):
        cols[i % 2].markdown(f"✓ {item}")

    st.markdown("### Como quer avançar?")
    q1, q2 = st.columns(2)

    with q1:
        st.markdown("""
        <div class="da-card">
          <div class="da-card-label">MODO RÁPIDO</div>
          <div class="da-card-value" style="font-size:20px">Só localização</div>
          <div class="da-card-note">Pesquisa oficial e estudo preliminar, mesmo sem documentos da parcela.</div>
        </div>
        """, unsafe_allow_html=True)
        quick = st.button("Avançar sem documentos →", use_container_width=True)

    with q2:
        st.markdown("""
        <div class="da-card">
          <div class="da-card-label">MODO COMPLETO</div>
          <div class="da-card-value" style="font-size:20px">Com documentos</div>
          <div class="da-card-note">Maior confiança, cruzamento documental e análise parcela-a-parcela.</div>
        </div>
        """, unsafe_allow_html=True)
        complete = st.button("Usar documentos anexados →", type="primary", use_container_width=True)

    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("← Voltar", use_container_width=True):
            go(1)
    with c2:
        if quick or complete:
            go(3)

# ------------------------------------------------------------
# 03 — ANÁLISE IA
# ------------------------------------------------------------
elif step == 3:
    header("Análise urbanística IA", "O Master Prompt aprovado é executado integralmente, com os documentos anexados e pesquisa web oficial.")

    st.markdown("""
    <div class="da-card">
    <b>Motor de análise V4.2 Plus</b><br><br>
    ✓ Interpretação integral dos documentos<br>
    ✓ Cruzamento e deteção de conflitos<br>
    ✓ Confirmação da localização<br>
    ✓ Pesquisa externa obrigatória em fontes oficiais<br>
    ✓ PDM, REN, RAN, ruído, incêndio, património e servidões<br>
    ✓ Extração de parâmetros quantitativos<br>
    ✓ Cálculos e identificação do fator limitante<br>
    ✓ Cenários Conservador / Equilibrado / Máximo<br>
    ✓ Referências numeradas [1], [2], [3] em todo o relatório<br>
    ✓ Lista final dos links efetivamente acedidos
    </div>
    """, unsafe_allow_html=True)

    with st.expander("Ver política do Master Prompt"):
        st.write("O ficheiro prompts/master_prompt.txt contém integralmente o prompt aprovado. A V4.2 Plus não o resume nem o substitui. Existe apenas um addendum separado para obrigar à rastreabilidade das fontes e dos links.")

    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("← Documentos", use_container_width=True):
            go(2)
    with c2:
        run = st.button("INICIAR ANÁLISE COMPLETA", type="primary", use_container_width=True)

    if run:
        if not st.session_state.location:
            st.error("Falta a localização.")
            st.stop()

        prompt = build_prompt(
            location=st.session_state.location,
            municipality=st.session_state.municipality,
            parish=st.session_state.parish,
            locality=st.session_state.locality,
            article=st.session_state.article,
            known_area=st.session_state.known_area,
            geo_lat=st.session_state.geo_lat,
            geo_lon=st.session_state.geo_lon,
            geo_display_name=st.session_state.geo_display_name,
            has_documents=bool(st.session_state.uploaded_files),
        )

        try:
            with st.spinner("A analisar documentos, consultar fontes oficiais e calcular o potencial do terreno…"):
                analysis, sources, response_id = run_full_analysis(prompt, st.session_state.uploaded_files)
            st.session_state.analysis_text = analysis
            st.session_state.analysis_sources = sources
            st.session_state.response_id = response_id
            go(4)
        except Exception as exc:
            st.error("Não foi possível concluir a análise.")
            st.exception(exc)
            st.info("Verifica a GEMINI_API_KEY e o modelo configurado nos Secrets privados do Streamlit.")

# ------------------------------------------------------------
# 04 — POTENCIAL / RELATÓRIO
# ------------------------------------------------------------
elif step == 4:
    header("Potencial do terreno", "Resultado executivo primeiro; fundamentação técnica, fontes e documentos permanecem disponíveis abaixo.")

    text = st.session_state.analysis_text
    if not text:
        st.warning("Ainda não existe uma análise concluída.")
        if st.button("Ir para Análise IA →", type="primary"):
            go(3)
        st.stop()

    # Executive extraction for clean cards. The complete report remains authoritative.
    viability = extract_highlight([
        r"(🟢\s*VIABILIDADE PRELIMINAR FAVORÁVEL(?: COM CONDICIONANTES)?)",
        r"(🟡\s*VIABILIDADE PRELIMINAR FAVORÁVEL COM CONDICIONANTES)",
        r"(🟠\s*VIABILIDADE AINDA INDETERMINADA)",
        r"(🔴\s*VIABILIDADE PRELIMINAR DESFAVORÁVEL)",
    ], text, "ANÁLISE CONCLUÍDA")

    area = extract_label(text, ["ÁREA CONSIDERADA", "ÁREA"], "—")
    classification = extract_label(text, ["CLASSIFICAÇÃO", "CATEGORIA"], "—")
    use = extract_label(text, ["USO MAIS INTERESSANTE", "USO RECOMENDADO"], "—")
    implantation = extract_label(text, ["IMPLANTAÇÃO MÁXIMA", "IMPLANTAÇÃO"], "—")
    floors = extract_label(text, ["PISOS"], "—")
    confidence = extract_label(text, ["CONFIANÇA GLOBAL", "CONFIANÇA"], "—")

    status_class = "da-status-good"
    if "DESFAVORÁVEL" in viability.upper():
        status_class = "da-status-bad"
    elif "INDETERMINADA" in viability.upper() or "CONDICIONANTES" in viability.upper():
        status_class = "da-status-warn"

    st.markdown(
        f'<div class="{status_class}"><b style="font-size:19px">{viability}</b>'
        '<br><span style="color:#667085">Síntese preliminar. A fundamentação e as referências estão disponíveis abaixo.</span></div>',
        unsafe_allow_html=True
    )
    st.write("")

    row1 = st.columns(3, gap="small")
    with row1[0]: metric_card("Área", area, "área considerada")
    with row1[1]: metric_card("Classificação", classification, "PDM / cartografia")
    with row1[2]: metric_card("Uso recomendado", use, "cenário principal")

    st.write("")
    row2 = st.columns(3, gap="small")
    with row2[0]: metric_card("Implantação", implantation, "quando determinada")
    with row2[1]: metric_card("Pisos", floors, "limite / cenário")
    with row2[2]: metric_card("Confiança", confidence, "evidência global")

    st.write("")
    tabs = st.tabs(["Síntese", "Análise técnica", "Fontes", "Relatório PDF"])

    with tabs[0]:
        # Show the conclusion section when possible; otherwise show the first part.
        marker = text.upper().find("CONCLUSÃO EXECUTIVA")
        if marker >= 0:
            st.markdown(text[marker:])
        else:
            st.markdown(text)

    with tabs[1]:
        st.markdown(text)

    with tabs[2]:
        st.markdown("### Links efetivamente acedidos")
        st.caption("Estes links são extraídos das anotações de citação URL devolvidas pela Pesquisa Google integrada no Gemini nesta execução.")
        source_cards(st.session_state.analysis_sources)
        st.divider()
        st.markdown("### Metodologia [1], [2], [3]")
        st.write("O próprio relatório usa referências numeradas junto às conclusões e termina com as secções de Referências, Fontes Online Acedidas e Documentos Fornecidos e Analisados, conforme o addendum obrigatório.")

    with tabs[3]:
        pdf = build_pdf(
            title="Estudo Preliminar de Viabilidade Urbanística",
            location=st.session_state.location,
            analysis_text=text,
            sources=st.session_state.analysis_sources,
        )
        st.download_button(
            "Descarregar relatório PDF",
            data=pdf,
            file_name="relatorio_viabilidade_urbanistica.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("← Rever documentos", use_container_width=True): go(2)
    with c2:
        if st.button("🔄 Repetir análise", use_container_width=True): go(3)
    with c3:
        if st.button("＋ Novo estudo", use_container_width=True):
            keep_auth = st.session_state.get("authenticated", False)
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.session_state.authenticated = keep_auth
            st.rerun()
