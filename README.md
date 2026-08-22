# doisarquitetos — Pré‑Viabilidade Urbanística V4

Aplicação Streamlit com 4 módulos:

1. **Localização** — identificação inicial e confirmação do terreno.
2. **Documentos** — upload e checklist documental.
3. **Análise IA** — execução integral do Master Prompt aprovado, análise de ficheiros e pesquisa web.
4. **Potencial** — resultado executivo, análise técnica, fontes/links e relatório PDF.

## O que está preservado

O ficheiro `prompts/master_prompt.txt` contém **integralmente e sem redução** o prompt aprovado no teste da Alameda Silva Rocha.

A V4 acrescenta um ficheiro separado, `prompts/source_addendum.txt`, exclusivamente para tornar obrigatória a metodologia de referências `[1]`, `[2]`, `[3]`, a lista de documentos analisados e a lista de **links efetivamente acedidos** durante a pesquisa.

## Publicar sem instalar Python

### 1. Criar um repositório no GitHub

Crie um repositório, por exemplo:

`doisarquitetos-viabilidade-v4`

Extraia o ZIP e envie **todo o conteúdo da pasta** para a raiz do repositório.

O GitHub deve ficar aproximadamente assim:

```text
app.py
requirements.txt
README.md
assets/
prompts/
src/
.streamlit/
```

Não envie um ficheiro `.streamlit/secrets.toml` real para o GitHub.

### 2. Criar a aplicação no Streamlit Community Cloud

Entre no Streamlit Community Cloud, escolha **New app**, selecione o repositório e indique:

```text
Main file path: app.py
```

### 3. Adicionar os Secrets

Nas definições da aplicação, abra **Secrets** e cole:

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-5.6-terra"

[auth]
username = "admin1"
password = "doisarquitetos"
```

Pode alterar utilizador e password.

### 4. Deploy

Carregue em **Deploy**.

O Streamlit instala automaticamente o `requirements.txt`. Não é necessário instalar Python no computador.

## Como funciona a análise

O motor usa a **Responses API** da OpenAI com:

- ficheiros enviados como `input_file`;
- `web_search` para pesquisa externa;
- Master Prompt completo;
- addendum obrigatório de fontes;
- extração das citações URL estruturadas devolvidas pela API;
- geração de PDF com as fontes efetivamente acedidas.

A documentação atual da OpenAI usa a Responses API para pedidos com modelos e ferramentas. Consulte sempre a documentação oficial antes de alterar versões ou parâmetros da API.

## Segurança / produção

O login incluído é deliberadamente simples, adequado a protótipo privado. Para produção com vários clientes, deverá ser substituído por autenticação real (por exemplo Auth0, Supabase Auth ou SSO).

O Streamlit Community Cloud não deve ser usado como armazenamento permanente de estudos. Nesta V4 os resultados vivem na sessão e podem ser descarregados em PDF/Markdown.

## Ficheiros importantes

### `prompts/master_prompt.txt`
Prompt aprovado, mantido integralmente.

### `prompts/source_addendum.txt`
Força:

- referências `[1]`, `[2]`, `[3]` junto das conclusões;
- fontes oficiais prioritárias;
- links realmente consultados;
- documentos fornecidos;
- páginas/artigos;
- indicação `FONTE NÃO CONFIRMADA` quando necessário.

### `src/openai_engine.py`
Upload dos documentos, pesquisa web e execução do modelo.

### `src/report.py`
Geração do relatório PDF.

## Modelo

Por defeito:

```toml
OPENAI_MODEL = "gpt-5.6-terra"
```

Pode trocar por outro modelo compatível com o fluxo, alterando apenas o Secret.

## Nota técnica importante

Os cartões do Módulo 4 fazem uma extração "best effort" dos títulos e valores do texto final. **O relatório técnico completo é sempre a fonte autoritativa dentro da aplicação.**

Para uma próxima versão, o ideal é manter o relatório narrativo perfeito e, em paralelo, pedir ao modelo uma pequena saída estruturada apenas para alimentar os cartões da interface. Assim os números ficam 100% estáveis sem alterar o Master Prompt.
