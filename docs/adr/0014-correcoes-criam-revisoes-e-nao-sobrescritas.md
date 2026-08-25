---
status: accepted
---

# Correções criam revisões e não sobrescritas

Importar novamente a mesma competência e o mesmo hash será uma operação idempotente. Um hash diferente exigirá revisão explícita: a versão corrigida será validada em staging e substituirá atomicamente a revisão ativa, preservando a anterior como substituída.

## Considered Options

- criar revisão auditável e substituí-la atomicamente;
- apagar e reimportar a competência no mesmo lugar;
- aceitar automaticamente qualquer novo hash.

## Consequences

Uma correção recalculará métricas da competência e eventos dos intervalos adjacentes. Mudança de janela, coorte, recorte ou contrato exigirá nova preparação completa, não correção mensal.
