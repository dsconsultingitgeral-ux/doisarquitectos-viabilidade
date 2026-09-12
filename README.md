# doisarquitectos — Estudo Inteligente de Viabilidade · V4.3 Final Candidate

Aplicação Streamlit com o mesmo desenho e o mesmo fluxo de 4 módulos já validado:

1. **Localização** — morada, mapa, clique e polígono aproximado.
2. **Documentos** — upload opcional de PDFs/imagens.
3. **Análise IA** — análise técnica + pesquisa oficial.
4. **Potencial** — decisão preliminar, cartões executivos, análise, fontes e PDF.

## O que foi melhorado nesta versão

- O visual, mapa, login, navegação e funcionamento geral foram preservados.
- O `master_prompt.txt` original continua integralmente disponível.
- Foi acrescentado `prompts/reliability_addendum.txt` com regras de regressão derivadas dos testes reais: não inventar área, não tratar “condicionado” como “proibido”, explorar multifamiliar quando tecnicamente defensável, separar envelope teórico/capacidade/recomendação e testar o máximo potencial sem criar tetos artificiais.
- Os cartões do Módulo 04 deixaram de depender apenas de parsing frágil do Markdown. Depois do relatório, a aplicação executa uma extração estruturada curta (`executive_summary_prompt.txt`) apenas para alimentar os cartões.
- A confiança é normalizada para formato `NN%`.
- Área/uso/classificação/implantação/pisos passam a mostrar `A confirmar` quando não existe valor seguro, em vez de `—` ou texto quebrado.
- O cabeçalho do PDF usa, quando disponível, a localização final validada pelo próprio relatório.
- Separadores visuais `=====`/`-----` deixam de aparecer como barras no ecrã e no PDF.

## Prompts ativos

- `prompts/master_prompt.txt` — prompt técnico principal completo.
- `prompts/reliability_addendum.txt` — regras finais de robustez e anti-subestimação.
- `prompts/source_addendum.txt` — rastreabilidade, fontes e referências.
- `prompts/executive_summary_prompt.txt` — extração estruturada dos 6 cartões do Módulo 04; não cria factos novos.

Ficheiros de prompts antigos que possam continuar no repositório GitHub (`scenario_prompt.py`, `synthesis_prompt.py`, etc.) **não são necessários nesta arquitetura** e podem ser apagados para evitar confusão. O motor ativo está em `src/gemini_engine.py`.

## Secrets do Streamlit

Não guardar chaves no GitHub. Em **Streamlit → App settings → Secrets**, usar:

```toml
GEMINI_API_KEY = "..."
GEMINI_MODEL = "gemini-3.7-flash"

[auth]
username = "..."
password = "..."
```

Pode manter exatamente os Secrets que já estão configurados na aplicação atual.

## Deploy

O ficheiro principal continua a ser:

```text
app.py
```

O `requirements.txt` mantém as dependências necessárias.

## Teste recomendado antes de enviar ao gabinete

1. São Marcos / Albergaria-a-Velha — confirmar que multifamiliar não é eliminado quando condicionado/permitido e que o cenário máximo não cria um teto sem metodologia.
2. Ílhavo — confirmar escala multifamiliar.
3. Alameda Silva Rocha — confirmar conflito 2.974/3.055 m² e manutenção do bom resultado.
4. Rua da Misericórdia / Águeda — confirmar potencial de pisos/volumetria sem transformar regra-base em teto absoluto.
5. Rua dos Andoeiros / Aveiro — confirmar uso multifamiliar, pisos e aproveitamento da topografia.

Esta é uma versão de **protótipo para validação técnica**, não substitui PIP, decisão municipal ou validação do arquiteto.
