---
status: accepted
---

# CNEFE alimenta projeção cartográfica derivada

O CNEFE 2022 do IBGE será a referência primária de coordenadas do mapa analítico regional. Suas coordenadas não serão incorporadas como atributos oficiais das fotografias da Receita: uma projeção cartográfica separada, auditável e recalculável relacionará cada ocorrência elegível à localização qualificada. O Mapbox GL JS somente renderizará os dados no navegador.

## Context

As fotografias de estabelecimento possuem endereço e município, mas não latitude e longitude. Geocodificar permanentemente os endereços pela Mapbox Geocoding API geraria custo, enquanto resultados temporários não podem ser persistidos. Os 35 arquivos municipais do CNEFE são públicos, pequenos para o ambiente local e fornecem coordenadas com nível de geocodificação explícito.

O experimento nos 270.411 estabelecimentos ativos de `2026-08` obteve cobertura de 95,18% por CEP e 59,70% por endereço completo. A fonte é de 2022 e possui níveis de precisão distintos; tratá-la como parte da evidência da Receita esconderia origem, incerteza e possibilidade de recálculo.

## Considered Options

- usar geocodificação temporária do Mapbox sem persistência;
- contratar geocodificação permanente do Mapbox;
- gravar latitude e longitude diretamente nas fotografias da Receita;
- calcular coordenadas durante as requisições web;
- usar o CNEFE numa projeção derivada preparada antecipadamente;
- adicionar PostGIS desde a POC.

## Consequences

A Receita continua sendo a fonte da situação cadastral, endereço e competência; o CNEFE fornece somente referência espacial. A resolução preservará método, nível da fonte, candidatos, dispersão e fallback. Mesmas fontes e regras deverão reproduzir a projeção.

A preparação completa ocorrerá manualmente antes das consultas, reutilizando endereços distintos e publicando a nova versão apenas após o quality gate. A última versão válida permanecerá disponível em caso de falha.

O PostgreSQL comum armazenará latitude e longitude numéricas. PostGIS permanece como evolução condicionada a consultas por raio, polígonos, vizinhos, junções espaciais ou insuficiência comprovada dos índices convencionais.

O Mapbox não receberá a base empresarial nem será usado para geocodificação. O token do navegador será público, dedicado, mínimo, restrito a localhost e mantido fora do Git.
