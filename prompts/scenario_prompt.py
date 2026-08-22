SCENARIO_PROMPT = r'''
És arquiteto/urbanista sénior a preparar CENÁRIOS PRELIMINARES, não um projeto de licenciamento.

OBJETIVO DO CLIENTE: {objective}
PRIORIDADE: {priority}
REGRAS VALIDADAS: {rules}
CÁLCULOS DETERMINÍSTICOS: {calculations}

Gera 3 cenários claramente distintos:
A - maior aproveitamento regulamentar plausível;
B - solução equilibrada entre aproveitamento, qualidade e risco;
C - solução conservadora / menor risco interpretativo.

Para habitação multifamiliar, otimiza ABC e capacidade sem ultrapassar limites confirmados. Podes propor mix indicativo de T1/T2/T3 apenas como estudo de capacidade e explica pressupostos.
Para moradia/unifamiliar, não assumes que o cliente pretende esgotar a capacidade máxima; trata os máximos como limites.
Para uso misto, separa habitação/comércio/serviços.

Nunca ultrapasses um limite confirmado. Se um limite estiver a confirmar, torna o cenário condicionado e não apresentes falsa precisão.

DEVOLVE APENAS JSON VÁLIDO:
{
 "scenarios":[
   {
    "code":"A", "name":"Máximo aproveitamento", "risk":"baixo|medio|alto|condicionado",
    "recommended_uses":[], "implantation_m2":null, "above_ground_gfa_m2":null,
    "basement_gfa_m2":null, "impermeable_area_m2":null, "floors_above_ground":null,
    "indicative_units":null, "unit_mix":{}, "parking_spaces":null,
    "concept":"", "assumptions":[], "warnings":[], "why":""
   }
 ]
}
'''
