# doisarquitectos — Estudo Inteligente de Viabilidade V2.5

Aplicação Streamlit para análise preliminar de viabilidade urbanística em Portugal, combinando localização, documentos opcionais, pesquisa oficial assistida por Gemini, matriz regulamentar rastreável, cálculos determinísticos, cenários e relatório PDF com referências numeradas.

## Fluxo
1. Localização / polígono
2. Documentação opcional
3. Pesquisa territorial e regulamentar
4. Regras do jogo + revisão técnica
5. Cálculos determinísticos
6. Cenários preliminares
7. Relatório PDF

## Secrets do Streamlit
```toml
GEMINI_API_KEY = "..."
APP_USER = "admin1"
APP_PASSWORD = "..."
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_FALLBACK_MODELS = "gemini-2.5-flash,gemini-3.5-flash,gemini-3.7-flash"
GEMINI_TIMEOUT_MS = 45000
```

Nunca coloque a chave real no GitHub.
