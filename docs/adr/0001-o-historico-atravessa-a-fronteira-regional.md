---
status: accepted
---

# O histórico atravessa a fronteira regional

Um estabelecimento integra a coorte quando possui ao menos uma ocorrência nos 35 municípios durante a janela aprovada. Preservaremos suas 13 fotografias mesmo antes da entrada ou depois da saída da região, pois filtrar cada competência isoladamente confundiria mudança geográfica com baixa, ausência ou falha de dados.

## Considered Options

- filtrar cada competência somente pelos municípios do recorte;
- formar primeiro a coorte regional e depois recuperar seu histórico completo.

## Consequences

A extração passa a ter duas etapas e armazena algumas fotografias externas adicionais. Em contrapartida, permite reconhecer entradas e saídas regionais e mantém as métricas regionais restritas às ocorrências dentro dos 35 municípios.
