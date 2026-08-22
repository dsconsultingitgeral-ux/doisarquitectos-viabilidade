WEB_RESEARCH_PROMPT = r'''
Faz investigação territorial e regulamentar ATUAL para um estudo preliminar em Portugal.

DADOS DO TERRENO:
{study_context}

DADOS EXTRAÍDOS DOS DOCUMENTOS:
{document_context}

OBJETIVO:
Localizar e confirmar, através de fontes oficiais, as regras do jogo aplicáveis ao local. Usa Google Search quando necessário e cita URLs.

ORDEM DE INVESTIGAÇÃO:
A. Identificar município/freguesia e instrumento(s) de gestão territorial em vigor.
B. Procurar SIG/geoportal/plantas oficiais relevantes e páginas oficiais para consulta.
C. Confirmar PDM em vigor, respetivo regulamento e publicação no Diário da República; verificar revisões, alterações, correções materiais, suspensões e datas.
D. Verificar se existem PU, PP, loteamentos ou instrumentos especiais potencialmente aplicáveis ao local.
E. A partir da classificação indicada pelos documentos ou SIG, localizar artigos que definam essa categoria/subcategoria.
F. Extrair: usos dominantes/permitidos/compatíveis/complementares; índice de utilização; ocupação; impermeabilização; implantação; área de construção; altura/cércea; nº pisos; afastamentos; alinhamentos; densidade; estacionamento; cedências; espaços verdes e outras regras específicas.
G. Investigar condicionantes relevantes: REN, RAN, recursos hídricos/domínio hídrico, risco/incêndio rural, ruído, património, rodovia, ferrovia, rede elétrica, infraestruturas/equipamentos, servidões e restrições de utilidade pública.
H. Identificar legislação nacional complementar necessária (ex.: RJUE e regimes especiais), sem encher o relatório com legislação não relacionada com o caso.

HIERARQUIA DE FONTES:
1 Diário da República / legislação oficial
2 Município / SIG / regulamento municipal
3 DGT/SNIT
4 CCDR / APA / ICNF / Património Cultural / Infraestruturas de Portugal / outras entidades públicas competentes
5 outras fontes apenas como pista

REGRAS:
- Não declares "não existe" se apenas não encontraste.
- Se a classificação do terreno não estiver confirmada, devolve-a como A CONFIRMAR e indica exatamente o passo necessário.
- Não apresentes parâmetro numérico sem base normativa rastreável.
- Se houver conflito entre documento fornecido e fonte atual, assinala CONFLITO.

DEVOLVE um texto técnico estruturado, incluindo no final uma secção "FONTES CONSULTADAS" com links e, sempre que possível, artigo/número/alínea/página.
'''
