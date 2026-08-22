# V4.2 PLUS FINAL — ENTREGA

Esta é a build final consolidada para teste/entrega.

## Alterações desta build

- Logo ORIGINAL em alta resolução (`assets/logo.png`), sem capturas de ecrã.
- Símbolo original também preservado (`assets/symbol.png`).
- Mapa clicável + pesquisa por morada + desenho de perímetro aproximado.
- Cartões de resultado limpos: removem LaTeX, markdown bruto e referências longas.
- Resultado executivo em 2 linhas de 3 cartões para evitar colunas estreitas.
- Processamento visual simplificado para um único estado elegante.
- Cache dos ficheiros Gemini na sessão para reanálises mais rápidas.
- Master Prompt integral mantido.
- Fontes `[1] [2] [3]` e links mantidos.
- PDF gerado SOBRE a folha-tipo oficial fornecida pelo gabinete em `assets/folha_tipo.pdf`.
- Cabeçalho, logótipo e rodapé da folha-tipo são preservados em todas as páginas.

## Secrets privados do Streamlit

Use apenas o painel privado do Streamlit:

```toml
GEMINI_API_KEY = "<CHAVE_PRIVADA>"
GEMINI_MODEL = "<MODELO_CONFIGURADO>"

[auth]
username = "<UTILIZADOR_PRIVADO>"
password = "<PASSWORD_PRIVADA>"
```

Nunca coloque os valores reais no GitHub.

## Teste final recomendado

1. Entrar.
2. Localizar Alameda Silva Rocha, Aveiro.
3. Confirmar mapa.
4. Anexar os dois PDFs do caso.
5. Executar análise.
6. Confirmar os seis cartões executivos.
7. Abrir Análise técnica.
8. Confirmar Fontes.
9. Gerar PDF e verificar folha-tipo.
