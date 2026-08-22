# PUBLICAÇÃO SEGURA — V4.2 PLUS GEMINI

## Regra principal

**Nunca colocar utilizador, palavra-passe ou API Key no GitHub.**

As credenciais ficam exclusivamente em:

**Streamlit Community Cloud → Manage app → Settings → Secrets**

## Secrets necessários

No painel privado do Streamlit, crie estas chaves:

```toml
GEMINI_API_KEY = "<CONFIGURAR_PRIVADAMENTE>"
GEMINI_MODEL = "gemini-3.7-flash"

[auth]
username = "<CONFIGURAR_PRIVADAMENTE>"
password = "<CONFIGURAR_PRIVADAMENTE>"
```

Os valores reais não devem existir em nenhum ficheiro do repositório.

## O GitHub público NÃO deve conter

- utilizador real;
- palavra-passe real;
- Gemini API Key;
- `.streamlit/secrets.toml`;
- `.env` com valores;
- screenshots onde as credenciais estejam visíveis.

## Login

A aplicação não possui utilizador ou palavra-passe por defeito.

Se os Secrets não estiverem configurados, o acesso é bloqueado e aparece uma mensagem de configuração.

## Gemini

A aplicação usa o SDK oficial `google-genai`.

A chave é lida apenas de `GEMINI_API_KEY` nos Secrets privados.

O modelo pode ser alterado com `GEMINI_MODEL`, também sem alterar o código público.
