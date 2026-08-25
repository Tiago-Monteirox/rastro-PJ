---
status: accepted
---

# Alertas numerosos bloqueiam a competência

Erros estruturais bloquearão desde a primeira ocorrência. Para cada regra de alerta localizado, a competência falhará quando `affected_rows > max(10, ceil(eligible_rows × 0,001))`. A regra `LATE_FIRST_SEEN` usa a calibração versionada de `0,005`, pois suspende o evento da entidade e representa backfill/latência observável da fonte, não desaparecimento do snapshot.

## Considered Options

- combinar piso absoluto de dez registros com limite proporcional de 0,1%;
- decidir manualmente por competência;
- usar somente percentual ou somente quantidade absoluta.

## Consequences

Ocorrências até o limite permitirão `PUBLISHED_WITH_WARNINGS` e suspenderão somente as entidades afetadas; acima dele, a competência assumirá `FAILED_QUALITY_GATE`. As 13 competências serão medidas antes de congelar o contrato. Qualquer ajuste será versionado e aplicado à janela inteira, nunca feito para aprovar um mês específico.

Na primeira janela real julho–agosto de 2026, `LATE_FIRST_SEEN` ocorreu em 1.241 de 706.151 estabelecimentos (0,176%), o que sustentou uma calibração provisória de 0,25%. A medição longitudinal das 12 comparações oficiais encontrou taxas entre 0,164% e 0,425%, com pico de 2.879 em 677.401 estabelecimentos na comparação janeiro–fevereiro de 2026. Não houve estabelecimento ausente na competência seguinte em nenhum dos 12 intervalos.

Com a série completa, a calibração foi fechada em 0,50%: margem de aproximadamente 17,6% sobre o pico observado, aplicada uniformemente à janela inteira. O teste de fronteira permite as 2.879 ocorrências reais e bloqueia 3.389 em 677.401 elegíveis. O alerta continua persistido e não gera abertura, entrada regional ou outro evento cadastral.
