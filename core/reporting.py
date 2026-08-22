from __future__ import annotations
from io import BytesIO
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

STATUS_LABEL = {
    "confirmado": "CONFIRMADO", "calculado": "CALCULADO", "interpretacao": "INTERPRETAÇÃO",
    "a_confirmar": "A CONFIRMAR", "conflito": "CONFLITO"
}

BASE_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = BASE_DIR / "assets" / "logo.png"

FOOTER_LINE_1 = "doisarquitectos  |  Praceta Dr. Alberto Souto n.º 42, 3800-147 Aveiro  |  tlm: 910 002 022*  |  info@doisarquitectos.com  |  www.doisarquitectos.com"
FOOTER_LINE_2 = "*chamada para rede móvel nacional"


def _esc(text):
    return str(text or "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _p(text, style):
    return Paragraph(_esc(text), style)


def _brand_page(canvas, doc):
    """Reproduz a lógica gráfica da folha-tipo fornecida: logo no topo direito e rodapé institucional."""
    w, h = A4
    canvas.saveState()
    # Logo superior direito, sem deformar nem cortar.
    if LOGO_PATH.exists():
        img = ImageReader(str(LOGO_PATH))
        iw, ih = img.getSize()
        target_w = 112
        target_h = target_w * ih / iw
        x = w - 48 - target_w
        y = h - 44 - target_h
        canvas.drawImage(img, x, y, width=target_w, height=target_h, preserveAspectRatio=True, mask='auto')
    # Rodapé inspirado diretamente na folha-tipo.
    y_line = 35
    canvas.setStrokeColor(colors.HexColor("#8A8A8A"))
    canvas.setLineWidth(0.45)
    canvas.line(54, y_line + 15, w - 54, y_line + 15)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.setFont("Helvetica", 6.5)
    canvas.drawCentredString(w / 2, y_line + 5, FOOTER_LINE_1)
    canvas.setFont("Helvetica", 6.1)
    canvas.drawCentredString(w / 2, y_line - 5, FOOTER_LINE_2)
    canvas.restoreState()


def _table(data, widths, styles, header=True):
    t = Table([[_p(c, styles["Small"]) for c in row] for row in data], colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#C8C8C8")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]
    if header:
        commands += [("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F0F0F0")), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold")]
    t.setStyle(TableStyle(commands))
    return t


def build_pdf(study: dict) -> bytes:
    buf = BytesIO()
    # Margens deixam espaço para o logótipo e o rodapé da folha-tipo.
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=48, leftMargin=48, topMargin=88, bottomMargin=66,
                            title="Estudo Preliminar de Viabilidade Urbanística", author="doisarquitectos")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.7, leading=10.2, textColor=colors.HexColor("#333333")))
    styles.add(ParagraphStyle(name="BodyDA", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.3, leading=13.2, spaceAfter=4))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13.5, leading=17, spaceBefore=11, spaceAfter=7, textColor=colors.HexColor("#222222")))
    styles.add(ParagraphStyle(name="TitleDA", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=21, leading=27, alignment=TA_LEFT, textColor=colors.HexColor("#202020")))
    styles.add(ParagraphStyle(name="CoverSub", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, leading=14, textColor=colors.HexColor("#666666")))
    styles.add(ParagraphStyle(name="CenterSmall", parent=styles["Small"], alignment=TA_CENTER))

    story = []
    # Capa muito limpa, coerente com a folha-tipo do gabinete.
    story += [Spacer(1, 115), _p("ESTUDO PRELIMINAR DE VIABILIDADE URBANÍSTICA", styles["TitleDA"]), Spacer(1, 14)]
    if study.get("location_text"):
        story.append(_p(study.get("location_text"), styles["Heading2"]))
    ref = study.get("study_ref") or "-"
    client = study.get("client_name") or "-"
    story += [_p(f"Referência: {ref}", styles["CoverSub"]), _p(f"Cliente: {client}", styles["CoverSub"]), Spacer(1, 24),
              _p("Documento de apoio técnico preliminar. As conclusões devem ser validadas pelo arquiteto e não substituem informação municipal, PIP, licenciamento ou decisão administrativa.", styles["Small"]), PageBreak()]

    rules = study.get("rules", {}) or {}
    identification = rules.get("identification", {}) or {}
    planning = rules.get("planning", {}) or {}

    story += [_p("1. Identificação e documentação", styles["Section"])]
    area = identification.get("area_m2") or study.get("confirmed_area_m2") or study.get("estimated_area_m2")
    rows = [["Campo", "Valor"],
            ["Localização", study.get("location_text")],
            ["Município", identification.get("municipality") or study.get("municipality")],
            ["Freguesia", identification.get("parish") or study.get("parish")],
            ["Área considerada", f"{area} m²" if area else "A confirmar"],
            ["Sistema de coordenadas", identification.get("coordinate_system")],
            ["Matriz / artigo", ", ".join(map(str, identification.get("matrices", []))) or "A confirmar"]]
    story += [_table(rows, [142, 345], styles), Spacer(1, 10)]

    docs = (study.get("documents_analysis") or {}).get("documents", [])
    if docs:
        drows = [["Documento", "Tipo identificado", "Importância", "Confiança"]]
        for d in docs[:20]:
            conf = d.get("confidence")
            conf = f"{float(conf)*100:.0f}%" if isinstance(conf,(int,float)) else conf
            drows.append([d.get("filename"), d.get("document_type"), d.get("importance"), conf])
        story += [_p("Documentação analisada", styles["BodyDA"]), _table(drows,[155,150,95,87],styles), Spacer(1, 8)]

    story += [_p("2. Enquadramento territorial e urbanístico", styles["Section"])]
    prows = [["Elemento", "Resultado"],
             ["Instrumento", planning.get("instrument") or "A confirmar"],
             ["Classe do solo", planning.get("soil_class") or "A confirmar"],
             ["Categoria", planning.get("category") or "A confirmar"],
             ["Subcategoria", planning.get("subcategory") or "A confirmar"],
             ["Estado", planning.get("status") or "A confirmar"]]
    story += [_table(prows,[150,337],styles), Spacer(1,8)]

    story += [_p("3. Usos admissíveis", styles["Section"])]
    use_rows = [["Uso", "Admissibilidade", "Fundamento"]]
    for u in rules.get("uses", [])[:25]:
        use_rows.append([u.get("use"), u.get("admissibility"), u.get("basis")])
    if len(use_rows) > 1:
        story.append(_table(use_rows,[115,92,280],styles))
    else:
        story.append(_p("Sem usos confirmados na informação disponível.", styles["BodyDA"]))

    story += [_p("4. Parâmetros urbanísticos", styles["Section"])]
    p_rows = [["Parâmetro", "Valor", "Estado", "Fundamento"]]
    for k,v in (rules.get("parameters",{}) or {}).items():
        if isinstance(v,dict):
            p_rows.append([k.replace("_"," ").title(), v.get("value"), STATUS_LABEL.get(v.get("status"), v.get("status")), v.get("basis")])
    if len(p_rows) > 1:
        story.append(_table(p_rows,[122,72,88,205],styles))
    else:
        story.append(_p("Parâmetros numéricos ainda por confirmar.", styles["BodyDA"]))

    story += [_p("5. Condicionantes", styles["Section"])]
    crows = [["Condicionante", "Estado", "Impacto / observação"]]
    for c in rules.get("constraints",[])[:30]:
        crows.append([c.get("name"), c.get("status"), c.get("impact")])
    if len(crows) > 1:
        story.append(_table(crows,[130,88,269],styles))
    else:
        story.append(_p("Sem condicionantes confirmadas na informação disponível.", styles["BodyDA"]))

    story += [_p("6. Capacidade urbanística calculada", styles["Section"])]
    calc = study.get("calculations",{}) or {}
    derived = calc.get("derived",{}) or {}
    if derived:
        calcrows=[["Indicador","Resultado"]]
        for k,v in derived.items(): calcrows.append([k.replace("_"," ").title(), v])
        story.append(_table(calcrows,[240,247],styles))
    else:
        story.append(_p("Os cálculos não foram executados ou faltam parâmetros confirmados.", styles["BodyDA"]))

    story += [_p("7. Cenários preliminares", styles["Section"])]
    scenarios = study.get("scenarios",[])[:3]
    if scenarios:
        srows=[["Cenário","ABC","Implantação","Pisos","Fogos","Risco"]]
        for s in scenarios:
            srows.append([f"{s.get('code','')} - {s.get('name','')}", s.get('above_ground_gfa_m2','-'), s.get('implantation_m2','-'), s.get('floors_above_ground','-'), s.get('indicative_units','-'), s.get('risk','-')])
        story += [_table(srows,[145,70,70,50,55,97],styles), Spacer(1,8)]
        for s in scenarios:
            story += [_p(f"{s.get('code','')} - {s.get('name','')}", styles["Heading3"]), _p(s.get("concept", ""), styles["BodyDA"])]
            if s.get("warnings"):
                story.append(_p("Alertas: " + " | ".join(map(str,s.get("warnings",[]))), styles["Small"]))
    else:
        story.append(_p("Cenários ainda não gerados.", styles["BodyDA"]))

    story += [_p("8. Pontos críticos e confirmações", styles["Section"])]
    qs = list(rules.get("critical_questions",[]) or [])
    conflicts = list(rules.get("conflicts",[]) or [])
    if not qs and not conflicts:
        story.append(_p("Sem pontos críticos adicionais registados.", styles["BodyDA"]))
    for q in qs: story.append(_p(f"• {q}", styles["BodyDA"]))
    for c in conflicts: story.append(_p(f"• CONFLITO: {c}", styles["BodyDA"]))

    story += [_p("9. Fontes e referências", styles["Section"])]
    citations = (study.get("web_research",{}) or {}).get("citations",[])[:40]
    if citations:
        for i,src in enumerate(citations,1):
            story.append(_p(f"{i}. {src.get('title','')} - {src.get('url','')}", styles["Small"]))
    else:
        story.append(_p("Sem referências web estruturadas registadas.", styles["Small"]))

    doc.build(story, onFirstPage=_brand_page, onLaterPages=_brand_page)
    return buf.getvalue()
