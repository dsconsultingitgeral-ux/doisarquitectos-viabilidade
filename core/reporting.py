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
    "a_confirmar": "A CONFIRMAR", "conflito": "CONFLITO", "confirmado_utilizador":"CONFIRMADO PELO ARQUITETO"
}
PARAM_LABELS = {
    "utilization_index": "Índice de utilização / edificabilidade",
    "occupation_index": "Índice de ocupação / implantação",
    "impermeability_index": "Impermeabilização",
    "max_height_m": "Altura / cércea máxima",
    "max_floors_above_ground": "Pisos máximos acima do solo",
    "max_floors_below_ground": "Pisos máximos abaixo do solo",
    "front_setback_m": "Afastamento frontal",
    "side_setback_m": "Afastamento lateral",
    "rear_setback_m": "Afastamento posterior",
    "parking_rule": "Regra de estacionamento",
}
CALC_LABELS = {
    "max_above_ground_gfa_by_utilization_m2":"ABC máxima pelo índice de utilização",
    "max_footprint_by_occupation_m2":"Área máxima de implantação",
    "max_impermeable_area_m2":"Área máxima impermeabilizada",
    "simple_volume_ceiling_m2":"Teto geométrico simples por pisos",
}

BASE_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = BASE_DIR / "assets" / "logo.png"
FOOTER_LINE_1 = "doisarquitectos  |  Praceta Dr. Alberto Souto n.º 42, 3800-147 Aveiro  |  tlm: 910 002 022*  |  info@doisarquitectos.com  |  www.doisarquitectos.com"
FOOTER_LINE_2 = "*chamada para rede móvel nacional"


def _esc(text):
    return str(text or "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _p(text, style):
    return Paragraph(_esc(text), style)

def _refs(value):
    if not value:
        return ""
    vals=value if isinstance(value,list) else [value]
    out=[]
    for v in vals:
        if isinstance(v,dict):
            v=v.get("ref") or v.get("label") or v.get("url")
        if isinstance(v,int): v=f"[{v}]"
        txt=str(v)
        if txt.isdigit(): txt=f"[{txt}]"
        if txt and txt not in out: out.append(txt)
    return " ".join(out)

def _safe(v):
    return "A confirmar" if v in (None,"","None") else v

def _brand_page(canvas, doc):
    w, h = A4
    canvas.saveState()
    if LOGO_PATH.exists():
        img = ImageReader(str(LOGO_PATH))
        iw, ih = img.getSize()
        target_w = 112
        target_h = target_w * ih / iw
        x = w - 48 - target_w
        y = h - 44 - target_h
        canvas.drawImage(img, x, y, width=target_w, height=target_h, preserveAspectRatio=True, mask='auto')
    y_line = 35
    canvas.setStrokeColor(colors.HexColor("#8A8A8A")); canvas.setLineWidth(0.45)
    canvas.line(54, y_line + 15, w - 54, y_line + 15)
    canvas.setFillColor(colors.HexColor("#666666")); canvas.setFont("Helvetica", 6.5)
    canvas.drawCentredString(w / 2, y_line + 5, FOOTER_LINE_1)
    canvas.setFont("Helvetica", 6.1); canvas.drawCentredString(w / 2, y_line - 5, FOOTER_LINE_2)
    canvas.restoreState()

def _table(data, widths, styles, header=True):
    t = Table([[_p(c, styles["Small"]) for c in row] for row in data], colWidths=widths, repeatRows=1 if header else 0)
    commands=[
        ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#C8C8C8")),("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]
    if header: commands += [("BACKGROUND",(0,0),(-1,0),colors.HexColor("#F0F0F0")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold")]
    t.setStyle(TableStyle(commands)); return t


def build_pdf(study: dict) -> bytes:
    buf=BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=48,leftMargin=48,topMargin=88,bottomMargin=66,
                          title="Estudo Preliminar de Viabilidade Urbanística",author="doisarquitectos")
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small",parent=styles["BodyText"],fontName="Helvetica",fontSize=7.5,leading=10,textColor=colors.HexColor("#333333")))
    styles.add(ParagraphStyle(name="BodyDA",parent=styles["BodyText"],fontName="Helvetica",fontSize=9.2,leading=13,spaceAfter=4))
    styles.add(ParagraphStyle(name="Section",parent=styles["Heading2"],fontName="Helvetica-Bold",fontSize=13.5,leading=17,spaceBefore=11,spaceAfter=7,textColor=colors.HexColor("#222222")))
    styles.add(ParagraphStyle(name="TitleDA",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=21,leading=27,alignment=TA_LEFT,textColor=colors.HexColor("#202020")))
    styles.add(ParagraphStyle(name="CoverSub",parent=styles["BodyText"],fontName="Helvetica",fontSize=10,leading=14,textColor=colors.HexColor("#666666")))
    styles.add(ParagraphStyle(name="CenterSmall",parent=styles["Small"],alignment=TA_CENTER))

    rules=study.get("rules",{}) or {}; identification=rules.get("identification",{}) or {}; planning=rules.get("planning",{}) or {}
    citations=(study.get("web_research",{}) or {}).get("citations",[]) or []
    story=[Spacer(1,115),_p("ESTUDO PRELIMINAR DE VIABILIDADE URBANÍSTICA",styles["TitleDA"]),Spacer(1,14)]
    if study.get("location_text"): story.append(_p(study.get("location_text"),styles["Heading2"]))
    story += [_p(f"Referência: {study.get('study_ref') or '-'}",styles["CoverSub"]),_p(f"Cliente: {study.get('client_name') or '-'}",styles["CoverSub"]),Spacer(1,24),
              _p("Documento de apoio técnico preliminar. As conclusões devem ser validadas pelo arquiteto e não substituem informação municipal, PIP, licenciamento ou decisão administrativa.",styles["Small"]),PageBreak()]

    story += [_p("1. Identificação e documentação",styles["Section"])]
    area=study.get("confirmed_area_m2") or identification.get("area_m2") or study.get("estimated_area_m2")
    rows=[["Campo","Valor","Ref."],
          ["Rua / localização",identification.get("street_or_place") or study.get("location_text"),_refs(identification.get("sources"))],
          ["Município",identification.get("municipality") or study.get("municipality"),_refs(identification.get("sources"))],
          ["Freguesia / localidade",identification.get("parish") or study.get("parish"),_refs(identification.get("sources"))],
          ["Área considerada",f"{area:,.1f} m²" if isinstance(area,(int,float)) else "A confirmar","—"],
          ["Sistema de coordenadas",identification.get("coordinate_system") or "A confirmar",_refs(identification.get("sources"))],
          ["Matriz / artigo",", ".join(map(str,identification.get("matrices",[]))) or "A confirmar",_refs(identification.get("sources"))]]
    story += [_table(rows,[128,310,49],styles),Spacer(1,10)]
    docs=(study.get("documents_analysis") or {}).get("documents",[])
    if docs:
        drows=[["Documento","Tipo identificado","Importância","Confiança"]]
        for d in docs[:20]:
            conf=d.get("confidence"); conf=f"{float(conf)*100:.0f}%" if isinstance(conf,(int,float)) else conf
            drows.append([d.get("filename"),(d.get("document_type") or "").replace("_"," "),(d.get("importance") or "").replace("_"," "),conf])
        story += [_p("Documentação analisada",styles["BodyDA"]),_table(drows,[155,150,95,87],styles),Spacer(1,8)]

    story += [_p("2. Enquadramento territorial e urbanístico",styles["Section"])]
    pref=_refs(planning.get("sources"))
    prows=[["Elemento","Resultado","Ref."],
           ["Instrumento",planning.get("instrument") or "A confirmar",pref],
           ["Versão / vigência",planning.get("version") or "A confirmar",pref],
           ["Classe do solo",planning.get("soil_class") or "A confirmar",pref],
           ["Categoria",planning.get("category") or "A confirmar",pref],
           ["Subcategoria",planning.get("subcategory") or "A confirmar",pref],
           ["Estado",STATUS_LABEL.get(planning.get("status"),planning.get("status") or "A confirmar"),pref]]
    story += [_table(prows,[140,298,49],styles),Spacer(1,8)]
    if planning.get("basis"): story.append(_p(f"Fundamento: {planning.get('basis')} {pref}",styles["Small"]))

    story += [_p("3. Usos admissíveis",styles["Section"])]
    use_rows=[["Uso","Admissibilidade","Fundamento","Ref."]]
    for u in rules.get("uses",[])[:25]:
        use_rows.append([u.get("use"),STATUS_LABEL.get(u.get("admissibility"),u.get("admissibility") or "A confirmar"),u.get("basis"),_refs(u.get("sources"))])
    story.append(_table(use_rows,[100,88,250,49],styles) if len(use_rows)>1 else _p("Sem usos confirmados na informação disponível.",styles["BodyDA"]))

    story += [_p("4. Parâmetros urbanísticos",styles["Section"])]
    p_rows=[["Parâmetro","Valor","Estado","Fundamento","Ref."]]
    for k,v in (rules.get("parameters",{}) or {}).items():
        if isinstance(v,dict):
            val=_safe(v.get("value")); unit=v.get("unit") or ""
            if val!="A confirmar" and unit: val=f"{val} {unit}"
            p_rows.append([PARAM_LABELS.get(k,k.replace("_"," ").title()),val,STATUS_LABEL.get(v.get("status"),v.get("status") or "A confirmar"),v.get("basis"),_refs(v.get("sources"))])
    story.append(_table(p_rows,[115,65,78,180,49],styles) if len(p_rows)>1 else _p("Parâmetros numéricos ainda por confirmar.",styles["BodyDA"]))

    story += [_p("5. Condicionantes",styles["Section"])]
    crows=[["Condicionante","Estado","Impacto / fundamento","Ref."]]
    for c in rules.get("constraints",[])[:30]:
        impact=" | ".join(x for x in [c.get("impact"),c.get("basis")] if x)
        crows.append([c.get("name"),STATUS_LABEL.get(c.get("status"),c.get("status") or "A confirmar"),impact,_refs(c.get("sources"))])
    story.append(_table(crows,[110,83,245,49],styles) if len(crows)>1 else _p("Sem condicionantes confirmadas na informação disponível.",styles["BodyDA"]))

    story += [_p("6. Capacidade urbanística calculada",styles["Section"])]
    calc=study.get("calculations",{}) or {}; derived=calc.get("derived",{}) or {}
    if derived:
        calcrows=[["Indicador","Resultado"]]
        for k,v in derived.items(): calcrows.append([CALC_LABELS.get(k,k.replace("_"," ").title()),f"{v:,.1f} m²" if isinstance(v,(int,float)) else v])
        story.append(_table(calcrows,[300,187],styles))
        for n in calc.get("notes",[]) or []: story.append(_p(n,styles["Small"]))
    else: story.append(_p("Não existem cálculos quantitativos: faltam parâmetros regulamentares confirmados.",styles["BodyDA"]))

    story += [_p("7. Cenários preliminares",styles["Section"])]
    scenarios=study.get("scenarios",[])[:3]
    if scenarios:
        srows=[["Cenário","ABC","Implantação","Pisos","Fogos","Risco","Ref."]]
        for sc in scenarios:
            srows.append([f"{sc.get('code','')} - {sc.get('name','')}",_safe(sc.get('above_ground_gfa_m2')),_safe(sc.get('implantation_m2')),_safe(sc.get('floors_above_ground')),_safe(sc.get('indicative_units')),sc.get('risk') or "condicionado",_refs(sc.get("references"))])
        story += [_table(srows,[120,58,58,45,45,85,40],styles),Spacer(1,8)]
        for sc in scenarios:
            story += [_p(f"{sc.get('code','')} - {sc.get('name','')}",styles["Heading3"]),_p(sc.get("concept","") or "Sem conceito quantitativo enquanto faltarem parâmetros.",styles["BodyDA"])]
            if sc.get("missing_inputs"): story.append(_p("A confirmar: " + " | ".join(map(str,sc.get("missing_inputs",[]))),styles["Small"]))
            if sc.get("warnings"): story.append(_p("Alertas: " + " | ".join(map(str,sc.get("warnings",[]))),styles["Small"]))
    else: story.append(_p("Cenários ainda não gerados.",styles["BodyDA"]))

    story += [_p("8. Pontos críticos e confirmações",styles["Section"])]
    qs=list(rules.get("critical_questions",[]) or []); conflicts=list(rules.get("conflicts",[]) or [])
    if not qs and not conflicts: story.append(_p("Sem pontos críticos adicionais registados.",styles["BodyDA"]))
    for q in qs: story.append(_p(f"• {q}",styles["BodyDA"]))
    for c in conflicts: story.append(_p(f"• CONFLITO: {c}",styles["BodyDA"]))

    story += [_p("9. Fontes e referências",styles["Section"])]
    if citations:
        for i,src in enumerate(citations,1):
            ref=src.get("ref") or i
            story.append(_p(f"[{ref}] {src.get('title','')} - {src.get('url','')}",styles["Small"]))
    else: story.append(_p("Sem referências web estruturadas registadas. Não devem ser tomadas conclusões regulamentares definitivas sem fontes oficiais.",styles["Small"]))

    doc.build(story,onFirstPage=_brand_page,onLaterPages=_brand_page)
    return buf.getvalue()
