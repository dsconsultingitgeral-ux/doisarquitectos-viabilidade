import re
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]

def inject_css():
    st.markdown("""
    <style>
      :root{
        --ink:#171D2A;
        --muted:#6B7280;
        --line:#E7E9EE;
        --paper:#FFFFFF;
        --soft:#F7F8FA;
        --accent:#1C2638;
      }

      html, body, [class*="css"] { font-family: Inter, "Helvetica Neue", Arial, sans-serif; }
      .stApp { background:#FFFFFF; }

      /* Do not let Streamlit's top chrome cut the page */
      .block-container{
        max-width:1160px;
        padding-top:3.5rem !important;
        padding-bottom:4rem;
      }

      section[data-testid="stSidebar"]{
        width:270px !important;
        background:#F7F8FA;
        border-right:1px solid #ECEEF2;
      }
      section[data-testid="stSidebar"] > div{
        padding-top:2.1rem;
      }

      .da-brand{
        display:flex;
        align-items:center;
        justify-content:center;
        margin:0 auto 1.2rem;
      }
      .da-kicker{
        font-size:11px;
        letter-spacing:.17em;
        font-weight:800;
        color:#697386;
        text-transform:uppercase;
      }
      .da-title{
        color:var(--ink);
        font-size:38px;
        line-height:1.04;
        font-weight:760;
        letter-spacing:-.03em;
        margin:.35rem 0 .55rem;
      }
      .da-sub{
        color:var(--muted);
        font-size:15px;
        line-height:1.55;
        margin-bottom:1.35rem;
      }

      .da-step{
        padding:12px 13px;
        border-radius:13px;
        border:1px solid var(--line);
        background:white;
        font-size:12.5px;
        font-weight:700;
        text-align:center;
        color:#384152;
        white-space:nowrap;
      }
      .da-step-active{
        background:var(--accent);
        color:white;
        border-color:var(--accent);
        box-shadow:0 8px 22px rgba(28,38,56,.10);
      }

      .da-hero{
        background:#F7F8FA;
        border:1px solid #ECEEF2;
        border-radius:22px;
        padding:24px 26px;
        margin:8px 0 22px;
      }
      .da-hero .big{
        color:var(--ink);
        font-size:24px;
        font-weight:760;
        letter-spacing:-.02em;
      }
      .da-hero .small{
        color:#667085;
        margin-top:6px;
        font-size:14px;
        line-height:1.55;
      }

      .da-card{
        background:white;
        border:1px solid var(--line);
        border-radius:18px;
        padding:18px 20px;
        box-shadow:0 7px 24px rgba(17,24,39,.045);
        height:100%;
      }
      .da-card-label{
        font-size:10.5px;
        letter-spacing:.10em;
        text-transform:uppercase;
        color:#7A8493;
        font-weight:800;
      }
      .da-card-value{
        font-size:25px;
        font-weight:760;
        margin-top:4px;
        color:var(--ink);
        letter-spacing:-.025em;
      }
      .da-card-note{font-size:12px;color:#7A8493;margin-top:3px;}

      .da-map-shell{
        border:1px solid #E4E7EC;
        border-radius:20px;
        overflow:hidden;
        background:white;
        box-shadow:0 8px 28px rgba(17,24,39,.055);
        padding:7px 7px 0;
        margin:8px 0 4px;
      }
      .da-map-hint{
        font-size:12.5px;
        line-height:1.5;
        color:#667085;
        padding:8px 4px 12px;
      }

      .da-status-good{background:#F0FDF4;border:1px solid #BBF7D0;padding:15px 17px;border-radius:14px;}
      .da-status-warn{background:#FFFBEB;border:1px solid #FDE68A;padding:15px 17px;border-radius:14px;}
      .da-status-bad{background:#FEF2F2;border:1px solid #FECACA;padding:15px 17px;border-radius:14px;}

      .source-box{
        background:#FAFAFA;
        border:1px solid #ECEEF2;
        border-left:4px solid var(--accent);
        padding:12px 14px;
        margin:8px 0;
        border-radius:10px;
      }

      div[data-testid="stTextInput"] input,
      div[data-testid="stNumberInput"] input{
        border-radius:12px !important;
        min-height:46px;
        background:#FBFCFD;
      }

      div[data-testid="stButton"] button,
      div[data-testid="stDownloadButton"] button{
        min-height:44px;
        border-radius:12px;
        font-weight:700;
      }

      /* Avoid oversized Streamlit logo/image scaling */
      div[data-testid="stImage"] img{
        object-fit:contain;
      }

      /* Folium iframe container */
      iframe{
        border-radius:14px !important;
      }

      @media(max-width: 900px){
        .block-container{padding-top:2.5rem !important;}
        .da-title{font-size:31px;}
        section[data-testid="stSidebar"]{width:240px !important;}
      }
    </style>
    """, unsafe_allow_html=True)

def _logo_path():
    candidates = [
        ROOT/"assets"/"logo.png",
        ROOT/"assets"/"logo.webp",
        ROOT/"assets"/"logo.jpg",
        ROOT/"assets"/"logo.svg",
    ]
    return next((p for p in candidates if p.exists()), None)

def brand_logo(sidebar=False, login=False):
    logo = _logo_path()
    if not logo:
        return
    # Crucial: never enlarge the raster logo, which was the cause of blur.
    if login:
        st.image(str(logo), width=245)
    elif sidebar:
        st.image(str(logo), width=225)
    else:
        st.image(str(logo), width=225)

def header(title: str, subtitle: str):
    # No duplicated logo here: the brand already lives in the sidebar.
    st.markdown(
        f'<div class="da-kicker">PRÉ-VIABILIDADE URBANÍSTICA · V4.2 PLUS</div>'
        f'<div class="da-title">{title}</div>'
        f'<div class="da-sub">{subtitle}</div>',
        unsafe_allow_html=True
    )

def steps(current: int):
    labels = ["01 · Localização", "02 · Documentos", "03 · Análise IA", "04 · Potencial"]
    cols = st.columns(4, gap="small")
    for i, (c, label) in enumerate(zip(cols, labels), start=1):
        cls = "da-step da-step-active" if i == current else "da-step"
        c.markdown(f'<div class="{cls}">{label}</div>', unsafe_allow_html=True)
    st.write("")

def metric_card(label: str, value: str, note: str = ""):
    st.markdown(
        f'<div class="da-card"><div class="da-card-label">{label}</div>'
        f'<div class="da-card-value">{value}</div><div class="da-card-note">{note}</div></div>',
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
        st.info("Não foram devolvidos links estruturados nesta execução. As referências [n] permanecem no relatório técnico.")
        return
    for i, s in enumerate(sources, start=1):
        title = getattr(s, "title", "Fonte consultada")
        url = getattr(s, "url", "")
        st.markdown(
            f'<div class="source-box"><b>[{i}] {title}</b><br>'
            f'<a href="{url}" target="_blank">{url}</a></div>',
            unsafe_allow_html=True
        )
