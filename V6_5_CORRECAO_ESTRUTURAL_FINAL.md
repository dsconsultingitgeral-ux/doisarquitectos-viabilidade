# V6.5 — Correção estrutural da síntese

Esta versão corrige o caso real de Lamas do Vouga sem assumir que o PDF `00324_Peças desenhadas` foi carregado na aplicação.

## Correções
- O módulo 04 deixa de aceitar `A confirmar` como se fosse um resultado válido quando o corpo técnico já contém um valor concreto.
- Pisos são recuperados da secção regulamentar mesmo quando aparecem em tabelas/quebras de linha: `3 pisos plurifamiliar/misto · 2 pisos unifamiliar` no caso testado.
- Sem proposta arquitetónica, o “uso recomendado” deixa de privilegiar cenários especulativos e passa a usar o uso dominante/admissível documentado.
- ABC e número de fogos deixam de aparecer como cartões `A confirmar`; só surgem quando existe base documental/cálculo sustentado.
- A condicionante principal é recuperada do corpo do relatório (incluindo ZGP/ZEP).
- Quando não existe máximo numérico de implantação confirmado, a UI mostra `Sem máximo confirmado` em vez de um placeholder vazio.
- O PDF e o dashboard continuam a usar a mesma estrutura de factos.
- O bloco executivo do PDF passa a escrever `Sem máximo numérico confirmado` quando o dado realmente não pode ser determinado, em vez de repetir `A confirmar` sem contexto.

## Validação executada
No relatório real de Lamas do Vouga fornecido em 12/09/2026, o extrator devolve:
- Viabilidade: FAVORÁVEL COM CONDICIONANTES
- Área: 4 539,43 m²
- Classificação: Solo Urbano — Espaços Habitacionais Tipo 1 (EH 1)
- Uso: Habitação
- Pisos: 3 pisos plurifamiliar/misto · 2 pisos unifamiliar
- Condicionante: ZGP/ZEP — património cultural; parecer da entidade competente
- Evidência: DOCUMENTADO
- Implantação: sem máximo numérico confirmado nos documentos analisados
- ABC/fogos: omitidos quando não existe proposta/base suficiente, em vez de inventados
