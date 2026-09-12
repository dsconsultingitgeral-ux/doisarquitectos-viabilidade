# V6.6 — Eficiência e consistência final

Correções sobre a V6.5:

1. **Pisos por tipologia**
   - O cartão executivo deixou de confiar cegamente num valor curto como `2 pisos`.
   - A síntese percorre também os parâmetros regulamentares, conclusão e cenários do mesmo relatório.
   - Quando existem regimes distintos, apresenta ambos, por exemplo:
     `3 pisos plurifamiliar/misto · 2 pisos unifamiliar`.
   - Um valor incompleto do bloco executivo nunca substitui uma regra mais completa encontrada no corpo técnico.

2. **Condicionante principal**
   - Corrigida a deteção de `PRINCIPAIS CONDICIONANTES` (plural em português).
   - O cartão complementar volta a ser mostrado quando o relatório contém uma condicionante concreta.

3. **Coerência única UI/PDF**
   - O bloco `DECISÃO PRELIMINAR` é reescrito a partir dos mesmos factos canónicos usados pelos cartões.
   - Não existe chamada adicional à IA para montar a síntese.

4. **Eficiência**
   - Mantém-se uma única análise IA principal por estudo.
   - Só existe uma segunda chamada se a aplicação detetar localmente um Projeto/PIP carregado e a primeira análise disser incorretamente que não existe proposta.
   - Cartões, PDF e síntese são montados localmente após a análise, sem custo/latência adicional de IA.

## Regressão verificada — Lamas do Vouga

Para o relatório de 12/09/2026:
- Área: 4 539,43 m²
- Classificação: EH1
- Uso dominante: Habitação
- Pisos: 3 pisos plurifamiliar/misto · 2 pisos unifamiliar
- Implantação: Sem máximo numérico confirmado
- Evidência: DOCUMENTADO
- Condicionante principal: extraída da conclusão técnica quando disponível

## Teste recomendado

Repetir exatamente o mesmo teste que gerou o PDF anterior, com os mesmos documentos efetivamente carregados na aplicação. O objetivo é confirmar que UI e PDF apresentam a mesma regra completa de pisos e a mesma condicionante principal.
