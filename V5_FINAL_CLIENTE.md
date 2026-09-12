# V5 - Fiabilidade, consistência e relatório institucional

Objetivo desta versão: manter praticamente inalterada a utilização da aplicação e corrigir o núcleo de confiança dos resultados antes de novo teste pelo cliente.

## Alterações principais

- Mantido o fluxo atual: 01 Localização -> 02 Documentos -> 03 Análise IA -> 04 Potencial.
- Os parâmetros regulamentares executivos passam a privilegiar o **máximo exato** suportado por norma/fonte, em vez de intervalos de prudência.
- Se implantação/pisos continuarem ambíguos, a aplicação mostra **A confirmar** em vez de um intervalo potencialmente inventado.
- Criado um **registo canónico único** dos principais factos da análise. O mesmo registo alimenta os cartões e o bloco executivo do relatório, evitando interpretações diferentes entre dashboard e PDF.
- Menor variabilidade do motor: temperatura/top_p explicitamente reduzidos nas chamadas de análise.
- Regras reforçadas de hierarquia de evidência: regulamento oficial > cartografia oficial georreferenciada > outros documentos oficiais > documentos fornecidos > interpretação visual da IA.
- Marcações do utilizador em plantas (setas, círculos, cores, etc.) deixam de poder ser tratadas como legenda/classificação oficial.
- Leitura visual de PDM sem confirmação inequívoca fica **A VALIDAR**.
- Cartão "Confiança" substituído por **Evidência** (CONFIRMADO / PROVÁVEL / A VALIDAR / NÃO DETERMINADO), evitando percentagens de confiança artificiais.
- PDF com **capa institucional opcional** usando o logótipo doisarquitectos; as páginas seguintes mantêm a folha-tipo já utilizada.

## Ficheiros alterados

- `app.py`
- `src/gemini_engine.py`
- `src/prompt_loader.py`
- `src/report.py`
- `prompts/canonical_facts_prompt.txt` (novo)
- `assets/cover_logo.png` (novo)

## Validação realizada

- Compilação Python (`py_compile`) concluída sem erros para `app.py`, `src/*.py` e `core/*.py`.
- Geração de PDF testada localmente com capa + folha-tipo.
- PDF renderizado e inspecionado visualmente sem cortes/sobreposições.

## Testes recomendados antes de enviar ao cliente

Executar primeiro os casos reais com resposta conhecida, especialmente o caso Policlínica. Confirmar em execuções repetidas que:

1. o máximo de implantação e o máximo de pisos coincidem com o regulamento;
2. os cartões e o bloco inicial do relatório exibem exatamente os mesmos valores;
3. nenhuma marcação gráfica acrescentada à planta é interpretada como classificação oficial;
4. parâmetros sem evidência suficiente aparecem como `A confirmar`/`A VALIDAR`;
5. o PDF é gerado com e sem capa.
