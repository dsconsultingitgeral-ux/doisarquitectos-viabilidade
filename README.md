# doisarquitetos — Pré‑Viabilidade Urbanística V4.2 Plus Studio · Gemini

Aplicação Streamlit para **estudo preliminar de viabilidade urbanística de terrenos em Portugal**.

## Fluxo

**01 Localização → 02 Documentos → 03 Análise IA → 04 Potencial / Relatório**

### 01 — Localização

- morada;
- mapa;
- coordenadas auxiliares;
- município/freguesia/localidade;
- artigo e área, quando conhecidos;
- validação visual do local.

A geocodificação é apenas uma ajuda de localização. **Nunca é utilizada para inventar a área ou os limites do prédio.**

### 02 — Documentos

Pode trabalhar:

- **Modo rápido:** apenas localização;
- **Modo completo:** localização + documentos.

Documentos podem incluir levantamento topográfico, plantas municipais, certidões, PIP, cadastro e outros elementos da parcela.

### 03 — Análise IA

Motor: **Gemini API + Pesquisa Google**.

A aplicação envia ao Gemini:

- o **Master Prompt integral aprovado**;
- os documentos anexados;
- o contexto da localização;
- regras adicionais obrigatórias de fontes e rastreabilidade.

O ficheiro `prompts/master_prompt.txt` mantém o prompt técnico integral.

### 04 — Potencial

Apresenta primeiro a decisão:

- viabilidade;
- área considerada;
- classificação;
- categoria;
- uso recomendado;
- implantação;
- construção;
- pisos;
- fogos indicativos;
- condicionantes;
- confiança.

Depois:

- Cenário A — Conservador;
- Cenário B — Equilibrado;
- Cenário C — Máximo potencial;
- recomendação;
- fundamentação técnica;
- fontes;
- links;
- relatório PDF.

## Fontes

O Master Prompt exige referências do tipo:

`[1]`, `[2]`, `[3]`...

No final do estudo deve existir uma secção de referências e documentos analisados.

Além disso, a interface recolhe os **links devolvidos pelo grounding da Pesquisa Google do Gemini** quando disponíveis.

## Segurança

Não existem credenciais por defeito no código.

Não coloque credenciais no GitHub.

Leia primeiro:

- `DEPLOY_SEGURO.md`
- `TESTE_HOJE.md`

## Logo

O projeto já inclui `assets/logo.png`, obtido do visual aprovado no teste.

Se quiser substituir pelo ficheiro original de alta resolução, basta trocar:

```text
assets/logo.png
```

A aplicação também aceita WEBP/JPG/SVG.

## API

SDK:

```text
google-genai
```

Secrets privados utilizados:

- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `[auth].username`
- `[auth].password`

## Nota

O resultado é um **estudo preliminar de apoio à decisão**. A aplicação deve distinguir sempre informação confirmada, provável, não determinada e em conflito, conforme definido no Master Prompt.


## Revisão visual Studio

Esta revisão corrige especificamente a experiência gráfica:

- logo real mostrado sem ampliação artificial, para evitar desfocagem;
- cabeçalho limpo, sem duplicação/corte do logótipo;
- espaçamento superior corrigido para não cortar a navegação;
- largura e tipografia ajustadas a um gabinete de arquitetura;
- mapa sempre visível no Módulo 01;
- pesquisa por morada;
- **clique direto no mapa com reverse geocoding** para tentar preencher rua/localização;
- coordenadas apresentadas após seleção;
- Município, Freguesia e Localidade preenchidos automaticamente quando a geocodificação os disponibiliza;
- mantém integralmente Documentos, Master Prompt, Gemini, fontes, potencial, cenários e PDF.
