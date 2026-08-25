---
status: accepted
---

# Falhas sistêmicas bloqueiam; alertas localizados não

Inconsistências estruturais ou sistêmicas impedirão a publicação da competência. Ocorrências isoladas e auditáveis permitirão publicação com alertas, sem gerar eventos para a entidade afetada e sem ocultar o problema.

## Considered Options

- classificar severidade conforme alcance e capacidade de isolamento;
- bloquear toda competência diante de qualquer inconsistência;
- publicar todas as inconsistências apenas como aviso.

## Consequences

O importador terá estados `FAILED` e `PUBLISHED_WITH_WARNINGS` e registrará ocorrências de qualidade. O limite para escalada por volume de alertas dependerá da medição das primeiras competências reais.
