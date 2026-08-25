---
status: accepted
---

# A preparação e a importação formam um ETL em dois estágios

O monólito terá uma preparação da janela histórica, que reduz fontes nacionais oficiais a pacotes regionais, e uma importação da competência, que valida esses pacotes e os incorpora ao PostgreSQL. Ambos são processos automatizados iniciados manualmente; nenhum deles exige edição manual de dados ou serviço distribuído.

## Considered Options

- separar preparação pesada e importação funcional por uma fronteira auditável de arquivos;
- processar ou restaurar a base nacional diretamente durante a operação da aplicação.

## Consequences

O mesmo projeto passa a oferecer dois comandos documentados e serviços internos reutilizáveis. A interface web permanece independente do volume nacional, enquanto os pacotes intermediários exigem contrato, versionamento, validação e política de retenção.
