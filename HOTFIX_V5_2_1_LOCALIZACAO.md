# V5.2.1 — Hotfix de Localização

Sem alterações visuais à interface.

- Geocodificação com fallback automático Nominatim -> ArcGIS World Geocoding Service.
- Reverse geocoding do clique no mapa com o mesmo fallback.
- Aceita coordenadas `latitude, longitude` diretamente no campo de pesquisa.
- Mantém filtro para Portugal.
- Evita que falha/rate-limit de um único fornecedor bloqueie a Etapa 01.

Testes recomendados após deploy:
1. `Rua dos Juncais, Sandim`
2. `Largo de São Marcos, Albergaria-a-Velha, Aveiro`
3. `Albergaria-a-Velha, Aveiro`
4. clique no mapa e confirmação do endereço.
