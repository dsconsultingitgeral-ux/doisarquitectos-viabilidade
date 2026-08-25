import re
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]

def inject_css():
    st.markdown("""
    <style>
      :root{
        --ink:#111827;
        --muted:#6B7280;
        --line:#E7E9EE;
        --soft:#F7F8FA;
        --soft2:#FBFBFC;
        --accent:#171D2A;
      }

      .stApp { background:#fff; }
      .block-container{
        max-width:1180px;
        padding-top:3.2rem !important;
        padding-bottom:4rem;
      }

      section[data-testid="stSidebar"]{
        width:270px !important;
        background:#F8F9FA;
        border-right:1px solid #ECEEF2;
      }
      section[data-testid="stSidebar"] > div{ padding-top:1.8rem; }

      .da-kicker{
        font-size:10.5px;
        letter-spacing:.18em;
        font-weight:800;
        color:#7C8593;
        text-transform:uppercase;
      }
      .da-title{
        color:var(--ink);
        font-size:38px;
        line-height:1.04;
        font-weight:760;
        letter-spacing:-.035em;
        margin:.35rem 0 .5rem;
      }
      .da-sub{
        color:var(--muted);
        font-size:15px;
        line-height:1.55;
        margin-bottom:1.2rem;
      }

      .da-step{
        padding:11px 12px;
        border-radius:13px;
        border:1px solid var(--line);
        background:white;
        font-size:12px;
        font-weight:700;
        text-align:center;
        color:#444D5C;
        white-space:nowrap;
      }
      .da-step-active{
        background:var(--accent);
        color:white;
        border-color:var(--accent);
      }

      .da-hero{
        background:#F7F8FA;
        border:1px solid #ECEEF2;
        border-radius:20px;
        padding:22px 24px;
        margin:8px 0 20px;
      }
      .da-hero .big{
        color:#141A24;
        font-size:23px;
        font-weight:740;
        letter-spacing:-.02em;
      }
      .da-hero .small{
        color:#667085;
        margin-top:6px;
        font-size:13.5px;
        line-height:1.55;
      }

      .da-card{
        background:#fff;
        border:1px solid #E7E9EE;
        border-radius:18px;
        padding:18px 18px 17px;
        min-height:132px;
        box-shadow:0 6px 24px rgba(17,24,39,.035);
      }
      .da-card-label{
        font-size:10px;
        letter-spacing:.10em;
        text-transform:uppercase;
        color:#8A93A3;
        font-weight:800;
      }
      .da-card-value{
        font-size:22px;
        line-height:1.18;
        font-weight:730;
        margin-top:8px;
        color:#151A23;
        letter-spacing:-.022em;
        overflow-wrap:anywhere;
      }
      .da-card-note{
        font-size:11.5px;
        color:#8A93A3;
        margin-top:8px;
        line-height:1.4;
      }

      .da-status-good{background:#F2FBF5;border:1px solid #C8EFD2;padding:15px 17px;border-radius:15px;}
      .da-status-warn{background:#FFFBF0;border:1px solid #F3E0A1;padding:15px 17px;border-radius:15px;}
      .da-status-bad{background:#FFF3F3;border:1px solid #F3C1C1;padding:15px 17px;border-radius:15px;}

      .source-box{
        background:#FAFAFB;
        border:1px solid #ECEEF2;
        border-left:3px solid #202938;
        padding:12px 14px;
        margin:8px 0;
        border-radius:10px;
      }

      div[data-testid="stTextInput"] input{
        min-height:45px;
        border-radius:12px !important;
        background:#FBFCFD;
      }
      div[data-testid="stButton"] button,
      div[data-testid="stDownloadButton"] button{
        min-height:44px;
        border-radius:12px;
        font-weight:700;
      }

      /* Keep original logo crisp: browsers downscale high-res raster very well. */
      div[data-testid="stImage"] img{
        object-fit:contain;
        image-rendering:auto;
      }

      iframe{ border-radius:14px !important; }

      @media(max-width:900px){
        .block-container{padding-top:2.5rem !important;}
        .da-title{font-size:31px;}
      }
    </style>
    """, unsafe_allow_html=True)

def brand_logo(sidebar=False, login=False):
    logo = ROOT / "assets" / "logo.png"
    if logo.exists():
        if login:
            st.image(str(logo), width=285)
        elif sidebar:
            st.image(str(logo), width=235)
        else:
            st.image(str(logo), width=230)

def header(title: str, subtitle: str):
    st.markdown(
        f'<div class="da-kicker">VIABILIDADE URBANÍSTICA</div>'
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

def _plain(value: str) -> str:
    if not value:
        return "—"
    s = value
    # Strip markdown / LaTeX fragments that must never leak into cards.
    s = re.sub(r'\$+', '', s)
    s = re.sub(r'\\text\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\(?:,|;|!|quad|qquad)', ' ', s)
    s = s.replace(r'\%', '%').replace(r'\_', '_')
    s = re.sub(r'\^\{([^}]*)\}', r'\1', s)
    s = re.sub(r'_\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\[([0-9]+)\]', r'[\1]', s)
    s = re.sub(r'[*#`]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def compact_value(value: str, max_chars: int = 72) -> str:
    s = _plain(value)
    # Cards are executive; references belong in the detailed report.
    s = re.sub(r'\s*\[[0-9]+\]', '', s).strip()
    if len(s) > max_chars:
        s = s[:max_chars-1].rstrip(" ,;:-") + "…"
    return s or "—"

def metric_card(label: str, value: str, note: str = ""):
    value = compact_value(value)
    st.markdown(
        f'<div class="da-card"><div class="da-card-label">{label}</div>'
        f'<div class="da-card-value">{value}</div>'
        f'<div class="da-card-note">{note}</div></div>',
        unsafe_allow_html=True
    )

def extract_highlight(patterns: list[str], text: str, fallback: str = "—") -> str:
    for p in patterns:
        m = re.search(p, text, flags=re.I | re.M)
        if m:
            return _plain(m.group(1).strip())
    return fallback

def extract_label(text: str, labels: list[str], fallback: str = "—") -> str:
    """Flexible extraction from Markdown labels, with one-line or next-line values."""
    lines = text.splitlines()
    clean_labels = [x.upper().strip(": ") for x in labels]
    for i, raw in enumerate(lines):
        line = re.sub(r'[*#`]', '', raw).strip()
        upper = line.upper()
        for lab in clean_labels:
            if upper.startswith(lab + ":"):
                val = line.split(":", 1)[1].strip()
                if val:
                    return _plain(val)
                # first meaningful following line
                for nxt in lines[i+1:i+4]:
                    v = re.sub(r'[*#`>-]', '', nxt).strip()
                    if v:
                        return _plain(v)
            if upper == lab:
                for nxt in lines[i+1:i+4]:
                    v = re.sub(r'[*#`>-]', '', nxt).strip()
                    if v:
                        return _plain(v)
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
