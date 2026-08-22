from pathlib import Path
import streamlit as st

from src.auth import login_required, logout_button
from src.state import init_state, go
from src.prompt_loader import build_prompt
from src.gemini_engine import run_full_analysis
from src.report import build_pdf
from src.ui import inject_css, header, steps, metric_card, extract_highlight, source_cards, brand_logo
from src.location import geocode_location, inferred_fields

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
    brand_logo(compact=True)
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
    header("Validar localização", "Localização clara, mapa imediato e confirmação antes do estudo técnico.")

    st.markdown("""
    <div class="da-hero">
      <div class="big">Começa apenas pela localização.</div>
      <div class="small">Mesmo sem documentos, a V4.2 Plus pode produzir um estudo preliminar da zona através de fontes oficiais. Os documentos aumentam a precisão e permitem confirmar a parcela.</div>
    </div>
    """, unsafe_allow_html=True)

    c_addr, c_btn = st.columns([4, 1])
    with c_addr:
        st.session_state.location = st.text_input(
            "Morada / localização do terreno *",
            value=st.session_state.location,
            placeholder="Ex.: Alameda Silva Rocha, Aveiro"
        )
    with c_btn:
        st.write("")
        st.write("")
        locate = st.button("📍 Localizar", use_container_width=True)

    if locate and st.session_state.location.strip():
        try:
            with st.spinner("A localizar…"):
                geo = geocode_location(st.session_state.location)
            if geo:
                st.session_state.geo_lat = geo.lat
                st.session_state.geo_lon = geo.lon
                st.session_state.geo_display_name = geo.display_name
                st.session_state.geo_source_url = geo.source_url
                inf = inferred_fields(geo)
                if not st.session_state.municipality:
                    st.session_state.municipality = inf["municipality"]
                if not st.session_state.parish:
                    st.session_state.parish = inf["parish"]
                if not st.session_state.locality:
                    st.session_state.locality = inf["locality"]
                st.success("Localização aproximada encontrada. Confirma visualmente o ponto no mapa.")
            else:
                st.warning("Não encontrei um ponto inequívoco. Podes completar manualmente a localização e continuar.")
        except Exception as exc:
            st.warning("Não foi possível geocodificar agora. A análise pode continuar com a morada escrita.")
            st.caption(str(exc))

    if st.session_state.geo_lat is not None and st.session_state.geo_lon is not None:
        st.markdown("### Mapa de localização")
        st.map(
            [{"lat": st.session_state.geo_lat, "lon": st.session_state.geo_lon}],
            latitude="lat",
            longitude="lon",
            zoom=16,
            use_container_width=True,
        )
        st.markdown(
            f'<div class="map-note"><b>Ponto aproximado:</b> {st.session_state.geo_display_name}<br>'
            'Este mapa serve para validar a localização. Não representa os limites cadastrais nem permite inferir a área do terreno.</div>',
            unsafe_allow_html=True
        )

    st.write("")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.municipality = st.text_input("Município", value=st.session_state.municipality)
    with c2:
        st.session_state.parish = st.text_input("Freguesia", value=st.session_state.parish)
    with c3:
        st.session_state.locality = st.text_input("Localidade", value=st.session_state.locality)

    c4, c5 = st.columns(2)
    with c4:
        st.session_state.article = st.text_input("Artigo matricial, se conhecido", value=st.session_state.article)
    with c5:
        st.session_state.known_area = st.text_input("Área conhecida, se disponível", value=st.session_state.known_area, placeholder="Ex.: 2.974 m²")

    st.markdown("""
    <div class="da-status-warn">
    <b>Regra de segurança:</b> a morada e o ponto do mapa são apenas uma referência de localização.
    A área, limites do prédio, artigo matricial e incidência exata de condicionantes só são considerados confirmados quando sustentados por documentos, cadastro, polígono conhecido ou fonte oficial aplicável.
    </div>
    """, unsafe_allow_html=True)

    st.session_state.location_confirmed = st.checkbox(
        "Confirmo que o ponto/morada correspondem ao local que pretendo estudar.",
        value=st.session_state.location_confirmed
    )

    if st.button("Confirmar localização e continuar →", type="primary", use_container_width=True):
        if not st.session_state.location.strip():
            st.error("Indica pelo menos uma morada ou localização.")
        elif not st.session_state.location_confirmed:
            st.error("Confirma a localização antes de continuar.")
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

        stages = [
            "A analisar documentos e desenhos…",
            "A cruzar localização, área e identificação predial…",
            "A pesquisar PDM e fontes oficiais…",
            "A verificar REN, RAN, riscos e servidões…",
            "A extrair regras quantitativas…",
            "A calcular cenários e potencial…",
            "A organizar referências [1], [2], [3] e links…",
        ]
        status = st.status("Estudo em execução…", expanded=True)
        for s in stages:
            status.write(s)

        try:
            analysis, sources, response_id = run_full_analysis(prompt, st.session_state.uploaded_files)
            st.session_state.analysis_text = analysis
            st.session_state.analysis_sources = sources
            st.session_state.response_id = response_id
            status.update(label="Análise concluída.", state="complete", expanded=False)
            st.success("Estudo concluído. A abrir o resultado executivo…")
            go(4)
        except Exception as exc:
            status.update(label="Não foi possível concluir a análise.", state="error")
            st.exception(exc)
            st.info("Verifica a GEMINI_API_KEY em Settings > Secrets do Streamlit Cloud.")

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

    # Best-effort extraction for headline cards. The complete report remains authoritative.
    viability = extract_highlight([
        r"(🟢\s*VIABILIDADE PRELIMINAR FAVORÁVEL(?: COM CONDICIONANTES)?)",
        r"(🟡\s*VIABILIDADE PRELIMINAR FAVORÁVEL COM CONDICIONANTES)",
        r"(🟠\s*VIABILIDADE AINDA INDETERMINADA)",
        r"(🔴\s*VIABILIDADE PRELIMINAR DESFAVORÁVEL)",
    ], text, "RESULTADO DISPONÍVEL")

    area = extract_highlight([
        r"ÁREA CONSIDERADA:\s*\n?\s*([^\n]+)",
        r"\*\*ÁREA CONSIDERADA:\*\*\s*([^\n]+)",
    ], text)
    classification = extract_highlight([
        r"CLASSIFICAÇÃO:\s*\n?\s*([^\n]+)",
        r"\*\*CLASSIFICAÇÃO:\*\*\s*([^\n]+)",
    ], text)
    use = extract_highlight([
        r"USO MAIS INTERESSANTE:\s*\n?\s*([^\n]+)",
        r"\*\*USO MAIS INTERESSANTE:\*\*\s*([^\n]+)",
    ], text)
    floors = extract_highlight([
        r"PISOS:\s*\n?\s*([^\n]+)",
        r"\*\*PISOS:\*\*\s*([^\n]+)",
    ], text)
    confidence = extract_highlight([
        r"CONFIANÇA GLOBAL:\s*\n?\s*([^\n]+)",
        r"\*\*CONFIANÇA GLOBAL:\*\*\s*([^\n]+)",
    ], text)

    st.markdown(f'<div class="da-status-good"><b style="font-size:20px">{viability}</b><br><span style="color:#4B5563">Conclusão preliminar produzida pelo motor técnico V4.2 Plus.</span></div>', unsafe_allow_html=True)
    st.write("")

    cols = st.columns(5)
    with cols[0]: metric_card("Área", area, "ver conflitos no relatório")
    with cols[1]: metric_card("Classificação", classification, "PDM / cartografia")
    with cols[2]: metric_card("Uso recomendado", use, "potencial principal")
    with cols[3]: metric_card("Pisos", floors, "quando determinado")
    with cols[4]: metric_card("Confiança", confidence, "evidência global")

    st.write("")
    tabs = st.tabs(["Resumo executivo", "Análise técnica completa", "Fontes e links", "Relatório PDF"])

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
            "📄 Descarregar relatório PDF",
            data=pdf,
            file_name="relatorio_viabilidade_urbanistica.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        st.download_button(
            "📝 Descarregar relatório Markdown",
            data=text.encode("utf-8"),
            file_name="relatorio_viabilidade_urbanistica.md",
            mime="text/markdown",
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
