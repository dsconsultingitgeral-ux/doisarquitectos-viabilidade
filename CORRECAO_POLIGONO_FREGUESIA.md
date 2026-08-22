# Correção final — desenho do terreno e freguesia

- Separados os modos **Selecionar localização** e **Desenhar terreno**.
- No modo desenho, os cliques dos vértices já não disparam reverse geocoding nem rerun da morada.
- Polígono e retângulo ficam guardados na sessão e reaparecem no mapa.
- O perímetro desenhado é enviado como contexto aproximado para a análise IA.
- Freguesia passa a usar uma hierarquia mais robusta de campos OpenStreetMap/Nominatim.
- Quando o campo administrativo `parish` não existe, a aplicação usa a melhor designação territorial disponível sem copiar o município.
