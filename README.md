# doisarquitectos — Estudo Inteligente de Viabilidade V2

Aplicação Streamlit para estudo preliminar de viabilidade urbanística em Portugal.

## O fluxo
1. Localização rápida e desenho opcional dos limites no mapa.
2. Upload opcional de qualquer documento que o cliente já tenha.
3. Gemini classifica e extrai levantamento, SIG, PDM, PIP, documentos prediais, estudos anteriores etc.
4. Gemini usa Google Search para procurar fontes oficiais atuais: Município/SIG, PDM, Diário da República, DGT/SNIT, REN/RAN e regimes relevantes.
5. Cruza documentação + pesquisa e cria as "regras do jogo" com estados: confirmado, calculado, interpretação, a confirmar e conflito.
6. Python executa cálculos determinísticos.
7. Gemini propõe 3 cenários preliminares.
8. Exporta PDF técnico e JSON.

## Sem instalar Python no seu computador
O projeto foi preparado para **GitHub + Streamlit Community Cloud**. Basta descompactar e carregar a pasta para um repositório GitHub.

## 1. Google AI Studio / Gemini API
1. Aceda a Google AI Studio.
2. Abra **API keys** e crie/seleccione um projeto.
3. Clique **Set up billing** se pretender Paid Tier.
4. O Google pode pedir pré-pagamento mínimo de **US$10 (ou equivalente)**. Este valor é saldo de API; não é uma mensalidade fixa.
5. Crie a API key e copie-a. Não a coloque no GitHub.
6. Em AI Studio pode acompanhar consumo em **Dashboard > Usage**.

Modelo default do projeto: `gemini-3.7-flash`. Pode alterar em Secrets.

## 2. GitHub
1. Crie um repositório privado, por exemplo `doisarquitectos-viabilidade`.
2. Descompacte este ZIP.
3. No GitHub: **Add file > Upload files**.
4. Arraste o conteúdo da pasta (incluindo `app.py`, `core`, `prompts`, `requirements.txt`, `.streamlit/secrets.toml.example`).
5. Faça commit.

**Não** faça upload de um ficheiro real `.streamlit/secrets.toml` com a chave.

## 3. Streamlit Community Cloud
1. Entre em `share.streamlit.io` com GitHub.
2. **Create app / Deploy an app**.
3. Escolha o repositório.
4. Main file: `app.py`.
5. Abra **Advanced settings / Secrets** e cole:

```toml
GEMINI_API_KEY = "A_SUA_CHAVE"
APP_USER = "admin1"
APP_PASSWORD = "doisarquitetos"
GEMINI_MODEL = "gemini-3.7-flash"
```

6. Deploy.

Antes de entregar ao cliente altere a password para uma exclusiva.

## 4. Documentos que a IA reconhece
O prompt já inclui explicitamente: levantamento topográfico; planta de localização/cartografia; SIG/plantas municipais; PDM ordenamento; PDM condicionantes; REN; RAN; incêndio; ruído; recursos hídricos; património; servidões/infraestruturas; cadastro; caderneta; certidão; PIP; parecer/despacho; alvará/loteamento; PU; PP; estudo prévio; projeto existente; fotografia; documento jurídico/administrativo e outros.

## 5. Limitações importantes
- SIG municipais não têm uma API uniforme. O motor de pesquisa encontra fontes públicas e links, mas alguns portais podem exigir intervenção do arquiteto para descarregar uma planta.
- O relatório é preliminar. Não substitui PIP, parecer municipal, licenciamento nem responsabilidade técnica do arquiteto.
- Área desenhada no mapa é aproximada.
- Um parâmetro sem fonte confirmada deve permanecer `A CONFIRMAR`.

## Segurança
- Chaves e passwords em Streamlit Secrets.
- Preferir repositório privado.
- Não guardar documentação de clientes no GitHub.
- Nesta V2 os uploads vivem apenas na sessão e são enviados à API para análise; não são intencionalmente persistidos pela aplicação.
