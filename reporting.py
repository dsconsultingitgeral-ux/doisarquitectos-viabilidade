from __future__ import annotations
from io import BytesIO
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether

STATUS_PT={"confirmed":"Confirmado","probable":"Provável","not_found":"Não encontrado","conflict":"Conflito"}

def _refs(item):
    r=item.get("refs") or []
    return " ".join(f"[{x}]" for x in r)

def build_pdf(study, research, calculations, potential, logo_path=None):
    buf=BytesIO(); styles=getSampleStyleSheet()
    normal=ParagraphStyle("n",parent=styles["BodyText"],fontName="Helvetica",fontSize=9.3,leading=13,textColor=colors.HexColor("#20252b"))
    h1=ParagraphStyle("h1",parent=styles["Heading1"],fontName="Helvetica-Bold",fontSize=19,leading=23,spaceAfter=10)
    h2=ParagraphStyle("h2",parent=styles["Heading2"],fontName="Helvetica-Bold",fontSize=13,leading=16,spaceBefore=8,spaceAfter=6)
    small=ParagraphStyle("s",parent=normal,fontSize=7.4,leading=9.5,textColor=colors.HexColor("#66737a"))
    def header_footer(canvas,doc):
        canvas.saveState(); w,h=A4
        canvas.setStrokeColor(colors.HexColor("#cfd7da")); canvas.line(18*mm,15*mm,w-18*mm,15*mm)
        canvas.setFont("Helvetica",6.7); canvas.setFillColor(colors.HexColor("#5f6d72"))
        canvas.drawString(18*mm,10*mm,"doisarquitectos | Praceta Dr. Alberto Souto n.º 42, 3800-147 Aveiro | 910 002 022 | info@doisarquitectos.com | www.doisarquitectos.com")
        canvas.drawRightString(w-18*mm,10*mm,f"p. {doc.page}")
        canvas.restoreState()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=20*mm)
    story=[]
    if logo_path and Path(logo_path).exists():
        im=Image(str(logo_path),width=48*mm,height=14*mm); im.hAlign="RIGHT"; story+=[im,Spacer(1,6)]
    story += [Paragraph("ESTUDO PRELIMINAR DE VIABILIDADE URBANÍSTICA",h1),
              Paragraph(f"<b>Localização:</b> {study.get('location_text','')}",normal),
              Paragraph(f"<b>Município:</b> {study.get('municipality','')} &nbsp;&nbsp; <b>Freguesia/localidade:</b> {study.get('parish','')}",normal),
              Paragraph(f"<b>Área considerada:</b> {study.get('area_m2','—')} m²",normal),Spacer(1,10)]
    verdict=(potential or {}).get("verdict","inconclusiva").replace("_"," ").title(); conf=(potential or {}).get("confidence",0)
    story += [Paragraph("1. Resumo executivo",h2),Paragraph(f"<b>Viabilidade preliminar:</b> {verdict} &nbsp;&nbsp; <b>Confiança:</b> {conf}%",normal),Paragraph((potential or {}).get("headline","") or "Análise preliminar baseada nas evidências disponíveis.",normal)]
    for title,group in [("2. Instrumentos e classificação","planning"),("3. Usos admissíveis","uses"),("4. Parâmetros urbanísticos","parameters"),("5. Condicionantes e servidões","constraints")]:
        story.append(Paragraph(title,h2)); rows=[["Item","Resultado","Estado","Conf.","Ref."]]
        for k,v in (research.get(group) or {}).items():
            if not isinstance(v,dict): continue
            val=v.get("value") or v.get("impact") or "—"; st=STATUS_PT.get(v.get("status"),v.get("status","")); c=v.get("confidence",0)
            rows.append([Paragraph(k.replace("_"," "),small),Paragraph(str(val),small),Paragraph(st,small),str(c)+"%",_refs(v)])
        t=Table(rows,colWidths=[42*mm,62*mm,28*mm,16*mm,20*mm],repeatRows=1); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#eef3f4")),("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#d7dfe1")),("VALIGN",(0,0),(-1,-1),"TOP"),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7.3),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4)])); story.append(t)
    story.append(Paragraph("6. Capacidade calculada",h2))
    for k,v in (calculations.get("results") or {}).items(): story.append(Paragraph(f"<b>{k.replace('_',' ')}:</b> {v}",normal))
    for w in calculations.get("warnings") or []: story.append(Paragraph("• "+w,normal))
    story.append(Paragraph("7. Potencial e recomendações",h2))
    story.append(Paragraph((potential or {}).get("capacity_summary","") or "Sem capacidade quantitativa fechada nesta fase.",normal))
    for x in (potential or {}).get("best_uses",[]) or []: story.append(Paragraph("• "+str(x),normal))
    for x in (potential or {}).get("recommended_next_actions",[]) or []: story.append(Paragraph("• "+str(x),normal))
    story.append(PageBreak()); story.append(Paragraph("8. Fontes",h2))
    for s in research.get("sources") or []: story.append(Paragraph(f"[{s.get('ref')}] {s.get('title') or s.get('url')} — {s.get('url')}",small))
    story.append(Spacer(1,8)); story.append(Paragraph("Nota: estudo preliminar de apoio à decisão. Não substitui PIP, parecer municipal, projeto, levantamento topográfico ou decisão administrativa.",small))
    doc.build(story,onFirstPage=header_footer,onLaterPages=header_footer); buf.seek(0); return buf.getvalue()
