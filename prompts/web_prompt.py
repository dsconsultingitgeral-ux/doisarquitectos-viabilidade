WEB_RESEARCH_PROMPT = r'''
Faz uma PESQUISA TERRITORIAL RÁPIDA E RASTREÁVEL para um estudo preliminar em Portugal.

DADOS DO TERRENO:
{study_context}

RESUMO DOS DOCUMENTOS JÁ ANALISADOS:
{document_context}

MISSÃO:
Encontrar APENAS as fontes e regras que podem alterar a viabilidade deste terreno. Não escrevas código, pseudocódigo, fórmulas Python, SQL ou instruções de programação. Não faças cálculos de capacidade. Não produzas uma monografia.

ORDEM DE PRIORIDADE:
1. Confirmar município/freguesia e instrumento(s) territorial(is) aplicável(eis).
2. Confirmar PDM/regulamento em vigor e respetivas alterações/correções/suspensões.
3. Identificar a categoria/subcategoria do solo se houver suporte nos documentos ou nas fontes.
4. Localizar os artigos que regem: usos, edificabilidade/índices, implantação, impermeabilização, altura/cércea/pisos, afastamentos, estacionamento e demais parâmetros relevantes.
5. Verificar apenas as condicionantes plausíveis no caso: REN, RAN, água/domínio hídrico, incêndio, ruído, património, rodovia/ferrovia, rede elétrica, servidões, PU/PP/loteamento e outras efetivamente relevantes.

FONTES PREFERENCIAIS:
- Diário da República / legislação oficial
- Município / SIG / geoportal / regulamento municipal
- DGT/SNIT
- CCDR, APA, ICNF, Património Cultural, Infraestruturas de Portugal e outras entidades públicas competentes

REGRAS DE SEGURANÇA TÉCNICA:
- Não inventes parâmetros numéricos.
- Não declares ausência de uma condicionante apenas porque não a encontraste.
- Se não conseguires confirmar algo, escreve A CONFIRMAR.
- Se documento e fonte atual divergirem, escreve CONFLITO.
- Distingue claramente FACTO OFICIAL, DOCUMENTO FORNECIDO e INTERPRETAÇÃO.
- Cita URL e, quando disponível, artigo/n.º/alínea/página.

FORMATO DA RESPOSTA — texto curto e sem blocos de código:
RESUMO EXECUTIVO
- Município / freguesia
- Instrumento territorial em vigor
- Classificação do solo (ou A CONFIRMAR)
- 3 a 8 conclusões principais

REGRAS ENCONTRADAS
- [tema] | [valor/regra] | [estado] | [fundamento/artigo] | [fonte]

CONDICIONANTES
- [condicionante] | [estado] | [impacto] | [fonte]

PONTOS A CONFIRMAR
- lista objetiva

FONTES CONSULTADAS
- título | URL

Máximo recomendado: 1600 palavras.
'''
