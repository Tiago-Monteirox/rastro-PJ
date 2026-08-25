---
status: accepted
---

# A janela do MVP é fixa; o motor não

O MVP validará `2025-08` a `2026-08`, mas o manifesto e o motor aceitarão qualquer sequência contínua. Ampliar o período criará nova janela e nova coorte sobre todo o intervalo; não anexará competências antigas à coorte atual como se o resultado fosse regionalmente completo.

## Considered Options

- motor parametrizável com reconstrução integral da coorte;
- número de competências fixo no código;
- backfill antigo somente para a coorte do MVP.

## Consequences

Inicialmente haverá uma única janela ativa. Uma janela ampliada será preparada e validada separadamente e substituirá a anterior de forma atômica, ao custo de regenerar também competências sobrepostas.
