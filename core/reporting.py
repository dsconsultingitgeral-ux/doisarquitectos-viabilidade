from __future__ import annotations
from io import BytesIO
import json
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

STATUS_LABEL = {
    "confirmado": "CONFIRMADO", "calculado": "CALCULADO", "interpretacao": "INTERPRETAÇÃO",
    "a_confirmar": "A CONFIRMAR", "conflito": "CONFLITO"
}

def _p(text, style):
    return Paragraph(str(text or "-").replace("&", "&amp;"), style)

def build_pdf(study: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8.2, leading=10.5))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=14, leading=17, spaceBefore=10, spaceAfter=7))
    styles.add(ParagraphStyle(name="Title2", parent=styles["Title"], fontSize=22, leading=26, alignment=TA_LEFT))
    story = []
    story += [_p("ESTUDO PRELIMINAR DE VIABILIDADE URBANÍSTICA", styles["Title2"]), Spacer(1, 8),
              _p(study.get("location_text", ""), styles["Heading2"]),
              _p(f"Referência: {study.get('study_ref','-')}  |  Cliente: {study.get('client_name','-')}", styles["BodyText"]), Spacer(1, 14),
              _p("Documento de apoio técnico. Não substitui validação do arquiteto, informação municipal, PIP ou decisão administrativa.", styles["Small"]), PageBreak()]

    rules = study.get("rules", {}) or {}
    identification = rules.get("identification", {}) or {}
    planning = rules.get("planning", {}) or {}
    story += [_p("1. Identificação", styles["Section"])]
    rows = [["Campo", "Valor"], ["Município", identification.get("municipality") or study.get("municipality")],
            ["Freguesia", identification.get("parish") or study.get("parish")],
            ["Área", identification.get("area_m2") or study.get("estimated_area_m2")],
            ["Sistema de coordenadas", identification.get("coordinate_system")],
            ["Matriz / artigo", ", ".join(map(str, identification.get("matrices", [])))] ]
    t = Table([[ _p(c, styles["Small"]) for c in row] for row in rows], colWidths=[150, 340])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E9F0F2")),("GRID",(0,0),(-1,-1),0.25,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP"),("PADDING",(0,0),(-1,-1),6)]))
    story += [t, Spacer(1, 12), _p("2. Enquadramento urbanístico", styles["Section"]),
              _p(f"Instrumento: {planning.get('instrument','-')}", styles["BodyText"]),
              _p(f"Classificação: {planning.get('soil_class','-')} / {planning.get('category','-')} / {planning.get('subcategory','-')}", styles["BodyText"]), Spacer(1,8)]

    story += [_p("3. Usos", styles["Section"])]
    use_rows = [["Uso","Admissibilidade","Fundamento"]]
    for u in rules.get("uses", [])[:20]:
        use_rows.append([u.get("use"), u.get("admissibility"), u.get("basis")])
    if len(use_rows)>1:
        t = Table([[ _p(c, styles["Small"]) for c in row] for row in use_rows], colWidths=[115,90,285])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E9F0F2")),("GRID",(0,0),(-1,-1),0.25,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP"),("PADDING",(0,0),(-1,-1),5)]))
        story.append(t)

    story += [_p("4. Parâmetros urbanísticos", styles["Section"])]
    p_rows = [["Parâmetro","Valor","Estado","Base"]]
    for k,v in (rules.get("parameters",{}) or {}).items():
        if isinstance(v,dict):
            p_rows.append([k.replace("_"," ").title(), v.get("value"), STATUS_LABEL.get(v.get("status"),v.get("status")), v.get("basis")])
    t = Table([[ _p(c, styles["Small"]) for c in row] for row in p_rows], colWidths=[125,75,85,205])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E9F0F2")),("GRID",(0,0),(-1,-1),0.25,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP"),("PADDING",(0,0),(-1,-1),5)]))
    story.append(t)

    story += [_p("5. Condicionantes", styles["Section"])]
    for c in rules.get("constraints",[])[:30]:
        story.append(_p(f"<b>{c.get('name','')}</b> - {c.get('status','')} - {c.get('impact','')}", styles["BodyText"]))

    story += [_p("6. Capacidade calculada", styles["Section"])]
    calc = study.get("calculations",{}) or {}
    for k,v in (calc.get("derived",{}) or {}).items():
        story.append(_p(f"{k.replace('_',' ').title()}: <b>{v}</b>", styles["BodyText"]))

    story += [_p("7. Cenários preliminares", styles["Section"])]
    for s in study.get("scenarios",[])[:3]:
        story += [_p(f"{s.get('code','')} - {s.get('name','')}", styles["Heading3"]),
                  _p(f"Risco: {s.get('risk','-')} | Implantação: {s.get('implantation_m2','-')} m² | ABC: {s.get('above_ground_gfa_m2','-')} m² | Pisos: {s.get('floors_above_ground','-')} | Fogos indicativos: {s.get('indicative_units','-')}", styles["BodyText"]),
                  _p(s.get("concept", ""), styles["BodyText"]), Spacer(1,6)]

    story += [_p("8. Pontos críticos / confirmação", styles["Section"])]
    for q in rules.get("critical_questions",[]):
        story.append(_p(f"• {q}", styles["BodyText"]))
    for c in rules.get("conflicts",[]):
        story.append(_p(f"• CONFLITO: {c}", styles["BodyText"]))

    story += [_p("9. Fontes web consultadas", styles["Section"])]
    for src in (study.get("web_research",{}) or {}).get("citations",[])[:40]:
        story.append(_p(f"{src.get('title','')} - {src.get('url','')}", styles["Small"]))

    doc.build(story)
    return buf.getvalue()
