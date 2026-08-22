from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
import re
import html
from datetime import datetime

def _clean_markdown(text: str) -> list[tuple[str,str]]:
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            out.append(("space",""))
            continue
        if line.startswith("### "):
            out.append(("h3", line[4:]))
        elif line.startswith("## "):
            out.append(("h2", line[3:]))
        elif line.startswith("# "):
            out.append(("h1", line[2:]))
        elif line.startswith("|") and line.endswith("|"):
            out.append(("tableline", line))
        elif line.startswith(("- ", "* ")):
            out.append(("bullet", line[2:]))
        else:
            out.append(("p", line))
    return out

def _fmt(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    return s

def build_pdf(title: str, location: str, analysis_text: str, sources: list[dict] | list) -> bytes:
    buff = BytesIO()
    doc = SimpleDocTemplate(
        buff, pagesize=A4,
        rightMargin=18*mm, leftMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title=title,
        author="doisarquitetos"
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleDA", parent=styles["Title"], fontSize=20, leading=24, spaceAfter=8, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="SubDA", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#6B7280"), alignment=TA_CENTER, spaceAfter=18))
    styles.add(ParagraphStyle(name="H2DA", parent=styles["Heading2"], fontSize=14, leading=18, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="H3DA", parent=styles["Heading3"], fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle(name="BodyDA", parent=styles["BodyText"], fontSize=9.5, leading=14, spaceAfter=5))
    styles.add(ParagraphStyle(name="BulletDA", parent=styles["BodyText"], fontSize=9.5, leading=14, leftIndent=12, bulletIndent=2, spaceAfter=3))

    story = [
        Paragraph(_fmt(title), styles["TitleDA"]),
        Paragraph(_fmt(location), styles["SubDA"]),
        Paragraph(f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["SubDA"]),
        Spacer(1, 5*mm)
    ]

    parsed = _clean_markdown(analysis_text)
    table_buffer = []

    def flush_table():
        nonlocal table_buffer
        if not table_buffer:
            return
        rows = []
        for ln in table_buffer:
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            rows.append([Paragraph(_fmt(c), styles["BodyDA"]) for c in cells])
        if rows:
            t = Table(rows, repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#D1D5DB")),
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#F3F4F6")),
                ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("LEFTPADDING",(0,0),(-1,-1),5),
                ("RIGHTPADDING",(0,0),(-1,-1),5),
                ("TOPPADDING",(0,0),(-1,-1),4),
                ("BOTTOMPADDING",(0,0),(-1,-1),4),
            ]))
            story.append(t)
            story.append(Spacer(1, 4*mm))
        table_buffer = []

    for kind, value in parsed:
        if kind == "tableline":
            table_buffer.append(value)
            continue
        flush_table()
        if kind == "space":
            story.append(Spacer(1, 2*mm))
        elif kind == "h1":
            story.append(Paragraph(_fmt(value), styles["Heading1"]))
        elif kind == "h2":
            story.append(Paragraph(_fmt(value), styles["H2DA"]))
        elif kind == "h3":
            story.append(Paragraph(_fmt(value), styles["H3DA"]))
        elif kind == "bullet":
            story.append(Paragraph(_fmt(value), styles["BulletDA"], bulletText="•"))
        else:
            story.append(Paragraph(_fmt(value), styles["BodyDA"]))
    flush_table()

    if sources:
        story.append(PageBreak())
        story.append(Paragraph("Links efetivamente acedidos pelo motor", styles["H2DA"]))
        story.append(Paragraph(
            "Esta lista é extraída das citações URL devolvidas pela API durante a execução com pesquisa web.",
            styles["BodyDA"]
        ))
        for i, s in enumerate(sources, start=1):
            title_s = getattr(s, "title", None) or (s.get("title") if isinstance(s, dict) else "Fonte")
            url_s = getattr(s, "url", None) or (s.get("url") if isinstance(s, dict) else "")
            story.append(Paragraph(f"[{i}] <b>{_fmt(title_s)}</b><br/><link href='{html.escape(url_s)}'>{html.escape(url_s)}</link>", styles["BodyDA"]))

    doc.build(story)
    return buff.getvalue()
