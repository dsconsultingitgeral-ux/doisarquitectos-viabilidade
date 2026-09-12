# V6.9 — Fecho regulamentar

Correção estrutural final: quando a classe urbanística está identificada mas faltam máximos/índices, a aplicação executa uma única pesquisa regulamentar de resgate, com Google grounding, exigindo fonte oficial atual (Diário da República/Câmara). Mantém uma chamada nos casos completos e só usa a segunda chamada nos casos em que o primeiro relatório deixou parâmetros nucleares por confirmar.

Também limpa markdown dos cartões e elimina duplicações comuns na classificação.
