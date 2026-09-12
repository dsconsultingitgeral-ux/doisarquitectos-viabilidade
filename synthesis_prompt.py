SYNTHESIS_PROMPT = r'''
Transforma os dados do terreno, documentos fornecidos e investigação oficial numa
MATRIZ TÉCNICA DE VIABILIDADE URBANÍSTICA PRELIMINAR rigorosa, prudente e utilizável
por arquitetos.

A tua função nesta etapa NÃO é inventar um projeto nem escolher prematuramente uma
solução. A tua função é consolidar FACTOS, REGRAS, INTERPRETAÇÕES, CONFLITOS e
INCERTEZAS que serão posteriormente utilizados pelo motor de cenários.

================================================================================
CONTEXTO DO ESTUDO
================================================================================

{study_context}

================================================================================
ANÁLISE DOCUMENTAL
================================================================================

{document_context}

================================================================================
INVESTIGAÇÃO WEB OFICIAL
================================================================================

{web_context}

================================================================================
PRINCÍPIO FUNDAMENTAL
================================================================================

A matriz deve refletir aquilo que está EFETIVAMENTE demonstrado pelas fontes.

É preferível devolver:

"a_confirmar"

do que transformar uma interpretação incompleta numa proibição, limite ou certeza.

NUNCA preencher uma regra apenas porque ela parece "habitual", "típica",
"normal" ou "provável" para determinada categoria de solo.

================================================================================
1. LOCALIZAÇÃO
================================================================================

- Preserva a rua/morada indicada pelo utilizador como dado inicial.
- Cruza-a com documentos, cartografia municipal e pesquisa oficial.
- Resolve município, freguesia e localidade quando houver suporte inequívoco.
- Se a informação introduzida pelo utilizador estiver errada mas as fontes oficiais
  forem inequívocas, utiliza a localização oficial correta.
- Regista a divergência em "conflicts".
- Não deixes freguesia/localidade como "a_confirmar" quando documentos oficiais
  permitirem resolvê-la.
- Não inventes coordenadas.

================================================================================
2. ÁREA DO TERRENO
================================================================================

NUNCA inventes área.

Se existir um único valor documental sólido:
- identification.area_m2 = valor;
- identification.area_source = fonte.

Se existirem vários valores contraditórios:
- identification.area_m2 = null;
- descreve todos os valores em "conflicts";
- identification.area_source deve indicar "conflito documental";
- calculation_inputs.parcel_area_m2 = null, salvo se existir instrução explícita
  para utilizar provisoriamente um dos valores.

Se não existir valor numérico:
- area_m2 = null;
- parcel_area_m2 = null.

NUNCA criar áreas de referência fictícias de 500, 1000, 1500 m² ou outro valor.

================================================================================
3. CLASSIFICAÇÃO E QUALIFICAÇÃO DO SOLO
================================================================================

Determina separadamente:

- soil_class
- category
- subcategory

Não derives automaticamente usos permitidos ou proibidos apenas da classificação
do solo.

Exemplo de raciocínio PROIBIDO:

"Solo Rústico → Habitação Multifamiliar = não"

A classificação territorial é apenas uma parte da análise.

Para usos, tens de analisar o regulamento concreto aplicável.

================================================================================
4. REGRA CRÍTICA PARA USOS
================================================================================

Para cada uso relevante analisa separadamente, pelo menos:

- habitação unifamiliar
- habitação bifamiliar
- habitação multifamiliar
- comércio
- serviços
- uso misto
- turismo
- equipamentos
- indústria/armazéns quando aplicável

Valores permitidos para "admissibility":

"sim"
"não"
"condicionado"
"a_confirmar"

REGRA ABSOLUTA:

Só podes utilizar:

"admissibility": "não"

quando existir uma disposição regulamentar EXPRESSA, CLARA e DIRETAMENTE APLICÁVEL
ao terreno que impeça esse uso.

A simples classificação como Solo Rústico, Área de Edificação Dispersa,
Espaço Habitacional, Espaço Central ou qualquer outra categoria NÃO É,
por si só, prova suficiente de proibição.

Antes de devolver "não", verifica obrigatoriamente:

1. artigo regulamentar concreto;
2. número/alínea quando disponível;
3. se a disposição é efetivamente aplicável à subcategoria do terreno;
4. se existem exceções;
5. se existem regimes de colmatação;
6. se existe possibilidade de operação conjunta;
7. se a regra se refere ao uso ou apenas ao tipo de operação urbanística;
8. se existe distinção entre loteamento e edificação;
9. se a morfologia/envolvente pode influenciar a solução;
10. se o tema depende de PIP ou apreciação municipal.

ATENÇÃO:

"loteamento urbano não admissível"

NÃO significa automaticamente:

"habitação multifamiliar não admissível".

São conceitos diferentes e nunca devem ser tratados como equivalentes sem fonte
regulamentar explícita.

Se a pesquisa apenas permitir concluir que o uso é pouco habitual, sujeito a
colmatação, dependente de enquadramento ou não totalmente claro:

usar:

"admissibility": "condicionado"

ou

"admissibility": "a_confirmar"

NUNCA "não".

No campo "basis", explica de forma precisa a disposição encontrada e o nível de
certeza.

================================================================================
5. PROIBIÇÕES — TESTE DE CONTRAPROVA
================================================================================

Sempre que estiveres prestes a marcar um uso como "não", executa esta verificação:

"Existe alguma interpretação alternativa razoável do regulamento pela qual este uso
possa ser admissível mediante colmatação, integração morfológica, PIP, operação
urbanística específica ou outra disposição regulamentar?"

Se a resposta for SIM ou INCERTA:

NÃO utilizar "não".

Utilizar "condicionado" ou "a_confirmar".

Uma proibição deve possuir confiança regulamentar muito elevada e referência
específica.

================================================================================
6. PARÂMETROS URBANÍSTICOS
================================================================================

Nunca inventes:

- índice de utilização;
- índice de ocupação;
- impermeabilização;
- cércea;
- pisos;
- afastamentos;
- estacionamento.

Se a fonte não sustenta inequivocamente o valor:

"value": null
"status": "a_confirmar"

Nunca utilizar médias, práticas usuais ou valores "típicos" como se fossem regras.

Exemplo PROIBIDO:

"implantação típica nesta categoria = 30–40%"

quando nenhum artigo consultado estabelece esse intervalo.

Nesse caso:

"value": null
"status": "a_confirmar"

e explicar no "basis" que o parâmetro não foi confirmado.

================================================================================
7. PISOS E CÉRCEA
================================================================================

Distingue sempre:

A) regra regulamentar diretamente confirmada;
B) leitura morfológica/envolvente;
C) potencial dependente de PIP;
D) hipótese não comprovada.

O campo:

"max_floors_above_ground"

só deve assumir um número com status "confirmado" quando existir regra diretamente
aplicável e inequívoca.

Se o regulamento indicar um parâmetro-base mas a cércea dominante, alinhamentos,
edificações contíguas, volumetria escalonada ou regimes específicos puderem alterar
a solução:

- usa o valor-base;
- status = "interpretacao" ou "a_confirmar", conforme o caso;
- explica no "basis" que o número não deve ser interpretado como teto absoluto
  sem validação da morfologia/PIP.

Nunca transformar automaticamente uma regra geral numa impossibilidade de solução
com corpos de altura distinta.

================================================================================
8. CAVES
================================================================================

Só preencher max_floors_below_ground quando existir regra concreta.

A existência de declive pode indicar POTENCIAL para cave, mas não prova um máximo
regulamentar.

Se apenas houver leitura topográfica:

"value": null
"status": "interpretacao"

e indicar no "basis" que a topografia favorece cave/semienterrado, mas o número
máximo não está confirmado.

================================================================================
9. CONDICIONANTES
================================================================================

Para REN, RAN, domínio hídrico, servidões, património, ferrovia, rodovia,
infraestruturas, risco de incêndio, ruído e outras condicionantes:

"nao_abrange" apenas quando a cartografia/documentação permitir confirmá-lo.

Ausência de menção NÃO equivale a "nao_abrange".

Se não foi possível verificar:

"a_confirmar"

================================================================================
10. CONFLITOS
================================================================================

Regista expressamente em "conflicts":

- diferenças de área;
- divergências de freguesia/localidade;
- diferenças entre levantamento e cartografia;
- documentos de datas diferentes;
- regras aparentemente contraditórias;
- diferença entre interpretação documental e pesquisa regulamentar.

Nunca resolver silenciosamente um conflito importante.

================================================================================
11. CÁLCULOS
================================================================================

calculation_inputs só pode conter valores NUMÉRICOS confirmados ou suficientemente
suportados.

Se area_m2 for desconhecida:

parcel_area_m2 = null

Se índice não estiver comprovado:

utilization_index = null
occupation_index = null
impermeability_index = null

Não preencher calculation_inputs com estimativas apenas para permitir que outro
módulo produza números.

É preferível impedir um cálculo do que alimentar o motor seguinte com uma premissa
inventada.

================================================================================
12. SCORE / READINESS
================================================================================

O score NÃO representa "probabilidade de o projeto ser aprovado".

Representa apenas:

QUALIDADE E COMPLETUDE DA BASE DE INFORMAÇÃO PARA PRODUZIR UMA ANÁLISE.

Exemplos:

90–100:
localização, área, classificação, artigos principais, usos, parâmetros e
condicionantes fortemente documentados.

70–89:
boa base documental, mas existem parâmetros relevantes a confirmar.

40–69:
classificação conhecida, mas faltam área, índices ou regras determinantes.

0–39:
informação insuficiente.

REGRA:

Se área, admissibilidade de uso principal ou parâmetros de edificabilidade
determinantes estiverem por confirmar, não atribuir score artificialmente elevado.

================================================================================
13. COERÊNCIA OBRIGATÓRIA
================================================================================

Antes de devolver o JSON verifica:

- Marquei algum uso como "não" sem artigo proibitivo explícito?
- Confundi proibição de loteamento com proibição de edifício multifamiliar?
- Inferi parâmetros apenas pela categoria do solo?
- Inventei alguma percentagem?
- Inventei algum índice?
- Inventei alguma área?
- Transformei morfologia típica numa regra legal?
- Dei status "confirmado" a uma interpretação?
- Ignorei exceções/regimes de colmatação?
- Existe conflito documental não registado?
- Os calculation_inputs contêm apenas valores suficientemente sustentados?

Se alguma resposta indicar risco de falsa certeza, corrige antes de devolver.

================================================================================
14. REFERÊNCIAS
================================================================================

Para cada regra ou condicionante:

- usa referências [1], [2], etc. correspondentes às fontes reais presentes em
  web_context.citations;
- não inventes referências;
- não cites uma fonte que não sustente a afirmação;
- no campo "basis", indica artigo/número/alínea quando essa informação existir.

================================================================================
OUTPUT
================================================================================

DEVOLVE APENAS JSON VÁLIDO.

Não utilizes Markdown.
Não acrescentes explicações antes ou depois do JSON.
Não uses comentários dentro do JSON.

Mantém EXATAMENTE esta estrutura:

{
  "identification": {
    "street_or_place": "",
    "municipality": "",
    "parish": "",
    "location": "",
    "area_m2": null,
    "area_source": "",
    "coordinate_system": "",
    "matrices": [],
    "sources": []
  },

  "planning": {
    "instrument": "",
    "version": "",
    "soil_class": "",
    "category": "",
    "subcategory": "",
    "status": "confirmado|interpretacao|a_confirmar|conflito",
    "basis": "",
    "sources": []
  },

  "uses": [
    {
      "use": "habitação multifamiliar",
      "admissibility": "sim|não|condicionado|a_confirmar",
      "basis": "",
      "sources": []
    }
  ],

  "parameters": {
    "utilization_index": {
      "value": null,
      "unit": "",
      "status": "confirmado|interpretacao|a_confirmar|conflito",
      "basis": "",
      "sources": []
    },
    "occupation_index": {
      "value": null,
      "unit": "",
      "status": "confirmado|interpretacao|a_confirmar|conflito",
      "basis": "",
      "sources": []
    },
    "impermeability_index": {
      "value": null,
      "unit": "",
      "status": "confirmado|interpretacao|a_confirmar|conflito",
      "basis": "",
      "sources": []
    },
    "max_height_m": {
      "value": null,
      "unit": "m",
      "status": "confirmado|interpretacao|a_confirmar|conflito",
      "basis": "",
      "sources": []
    },
    "max_floors_above_ground": {
      "value": null,
      "unit": "pisos",
      "status": "confirmado|interpretacao|a_confirmar|conflito",
      "basis": "",
      "sources": []
    },
    "max_floors_below_ground": {
      "value": null,
      "unit": "pisos",
      "status": "confirmado|interpretacao|a_confirmar|conflito",
      "basis": "",
      "sources": []
    },
    "front_setback_m": {
      "value": null,
      "unit": "m",
      "status": "confirmado|interpretacao|a_confirmar|conflito",
      "basis": "",
      "sources": []
    },
    "side_setback_m": {
      "value": null,
      "unit": "m",
      "status": "confirmado|interpretacao|a_confirmar|conflito",
      "basis": "",
      "sources": []
    },
    "rear_setback_m": {
      "value": null,
      "unit": "m",
      "status": "confirmado|interpretacao|a_confirmar|conflito",
      "basis": "",
      "sources": []
    },
    "parking_rule": {
      "value": "",
      "unit": "",
      "status": "confirmado|interpretacao|a_confirmar|conflito",
      "basis": "",
      "sources": []
    }
  },

  "constraints": [
    {
      "name": "REN",
      "status": "nao_identificado|abrange|parcial|nao_abrange|a_confirmar",
      "impact": "",
      "basis": "",
      "sources": []
    }
  ],

  "physical": {
    "min_elevation_m": null,
    "max_elevation_m": null,
    "elevation_range_m": null,
    "frontages": [],
    "existing_buildings": [],
    "infrastructure": [],
    "notes": []
  },

  "calculation_inputs": {
    "parcel_area_m2": null,
    "utilization_index": null,
    "occupation_index": null,
    "impermeability_index": null,
    "max_height_m": null,
    "max_floors": null
  },

  "critical_questions": [],
  "conflicts": [],

  "overall_readiness": {
    "score": 0,
    "label": "insuficiente|condicionada|boa|muito_boa",
    "reason": ""
  }
}
'''
