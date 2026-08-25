from io import BytesIO
from pathlib import Path
from datetime import datetime
import html
import re
import tempfile

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether
from reportlab.lib import colors
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "folha_tipo.pdf"

def _fmt(s: str) -> str:
    s = html.escape(s or "")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    # Never show raw LaTeX in final PDF.
    s = re.sub(r'\$+', '', s)
    s = re.sub(r'\\text\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', s)
    return s

def _parse(text: str):
    for raw in text.splitlines():
        line = raw.strip()
        if line and re.fullmatch(r"[=\-_]{8,}", line):
            continue
        if not line:
            yield ("space", "")
        elif line.startswith("### "):
            yield ("h3", line[4:])
        elif line.startswith("## "):
            yield ("h2", line[3:])
        elif line.startswith("# "):
            yield ("h1", line[2:])
        elif line.startswith("|") and line.endswith("|"):
            yield ("table", line)
        elif line.startswith(("- ", "* ")):
            yield ("bullet", line[2:])
        else:
            yield ("p", line)

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

def build_pdf(title: str, location: str, analysis_text: str, sources) -> bytes:
    content_bytes = _content_pdf(title, location, analysis_text, sources)

    # Merge every generated page over the official folha-tipo.
    if not TEMPLATE.exists():
        return content_bytes

    template_reader = PdfReader(str(TEMPLATE))
    content_reader = PdfReader(BytesIO(content_bytes))
    writer = PdfWriter()

    template_page = template_reader.pages[0]

    for content_page in content_reader.pages:
        # Clone through a fresh reader page so each merge is independent.
        base_reader = PdfReader(str(TEMPLATE))
        base_page = base_reader.pages[0]
        base_page.merge_page(content_page)
        writer.add_page(base_page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()
