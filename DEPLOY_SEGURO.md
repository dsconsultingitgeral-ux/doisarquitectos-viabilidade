# Publicação segura — V4.2 Plus

Nunca coloque credenciais, palavras-passe ou chaves de API no GitHub.

No Streamlit Community Cloud, configure os valores apenas em **Settings > Secrets**.

Estrutura:

```toml
OPENAI_API_KEY = ""
OPENAI_MODEL = ""

[auth]
username = ""
password = ""
```

Preencha os valores apenas no painel privado do Streamlit Cloud.

O repositório público não deve conter:
- utilizador real;
- palavra-passe real;
- chave de API real;
- ficheiro `.env`;
- ficheiro `.streamlit/secrets.toml`;
- screenshots com credenciais.

A aplicação falha de forma segura se o utilizador ou a palavra-passe não estiverem configurados.
