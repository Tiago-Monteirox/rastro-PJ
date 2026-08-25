---
status: accepted
---

# Parquet é materializado em lote colunar

Depois da validação individual dos registros, a preparação converterá o lote para uma tabela Apache Arrow, registrará essa tabela no DuckDB e fará um único `INSERT ... SELECT` para a tabela tipada do contrato. A exportação Parquet continuará comprimida, validada e publicada por substituição atômica.

## Context

No primeiro smoke oficial de julho de 2026, a inserção com `executemany` permaneceu mais de 26 minutos consumindo CPU sem produzir o artefato final. Com a carga colunar, um benchmark do mesmo contrato gravou e revalidou 100 mil empresas em 0,598 segundo, e o pacote completo de julho terminou em 381,62 segundos, incluindo hashes das fontes, duas leituras dos ZIPs, normalização, três Parquets e validações.

## Considered Options

- manter uma inserção Python por linha;
- escrever um CSV intermediário adicional e relê-lo;
- reproduzir todo o contrato e os hashes em SQL específico;
- usar a integração colunar Arrow suportada pelo DuckDB e manter a tabela de destino tipada.

## Consequences

O contrato, os tipos DuckDB, as verificações de privacidade e a atomicidade não mudam. A dependência PyArrow aumenta a imagem local, mas reduz em mais de quatro vezes o smoke observado e torna viável preparar as 13 competências no prazo do projeto.
