# V6.1 FINAL CLIENTE

Correção estrutural final do motor documental.

- Todos os ficheiros carregados entram num índice determinístico antes da chamada à IA.
- Preserva o nome original de cada ficheiro junto da referência enviada ao Gemini.
- PDFs recebem extração textual local auxiliar (quando possível) para não perder quadros-síntese e rótulos de projeto.
- Deteta automaticamente sinais de Projeto / Estudo / PIP.
- Se existir projeto candidato, é proibido concluir "não existe proposta" sem o analisar.
- Se a primeira resposta ainda ignorar uma proposta detetada, o motor executa uma única correção automática focada.
- Mantém uma única chamada principal nos casos normais; a segunda chamada só ocorre quando existe contradição objetiva.
- Mantém a interface existente e a capa institucional automática.
- Upload manual de capa removido.
