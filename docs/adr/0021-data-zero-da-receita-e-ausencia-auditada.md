---
status: accepted
---

# Data zero da Receita é ausência auditada

Os valores `0` e `00000000` em campos de data da Receita serão normalizados como ausência (`NULL`). Cada ocorrência de `0` será contada por tabela e campo e registrada como `SOURCE_ZERO_DATE` no manifesto. Qualquer outro valor não vazio que não represente uma data válida continuará bloqueando a preparação.

## Context

Na coorte regional da competência oficial de julho de 2026, 1.122 estabelecimentos possuem `registration_status_date` igual a `0`. Descartar essas linhas eliminaria empresas reais; inventar uma data alteraria o significado cadastral; e tratar o sentinela conhecido como fatal impediria o uso da própria fonte oficial.

## Considered Options

- rejeitar toda a competência por causa do sentinela;
- descartar os 1.122 estabelecimentos afetados;
- substituir por uma data arbitrária;
- representar a ausência como `NULL`, preservar a linha e auditar a contagem.

## Consequences

O snapshot preserva os estabelecimentos sem fabricar informação temporal. O warning torna a decisão rastreável e sujeita ao quality gate. A tolerância permanece estreita: erros de formato diferentes dos dois sentinelas conhecidos continuam fatais.
