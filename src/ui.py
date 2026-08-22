import re
import streamlit as st

def inject_css():
    st.markdown("""
    <style>
      .block-container {max-width: 1220px; padding-top: 2rem; padding-bottom: 4rem;}
      .da-kicker {font-size:12px; letter-spacing:.14em; font-weight:800; color:#6B7280;}
      .da-title {font-size:34px; line-height:1.08; font-weight:850; margin:.25rem 0 .5rem;}
      .da-sub {color:#6B7280; font-size:15px; margin-bottom:1rem;}
      .da-card {background:white;border:1px solid #E5E7EB;border-radius:18px;padding:18px 20px;box-shadow:0 1px 2px rgba(0,0,0,.03);height:100%;}
      .da-card-label {font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#6B7280;font-weight:700;}
      .da-card-value {font-size:27px;font-weight:850;margin-top:3px;color:#111827;}
      .da-card-note {font-size:12px;color:#6B7280;margin-top:2px;}
      .da-step {padding:10px 12px;border-radius:12px;border:1px solid #E5E7EB;background:#fff;font-size:13px;font-weight:700;text-align:center;}
      .da-step-active {background:#111827;color:white;border-color:#111827;}
      .da-status-good {background:#ECFDF5;border:1px solid #A7F3D0;padding:15px;border-radius:14px;}
      .da-status-warn {background:#FFFBEB;border:1px solid #FDE68A;padding:15px;border-radius:14px;}
      .da-status-bad {background:#FEF2F2;border:1px solid #FECACA;padding:15px;border-radius:14px;}
      .source-box {background:#F9FAFB;border-left:4px solid #111827;padding:12px 14px;margin:8px 0;border-radius:8px;}
      div[data-testid="stButton"] button {border-radius:12px;font-weight:700;}
      div[data-testid="stDownloadButton"] button {border-radius:12px;font-weight:700;}
    </style>
    """, unsafe_allow_html=True)

def header(title: str, subtitle: str):
    st.markdown(f'<div class="da-kicker">PRÉ-VIABILIDADE URBANÍSTICA · V4</div><div class="da-title">{title}</div><div class="da-sub">{subtitle}</div>', unsafe_allow_html=True)

def steps(current: int):
    labels = ["01 · Localização", "02 · Documentos", "03 · Análise IA", "04 · Potencial"]
    cols = st.columns(4)
    for i, (c, label) in enumerate(zip(cols, labels), start=1):
        cls = "da-step da-step-active" if i == current else "da-step"
        c.markdown(f'<div class="{cls}">{label}</div>', unsafe_allow_html=True)
    st.write("")

def metric_card(label: str, value: str, note: str = ""):
    st.markdown(
        f'<div class="da-card"><div class="da-card-label">{label}</div><div class="da-card-value">{value}</div><div class="da-card-note">{note}</div></div>',
        unsafe_allow_html=True
    )

def extract_highlight(patterns: list[str], text: str, fallback: str = "—") -> str:
    for p in patterns:
        m = re.search(p, text, flags=re.I | re.M)
        if m:
            value = m.group(1).strip()
            value = re.sub(r"[*#`]", "", value)
            return value[:120]
    return fallback

def source_cards(sources):
    if not sources:
        st.info("A API não devolveu anotações URL estruturadas nesta execução. As referências [n] permanecem no relatório gerado pelo modelo.")
        return
    for i, s in enumerate(sources, start=1):
        title = getattr(s, "title", "Fonte consultada")
        url = getattr(s, "url", "")
        st.markdown(
            f'<div class="source-box"><b>[{i}] {title}</b><br><a href="{url}" target="_blank">{url}</a></div>',
            unsafe_allow_html=True
        )
