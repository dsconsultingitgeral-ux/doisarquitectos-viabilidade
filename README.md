# doisarquitectos — Estudo Inteligente de Viabilidade V2.7

Aplicação Streamlit para estudo preliminar de viabilidade urbanística em Portugal.

## Fluxo
1. Localização por morada/coordenadas/mapa.
2. Documentação opcional.
3. Estudo territorial automático: rua + freguesia + município + coordenadas + documentos + fontes oficiais.
4. Ficha de regras e condicionantes, com confiança e referências.
5. Cálculos determinísticos em Python.
6. Cenários apenas quando existe base quantitativa suficiente.
7. PDF preliminar ou completo, sempre com referências e sem JSON técnico.

## Secrets
```toml
GEMINI_API_KEY = "..."
APP_USER = "admin1"
APP_PASSWORD = "..."
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_FALLBACK_MODELS = "gemini-3.7-flash"
GEMINI_TIMEOUT_MS = 45000
```

> A aplicação é apoio técnico preliminar e não substitui validação do arquiteto, PIP, licenciamento ou decisão municipal.
