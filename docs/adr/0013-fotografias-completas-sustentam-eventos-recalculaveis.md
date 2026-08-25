---
status: accepted
---

# Fotografias completas sustentam eventos recalculáveis

O PostgreSQL manterá uma fotografia normalizada completa de cada empresa, estabelecimento e participação societária em cada competência publicada. Eventos serão derivados das fotografias consecutivas e poderão ser recalculados sem modificar a evidência de origem.

## Considered Options

- fotografias completas por competência e eventos derivados;
- estado atual acompanhado somente de eventos;
- histórico compactado em intervalos SCD Type 2.

## Consequences

Auditoria, correção de regras e testes ficam mais simples, e o estado atual será consultado na competência mais recente. O custo aceito é repetir atributos inalterados durante 13 competências regionais.

“Completa” significa conter todos os registros oficiais existentes naquela competência que pertençam à coorte fixa da janela. Não significa preencher o passado de um membro que só passou a existir em competência posterior. A ausência histórica real permanece ausência e sustenta eventos de primeira aparição sem fabricar dados retroativos.
