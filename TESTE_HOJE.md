# COMEÇAR AQUI — TESTE V4.2 PLUS GEMINI

## 1. GitHub

Extraia o ZIP e coloque **o conteúdo** desta pasta na raiz do repositório.

O repositório deve mostrar diretamente:

```text
app.py
requirements.txt
README.md
DEPLOY_SEGURO.md
TESTE_HOJE.md
assets/
prompts/
src/
.streamlit/
```

## 2. Streamlit

No Streamlit Community Cloud:

1. Abra a aplicação.
2. Vá a **Manage app**.
3. Abra **Settings**.
4. Abra **Secrets**.
5. Configure `GEMINI_API_KEY`, `GEMINI_MODEL` e o bloco privado `[auth]`.
6. Guarde.
7. Faça reboot/redeploy da aplicação.

As credenciais são privadas e **não vão para o GitHub**.

## 3. Teste 1 — Alameda Silva Rocha

Use:

- localização: Alameda Silva Rocha, Aveiro;
- documentos: levantamento topográfico + plantas de localização/PDM;
- modo completo.

Validar:

- mapa;
- extração de área;
- conflito 2.974 / 3.055 m²;
- classificação;
- usos;
- implantação;
- pisos;
- REN/RAN;
- três cenários;
- referências `[1]`, `[2]`, `[3]`;
- fontes Google realmente consultadas;
- PDF final.

## 4. Teste 2 — sem documentos

Use outra localização e **não anexe ficheiros**.

A aplicação deve:

- continuar sem bloquear;
- localizar no mapa;
- pesquisar fontes oficiais;
- produzir pré-viabilidade;
- NÃO inventar área ou limites;
- marcar dependências da parcela como `A CONFIRMAR`;
- indicar documentos que faltam.
