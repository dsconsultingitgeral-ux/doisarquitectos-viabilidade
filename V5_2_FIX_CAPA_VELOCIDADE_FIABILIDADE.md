# V5.2 — Capa + velocidade + fiabilidade (sem redesenho da interface)

- Capa PDF opcional no módulo **02 · Documentos**. A capa não é enviada à IA.
- Se existir capa carregada, a primeira página é preservada como página 1 do relatório.
- Se não existir capa carregada, mantém-se a capa institucional automática.
- PDF fica em cache na sessão para não ser reconstruído a cada rerun do Streamlit.
- Limpeza de Markdown/LaTeX no PDF (`####`, `\\times`, `\\%`, subscritos/sobrescritos mais comuns).
- Modelo por defeito alterado para `gemini-2.5-flash` (estável) e cadeia de fallback encurtada.
- Menos retries/backoff para evitar esperas longas quando um endpoint falha.
- Cartões críticos (implantação/pisos) só mostram número quando: valor único + citação na linha + fontes grounded capturadas; caso contrário mostram **A confirmar**.
- Dashboard e PDF continuam a derivar da mesma análise final.
