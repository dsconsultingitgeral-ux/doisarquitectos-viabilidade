from io import BytesIO
from pathlib import Path
from datetime import datetime
import html
import re
import tempfile

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether, Image
from reportlab.lib import colors
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "folha_tipo.pdf"
COVER_LOGO = ROOT / "assets" / "cover_logo.png"

def _fmt(s: str) -> str:
    """Convert common Markdown/LaTeX artefacts to clean ReportLab inline markup."""
    raw = str(s or "")

    # Common LaTeX/math tokens that otherwise leaked into client PDFs.
    raw = raw.replace(r"\%", "%")
    raw = raw.replace(r"\times", "×")
    raw = raw.replace(r"\leq", "≤").replace(r"\geq", "≥")
    raw = raw.replace(r"\le", "≤").replace(r"\ge", "≥")
    raw = re.sub(r"\\text\{([^}]*)\}", r"\1", raw)
    raw = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", raw)
    raw = re.sub(r"\\mathbf\{([^}]*)\}", r"\1", raw)
    raw = re.sub(r"\\(?:,|;|!|quad|qquad)\b", " ", raw)
    raw = re.sub(r"\\^\{([^}]*)\}", r"^\1", raw)
    raw = re.sub(r"_\{([^}]*)\}", r"_\1", raw)
    raw = raw.replace("$", "")
    raw = re.sub(r"\s+", " ", raw).strip()

    # Escape first, then apply only the small subset of markup ReportLab supports.
    escaped = html.escape(raw)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = escaped.replace("`", "")
    return escaped

def _parse(text: str):
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line and re.fullmatch(r"[=\-_]{8,}", line):
            continue
        if not line:
            yield ("space", "")
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            value = heading.group(2).strip()
            if level == 1:
                yield ("h1", value)
            elif level == 2:
                yield ("h2", value)
            else:
                yield ("h3", value)
        elif line.startswith("|") and line.endswith("|"):
            yield ("table", line)
        elif line.startswith(("- ", "* ", "• ")):
            yield ("bullet", line[2:] if line[:2] in {"- ", "* "} else line[2:])
        else:
            yield ("p", line)


def _cover_pdf(title: str, location: str) -> bytes:
    """Create a clean one-page institutional cover using the client logo."""
    out = BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=A4, leftMargin=24*mm, rightMargin=24*mm,
        topMargin=30*mm, bottomMargin=24*mm, title=title, author="doisarquitetos",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=25, leading=29, textColor=colors.HexColor("#1B1B1B"),
        alignment=TA_CENTER, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="CoverLocation", parent=styles["Normal"], fontName="Helvetica",
        fontSize=11, leading=16, textColor=colors.HexColor("#555B63"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="CoverMeta", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9, leading=13, textColor=colors.HexColor("#7A7F87"),
        alignment=TA_CENTER,
    ))

    story = [Spacer(1, 18*mm)]
    if COVER_LOGO.exists():
        # Preserve aspect ratio and keep generous white space.
        img = Image(str(COVER_LOGO), width=150*mm, height=41.5*mm)
        img.hAlign = "CENTER"
        story.extend([img, Spacer(1, 35*mm)])
    else:
        story.append(Spacer(1, 40*mm))

    story.extend([
        Paragraph(_fmt(title.upper()), styles["CoverTitle"]),
        Spacer(1, 7*mm),
        Paragraph(_fmt(location or "Localização a confirmar"), styles["CoverLocation"]),
        Spacer(1, 35*mm),
        Paragraph(_fmt(f"Data do estudo: {datetime.now().strftime('%d/%m/%Y')}"), styles["CoverMeta"]),
        Spacer(1, 3*mm),
        Paragraph("Análise preliminar de apoio à decisão urbanística", styles["CoverMeta"]),
    ])
    doc.build(story)
    return out.getvalue()

def _content_pdf(title: str, location: str, analysis_text: str, sources) -> bytes:
    out = BytesIO()

    # Large top/right whitespace respects the user's official sheet.
    doc = SimpleDocTemplate(
        out,
        pagesize=A4,
        leftMargin=24*mm,
        rightMargin=24*mm,
        topMargin=40*mm,
        bottomMargin=28*mm,
        title=title,
        author="doisarquitetos",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DA_Title", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=18, leading=22, textColor=colors.HexColor("#1B1B1B"),
        spaceAfter=4, alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        name="DA_Meta", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.5, leading=12, textColor=colors.HexColor("#70757D"),
        spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        name="DA_H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=15, leading=19, textColor=colors.HexColor("#1B1B1B"),
        spaceBefore=8, spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name="DA_H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12.5, leading=16, textColor=colors.HexColor("#1B1B1B"),
        spaceBefore=8, spaceAfter=5
    ))
    styles.add(ParagraphStyle(
        name="DA_H3", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=10.5, leading=14, textColor=colors.HexColor("#1B1B1B"),
        spaceBefore=6, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name="DA_Body", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=9, leading=13.2, textColor=colors.HexColor("#292D32"),
        spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name="DA_Bullet", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=9, leading=13.2, leftIndent=10, bulletIndent=1,
        textColor=colors.HexColor("#292D32"), spaceAfter=3
    ))

    story = [
        Paragraph(_fmt(title), styles["DA_Title"]),
        Paragraph(
            _fmt(f"{location} · Relatório de Viabilidade Urbanística · {datetime.now().strftime('%d/%m/%Y')}"),
            styles["DA_Meta"]
        ),
        Spacer(1, 3*mm)
    ]

    table_lines = []
    def flush_table():
        nonlocal table_lines
        if not table_lines:
            return
        rows=[]
        for ln in table_lines:
            cells=[c.strip() for c in ln.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            rows.append([Paragraph(_fmt(c), styles["DA_Body"]) for c in cells])
        if rows:
            t=Table(rows, repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#F4F5F6")),
                ("TEXTCOLOR",(0,0),(-1,0),colors.HexColor("#1B1B1B")),
                ("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#D9DCE1")),
                ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("LEFTPADDING",(0,0),(-1,-1),5),
                ("RIGHTPADDING",(0,0),(-1,-1),5),
                ("TOPPADDING",(0,0),(-1,-1),4),
                ("BOTTOMPADDING",(0,0),(-1,-1),4),
            ]))
            story.append(t)
            story.append(Spacer(1, 3*mm))
        table_lines=[]

    for kind, value in _parse(analysis_text):
        if kind == "table":
            table_lines.append(value)
            continue
        flush_table()
        if kind == "space":
            story.append(Spacer(1, 1.5*mm))
        elif kind == "h1":
            story.append(Paragraph(_fmt(value), styles["DA_H1"]))
        elif kind == "h2":
            story.append(Paragraph(_fmt(value), styles["DA_H2"]))
        elif kind == "h3":
            story.append(Paragraph(_fmt(value), styles["DA_H3"]))
        elif kind == "bullet":
            story.append(Paragraph(_fmt(value), styles["DA_Bullet"], bulletText="•"))
        else:
            story.append(Paragraph(_fmt(value), styles["DA_Body"]))
    flush_table()

    if sources:
        story.append(PageBreak())
        story.append(Paragraph("Fontes online acedidas", styles["DA_H1"]))
        for i, s in enumerate(sources, 1):
            title_s = getattr(s, "title", "Fonte consultada")
            url_s = getattr(s, "url", "")
            story.append(Paragraph(
                f"[{i}] <b>{_fmt(title_s)}</b><br/><font color='#666666'>{html.escape(url_s)}</font>",
                styles["DA_Body"]
            ))

    doc.build(story)
    return out.getvalue()

def build_pdf(
    title: str,
    location: str,
    analysis_text: str,
    sources,
    include_cover: bool = True,
    cover_pdf_bytes: bytes | None = None,
) -> bytes:
    """Build the final PDF.

    If a client-supplied cover PDF is provided, its FIRST page is preserved exactly
    as page 1. Otherwise the institutional fallback cover is generated. Content pages
    keep the existing official folha-tipo.
    """
    content_bytes = _content_pdf(title, location, analysis_text, sources)
    content_reader = PdfReader(BytesIO(content_bytes))
    writer = PdfWriter()

    if include_cover:
        if cover_pdf_bytes:
            try:
                supplied = PdfReader(BytesIO(cover_pdf_bytes))
                if not supplied.pages:
                    raise ValueError("O PDF de capa não contém páginas.")
                writer.add_page(supplied.pages[0])
            except Exception as exc:
                raise ValueError(f"Capa PDF inválida: {exc}") from exc
        else:
            fallback_cover = PdfReader(BytesIO(_cover_pdf(title, location)))
            writer.add_page(fallback_cover.pages[0])

    if TEMPLATE.exists():
        template_bytes = TEMPLATE.read_bytes()
        for content_page in content_reader.pages:
            # Fresh reader/page for each merge: pypdf mutates the page object.
            base_reader = PdfReader(BytesIO(template_bytes))
            base_page = base_reader.pages[0]
            base_page.merge_page(content_page)
            writer.add_page(base_page)
    else:
        for content_page in content_reader.pages:
            writer.add_page(content_page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()

