# doisarquitectos — Estudo Inteligente de Viabilidade V3

Versão V3 simplificada e reconstruída em torno de uma checklist urbanística fixa.

## Fluxo
1. Localização do terreno.
2. Documentação opcional.
3. Análise automática por quatro checklists paralelas: planeamento, usos, parâmetros e condicionantes.
4. Relatório PDF com referências numeradas.

## Princípios
- Documentação não obrigatória.
- A área só vem de documento, polígono ou confirmação manual.
- Nunca considera ausência de informação como ausência de condicionante.
- Cada conclusão tem estado e confiança próprios.
- REN, RAN, domínio hídrico, incêndio, ruído, património e servidões são verificações obrigatórias.
- Cálculos são determinísticos em Python.
- O relatório pode ser gerado mesmo com lacunas, deixando-as explícitas.

## Secrets
Veja `.streamlit/secrets.toml.example`.
