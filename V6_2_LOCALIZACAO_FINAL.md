# V6.2 — CORREÇÃO FINAL DE LOCALIZAÇÃO

- Corrigido parsing de moradas com código postal e `Portugal` no fim.
- `Portugal` deixa de ser interpretado como localidade.
- Pesquisa de rua é validada contra a localidade pedida antes de aceitar coordenadas.
- Resultados de outra cidade são rejeitados; não existe fallback silencioso para Lisboa/outra cidade.
- ArcGIS deixa de aceitar automaticamente o primeiro candidato e passa pela mesma validação rua + localidade.
- Se a rua não for confirmada, a app centra apenas na localidade correta e pede seleção manual do ponto.
- Coordenadas introduzidas/clicadas são preservadas exatamente; reverse geocoding não pode deslocar o ponto.
- Mantidas as correções V6.1 de leitura/classificação dos documentos e deteção de proposta arquitetónica.
