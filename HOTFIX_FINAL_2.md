# HOTFIX FINAL 2

Corrige o erro de importação no arranque do Streamlit.

Alterações:
- `extract_label` deixou de ser importado de `src.ui`; fica definido localmente no `app.py`, evitando falhas por ficheiros GitHub fora de sincronização.
- removido o download Markdown;
- fica apenas o relatório PDF;
- mantém logo original de alta resolução;
- mantém mapa, Gemini, Master Prompt, fontes e folha-tipo oficial do PDF.

IMPORTANTE: substitua TODO o conteúdo do repositório por esta build. Não copie apenas `app.py`.
