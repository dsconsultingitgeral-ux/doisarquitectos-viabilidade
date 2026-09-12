# V6.4 — Correção final da Síntese / Potencial

Correção do problema observado em Lamas do Vouga: o relatório técnico continha resultados concretos, mas o módulo 04 mostrava "A confirmar".

## Alterações
- Os cartões deixam de depender exclusivamente do bloco `DECISÃO PRELIMINAR`.
- Se esse bloco vier incompleto, os valores são extraídos deterministicamente do corpo do mesmo relatório final.
- Documentos carregados passam a contar como evidência; já não é obrigatório existir um link de Google Search para apresentar valores documentados.
- Mantém-se a regra de não inventar máximos regulamentares.
- Intervalos de cenários estimados são apresentados como estimativas do cenário recomendado, sem serem confundidos com máximos do PDM.
- Adicionados três cartões complementares: ABC, Potencial (fogos/capacidade) e Condicionante principal.
- Não foi adicionada nenhuma chamada adicional à IA, preservando a velocidade da V6.3.

## Teste de regressão — Lamas do Vouga
A extração local do relatório produzido recupera:
- Viabilidade: FAVORÁVEL COM CONDICIONANTES
- Área: 4 539,43 m²
- Classificação: Solo Urbano — Espaços Habitacionais Tipo 1 (EH 1)
- Uso recomendado: edifício residencial multifamiliar com fração comercial/serviços no R/C
- Implantação estimada do cenário recomendado: ~1 600–1 800 m²
- Pisos: 3 multifamiliar / 2 unifamiliar
- ABC estimada: ~4 000–4 500 m²
- Potencial: ~35–45 fogos
- Evidência: DOCUMENTADO
