---
status: accepted
---

# Fontes são transcodificadas sem descartar linhas

Os CSVs compactados da Receita serão transcodificados em streaming de Windows-1252 para UTF-8 antes da leitura pelo DuckDB. Bytes indefinidos isolados serão substituídos por `U+FFFD`, contados por arquivo e registrados como warning no manifesto.

## Context

A competência real de julho de 2026 contém bytes que não são aceitos nem pelo decoder Latin-1 nem pelo decoder CP1252 estrito do DuckDB. A primeira ocorrência observada estava em um campo fora do contrato do MVP, mas fazia o leitor rejeitar a linha inteira antes do filtro regional.

## Considered Options

- ativar `ignore_errors` e perder toda linha que contivesse um byte inválido;
- tratar a competência como fatal e impedir o uso da fonte oficial;
- transcodificar a fonte, preservar a linha e auditar somente as substituições pontuais.

## Consequences

Nenhum estabelecimento é removido silenciosamente por sujeira em um campo descartado. Os hashes continuam referindo-se aos ZIPs originais imutáveis; a transformação UTF-8 é temporária, reproduzível e removida ao fim de cada leitura. Um volume excessivo de warnings continua sujeito ao quality gate aprovado.
