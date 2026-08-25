---
status: accepted
---

# Empresa e estabelecimento possuem ciclos distintos

Eventos corporativos e societários pertencem à empresa identificada pelo CNPJ básico; eventos cadastrais, geográficos e de atividade pertencem ao estabelecimento identificado pelo CNPJ completo. Abertura ou baixa de uma filial não será apresentada como criação ou encerramento da empresa.

## Considered Options

- modelar e contar empresa e estabelecimento separadamente;
- expor todos os eventos sob o conceito genérico de empresa.

## Consequences

Eventos deverão declarar o tipo e a identidade da entidade afetada. Dashboard, filtros, testes e textos de interface distinguirão empresas de estabelecimentos, evitando indicadores semanticamente falsos.
