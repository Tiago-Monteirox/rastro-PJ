---
status: accepted
---

# Ausência cadastral não prova encerramento

O desaparecimento de uma empresa ou estabelecimento entre competências será uma ocorrência de qualidade de dados, nunca evidência suficiente de encerramento ou saída regional. Eventos de negócio exigirão uma transição explícita entre fotografias consecutivas.

## Considered Options

- suspender a comparação da entidade e registrar a ausência;
- inferir encerramento ou saída quando o registro desaparecer.

## Consequences

`ESTABLISHMENT_CLOSED` dependerá de situação baixada e `LEFT_REGION` dependerá de nova localização externa. Algumas entidades poderão exibir lacunas sem evento, preservando a precisão e a auditabilidade da informação.
