from __future__ import annotations
import base64, json, hashlib
from pathlib import Path
import pandas as pd
import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from core.config import APP_USER, APP_PASSWORD, GEMINI_MODEL
from core.geocode import geocode_location
from core.utils import polygon_area_m2
from core.engine import UrbanEngine
from core.calculations import calculate_capacity
from core.reporting import build_pdf

ROOT=Path(__file__).parent; LOGO=ROOT/'assets'/'logo.png'; ICON=ROOT/'assets'/'icon_logo.png'
st.set_page_config(page_title='doisarquitectos | Viabilidade V3',page_icon=str(ICON),layout='wide')
st.markdown('''<style>
.block-container{padding-top:1.15rem;max-width:1500px}.brand{display:flex;align-items:center;gap:28px;margin:4px 0 20px}.brand img{width:190px;height:auto;object-fit:contain}.brand h1{font:800 2.25rem/1.25 Arial;margin:0;color:#20252b}.brand p{margin:4px 0 0;color:#66737a}.login{max-width:560px;margin:2rem auto}.login img{width:min(420px,90%);height:auto;display:block;margin:0 auto 20px;object-fit:contain}.card{background:#f6f9fa;border:1px solid #dfe7e9;border-radius:12px;padding:14px}.pill{display:inline-block;border-radius:999px;padding:4px 9px;background:#eef4f5;font-size:.78rem}.good{color:#167a3e}.warn{color:#a96b00}.bad{color:#b42318}.muted{color:#66737a;font-size:.88rem} div[data-testid="stMetricValue"]{font-size:1.75rem}</style>''',unsafe_allow_html=True)

def uri(p):
    return 'data:image/png;base64,'+base64.b64encode(Path(p).read_bytes()).decode() if Path(p).exists() else ''
def brand():
    st.markdown(f'<div class="brand"><img src="{uri(LOGO)}"><div><h1>Estudo Inteligente de Viabilidade</h1><p>Localização → documentos → checklist urbanística → potencial construtivo.</p></div></div>',unsafe_allow_html=True)

def init():
    defaults={
      'auth':False,'step':1,'location_text':'','geo':None,'polygon':None,'polygon_area':None,'area_m2':None,'area_confirmed':False,
      'documents':None,'research':None,'calculations':None,'potential':None,'uploaded_names':[]
    }
    for k,v in defaults.items(): st.session_state.setdefault(k,v)

def reset_after_location():
    for k in ['documents','research','calculations','potential','area_m2','area_confirmed','uploaded_names']:
        st.session_state[k]=None if k not in ['area_confirmed','uploaded_names'] else (False if k=='area_confirmed' else [])

def login():
    st.markdown(f'<div class="login"><img src="{uri(LOGO)}"></div>',unsafe_allow_html=True)
    st.markdown('<h2 style="text-align:center">Acesso ao estudo de viabilidade</h2>',unsafe_allow_html=True)
    c1,c2,c3=st.columns([1,1.3,1]);
    with c2:
        u=st.text_input('Utilizador'); p=st.text_input('Password',type='password')
        if st.button('Entrar',type='primary',use_container_width=True):
            if u==APP_USER and p==APP_PASSWORD: st.session_state.auth=True; st.rerun()
            else: st.error('Credenciais inválidas.')

def sidebar():
    st.sidebar.subheader('Estudo')
    labels=['1. Localização','2. Documentação','3. Análise urbanística','4. Relatório']
    for i,l in enumerate(labels,1):
        done=(i==1 and bool(st.session_state.geo or st.session_state.location_text)) or (i==2 and st.session_state.step>2) or (i==3 and bool(st.session_state.research)) or (i==4 and bool(st.session_state.potential))
        prefix='✅ ' if done else '○ '
        if st.sidebar.button(prefix+l,use_container_width=True,key=f'nav{i}'): st.session_state.step=i; st.rerun()
    st.sidebar.divider(); st.sidebar.caption(f'IA: {GEMINI_MODEL} · V3.0')
    if st.sidebar.button('↻ Novo estudo / limpar dados',use_container_width=True):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()
    if st.sidebar.button('Sair'):
        st.session_state.auth=False; st.rerun()

def step1():
    st.header('1. Localização do terreno')
    st.write('Identifique o terreno por morada/local, confirme no mapa e desenhe as estremas se souber. A documentação não é obrigatória.')
    c1,c2=st.columns([2,1])
    with c1:
        q=st.text_input('Morada / rua / lugar / referência',value=st.session_state.location_text,placeholder='Ex.: Rua dos Juncais, Sandim, Vila Nova de Gaia')
    with c2:
        if st.button('🔎 Localizar',type='primary',use_container_width=True):
            if q.strip()!=st.session_state.location_text: reset_after_location()
            st.session_state.location_text=q.strip(); st.session_state.geo=geocode_location(q)
            if not st.session_state.geo: st.warning('Não foi possível geocodificar automaticamente. Pode posicionar/desenhar no mapa e preencher município/freguesia abaixo.')
            st.rerun()
    geo=st.session_state.geo or {}; lat=geo.get('lat',40.6405); lon=geo.get('lon',-8.6538)
    m=folium.Map(location=[lat,lon],zoom_start=17 if geo else 13,tiles='OpenStreetMap')
    if geo: folium.Marker([lat,lon],tooltip=geo.get('display_name','Local encontrado')).add_to(m)
    Draw(export=False,draw_options={'polyline':False,'rectangle':True,'circle':False,'circlemarker':False,'marker':False},edit_options={'edit':True}).add_to(m)
    out=st_folium(m,height=490,use_container_width=True,key='map')
    drawings=(out or {}).get('all_drawings') or []
    if drawings:
        g=drawings[-1].get('geometry') or {}; coords=[]
        if g.get('type')=='Polygon':
            ring=(g.get('coordinates') or [[]])[0]; coords=[(x[1],x[0]) for x in ring[:-1]]
        if coords:
            area=polygon_area_m2(coords); st.session_state.polygon=coords; st.session_state.polygon_area=area
    c1,c2,c3=st.columns(3)
    with c1: municipality=st.text_input('Município',value=geo.get('municipality',''))
    with c2: parish=st.text_input('Freguesia / localidade',value=geo.get('parish',''))
    with c3: district=st.text_input('Distrito',value=geo.get('district',''))
    st.session_state['manual_admin']={'municipality':municipality,'parish':parish,'district':district}
    if st.session_state.polygon_area: st.success(f'Área cartográfica do polígono: {st.session_state.polygon_area:,.1f} m². Pode ser corrigida mais tarde.')
    if st.button('Continuar para documentação →',type='primary'):
        st.session_state.step=2; st.rerun()

def human_doc(doc):
    st.markdown(f"**{doc.get('filename','Documento')}** — {doc.get('type','não identificado')} · confiança {doc.get('confidence',0)}%")
    ev=doc.get('evidence') or []
    if ev:
        for e in ev[:8]: st.write(f"• {e.get('item','')}: **{e.get('value','')}**" + (f" (p. {e.get('page')})" if e.get('page') else ''))
    for w in doc.get('warnings') or []: st.warning(w)

def step2():
    st.header('2. Documentação disponível (opcional)')
    st.write('Carregue apenas o que o cliente/gabinete já possui. A aplicação pesquisará automaticamente PDM, REN, RAN, condicionantes e legislação na etapa seguinte.')
    files=st.file_uploader('PDF, PNG ou JPG',type=['pdf','png','jpg','jpeg'],accept_multiple_files=True)
    c1,c2=st.columns([1,1])
    with c1:
        analyze=st.button('🧠 Analisar documentos',type='primary',disabled=not files,use_container_width=True)
    with c2:
        skip=st.button('Continuar sem documentação →',use_container_width=True)
    if analyze:
        with st.status('A ler e extrair evidências dos documentos...',expanded=True) as status:
            try:
                engine=UrbanEngine(); st.session_state.documents=engine.analyze_documents(files); st.session_state.uploaded_names=[f.name for f in files]
                status.update(label='Documentação analisada',state='complete')
            except Exception as e:
                status.update(label='Falha na análise documental',state='error'); st.error(str(e))
    if st.session_state.documents:
        st.success('Evidências extraídas. Nada de JSON interno é mostrado ao utilizador.')
        for d in st.session_state.documents.get('documents') or []:
            with st.expander(d.get('filename','Documento'),expanded=False): human_doc(d)
        combined=st.session_state.documents.get('combined') or {}; areas=combined.get('area_candidates_m2') or []
        if areas: st.info('Áreas identificadas nos documentos: '+', '.join(str(x) for x in areas))
    if skip:
        st.session_state.step=3; st.rerun()
    if st.session_state.documents and st.button('Continuar para análise urbanística →',type='primary'):
        st.session_state.step=3; st.rerun()

def build_context():
    geo=st.session_state.geo or {}; admin=st.session_state.get('manual_admin') or {}
    docs=st.session_state.documents or {"documents":[],"combined":{}}
    return {
      'location_text':st.session_state.location_text,
      'municipality':admin.get('municipality') or geo.get('municipality',''),
      'parish':admin.get('parish') or geo.get('parish',''),
      'district':admin.get('district') or geo.get('district',''),
      'lat':geo.get('lat'),'lon':geo.get('lon'),'polygon':st.session_state.polygon,
      'area_m2':st.session_state.area_m2,'document_evidence':docs.get('combined') or {},
      'documents_summary':[{'filename':d.get('filename'),'type':d.get('type'),'planning':d.get('planning'),'constraints':d.get('constraints'),'evidence':d.get('evidence')} for d in docs.get('documents') or []]
    }

def area_controls():
    docs=st.session_state.documents or {}; combined=docs.get('combined') or {}; opts=[]
    for x in combined.get('area_candidates_m2') or []:
        try: v=float(x.get('value') if isinstance(x,dict) else x); opts.append((f'{v:,.1f} m² — documento',v))
        except Exception: pass
    if st.session_state.polygon_area: opts.append((f'{st.session_state.polygon_area:,.1f} m² — polígono no mapa',float(st.session_state.polygon_area)))
    opts.append(('Introduzir/editar manualmente',None)); labels=[x[0] for x in opts]
    selected=st.selectbox('Referência de área',labels,index=0 if len(opts)>1 else len(opts)-1)
    default=next((v for l,v in opts if l==selected),None) or st.session_state.area_m2 or 0.0
    area=st.number_input('Área do terreno a considerar (m²)',min_value=0.0,value=float(default),step=1.0)
    confirm=st.checkbox('Confirmo esta área para os cálculos',value=bool(st.session_state.area_confirmed))
    if confirm and area>0:
        st.session_state.area_m2=float(area); st.session_state.area_confirmed=True; st.success(f'Área confirmada: {area:,.1f} m².')
    return area,confirm

def status_badge(s):
    return {'confirmed':'✅ Confirmado','probable':'🟡 Provável','not_found':'⚪ Não encontrado','conflict':'🔴 Conflito'}.get(s,str(s))

def table_group(group):
    rows=[]
    for k,v in group.items():
        if not isinstance(v,dict):continue
        rows.append({'Item':k.replace('_',' '),'Resultado':v.get('value') or '—','Estado':status_badge(v.get('status')),'Confiança':f"{v.get('confidence',0)}%",'Artigo/Mapa':v.get('article_or_map',''),'Ref.':' '.join(f'[{x}]' for x in v.get('refs') or [])})
    return pd.DataFrame(rows)

def readiness(research):
    items=[]
    for g in ['planning','parameters','uses','constraints']:
        items+=list((research.get(g) or {}).values())
    scored=[x for x in items if isinstance(x,dict) and x.get('status') in ['confirmed','probable']]
    confirmed=[x for x in items if isinstance(x,dict) and x.get('status')=='confirmed']
    avg=sum(int(x.get('confidence') or 0) for x in scored)/len(scored) if scored else 0
    return round(avg),len(confirmed),len(scored),len(items)

def step3():
    st.header('3. Análise urbanística automática')
    ctx=build_context();
    c1,c2,c3=st.columns(3); c1.metric('Município',ctx.get('municipality') or 'A confirmar'); c2.metric('Freguesia/localidade',ctx.get('parish') or 'A confirmar'); c3.metric('Rua/local',ctx.get('location_text') or 'A confirmar')
    st.subheader('Área do terreno'); area_controls()
    st.markdown('#### Checklist automática obrigatória')
    st.caption('A aplicação verifica individualmente PDM/PU/PP/loteamento, classificação do solo, usos, índices, implantação, impermeabilização, pisos/cércea, afastamentos, estacionamento, REN, RAN, água, cheias, incêndio, ruído, património, Natura 2000, estradas, ferrovia, aeroporto, eletricidade, gasodutos, redes e demais servidões.')
    if st.button('🌐 Executar análise urbanística',type='primary',disabled=not bool(st.session_state.location_text)):
        ctx=build_context();
        prog=st.progress(0,text='A iniciar as quatro verificações em paralelo...')
        def cb(done,total,name): prog.progress(done/total,text=f'{done}/{total} — {name}: concluído')
        try:
            engine=UrbanEngine(); research=engine.research(ctx,progress_cb=cb); st.session_state.research=research
            calc=calculate_capacity(st.session_state.area_m2 if st.session_state.area_confirmed else None,research.get('parameters') or {}); st.session_state.calculations=calc
            st.session_state.potential=engine.potential(ctx,research,calc); prog.progress(1.0,text='Análise concluída')
        except Exception as e: st.error(str(e))
    if st.session_state.research:
        r=st.session_state.research; score,confirmed,usable,total=readiness(r); p=st.session_state.potential or {}
        st.divider(); st.subheader('Resultado executivo')
        m1,m2,m3,m4=st.columns(4); m1.metric('Confiança média',f'{score}%'); m2.metric('Itens confirmados',confirmed); m3.metric('Itens utilizáveis',usable); m4.metric('Checklist total',total)
        verdict=(p.get('verdict') or 'inconclusiva').replace('_',' ').title(); st.info(f"**Viabilidade preliminar: {verdict}** — {p.get('headline','')}")
        tabs=st.tabs(['Instrumentos e solo','Usos','Parâmetros','Condicionantes','Capacidade','Fontes'])
        groups=['planning','uses','parameters','constraints']
        for tab,g in zip(tabs[:4],groups):
            with tab: st.dataframe(table_group(r.get(g) or {}),use_container_width=True,hide_index=True)
        with tabs[4]:
            calc=st.session_state.calculations or {}; 
            if calc.get('results'):
                for k,v in calc['results'].items(): st.metric(k.replace('_',' ').title(),f'{v:,.2f} m²' if 'm2' in k else v)
            else: st.warning('Ainda faltam parâmetros quantitativos suficientes. A análise qualitativa e o relatório continuam disponíveis.')
            if p.get('best_uses'): st.write('**Usos com melhor potencial:** '+', '.join(p['best_uses']))
            if p.get('missing_critical_items'):
                st.write('**Elementos críticos em falta:**'); [st.write('• '+x) for x in p['missing_critical_items']]
        with tabs[5]:
            for s in r.get('sources') or []: st.markdown(f"[{s['ref']}] [{s.get('title') or s['url']}]({s['url']})" + (' — **oficial**' if s.get('official') else ''))
        if st.button('Gerar relatório →',type='primary'): st.session_state.step=4; st.rerun()

def step4():
    st.header('4. Relatório de viabilidade')
    if not st.session_state.research:
        st.info('Execute primeiro a análise urbanística.'); return
    p=st.session_state.potential or {}; r=st.session_state.research; c=st.session_state.calculations or {}; ctx=build_context(); ctx['area_m2']=st.session_state.area_m2
    st.subheader((p.get('headline') or 'Estudo preliminar de viabilidade'))
    st.write(f"**Conclusão:** {(p.get('verdict') or 'inconclusiva').replace('_',' ').title()} · **Confiança:** {p.get('confidence',0)}%")
    st.write(p.get('capacity_summary') or 'Capacidade quantitativa condicionada aos parâmetros confirmados.')
    if p.get('recommended_next_actions'):
        st.write('**Próximas validações recomendadas:**'); [st.write('• '+x) for x in p['recommended_next_actions']]
    pdf=build_pdf(ctx,r,c,p,logo_path=LOGO)
    st.download_button('📄 Descarregar relatório PDF',data=pdf,file_name='estudo_viabilidade_doisarquitectos.pdf',mime='application/pdf',type='primary')

init()
if not st.session_state.auth: login(); st.stop()
brand(); sidebar()
{1:step1,2:step2,3:step3,4:step4}.get(st.session_state.step,step1)()
