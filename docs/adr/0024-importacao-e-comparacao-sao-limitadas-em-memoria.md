---
status: accepted
---

# Importação e comparação são limitadas em memória

A importação lerá, validará e persistirá `companies`, `establishments` e `partners` separadamente, com `bulk_create` em chunks. A comparação consecutiva fará `FULL OUTER JOIN` dos Parquets pela identidade de negócio e materializará em Python apenas linhas cujo hash de conteúdo difira ou que existam em somente um lado.

## Context

A primeira tentativa de importar as duas competências reais manteve simultaneamente os três conjuntos de linhas, mapas ORM completos da competência anterior e atual e grandes listas de objetos. O processo atingiu aproximadamente 5,5 GiB e foi encerrado pelo limite global de 8 GiB da VM Docker, que também hospedava outros projetos. A transação foi revertida integralmente.

## Considered Options

- aumentar a memória local e manter o algoritmo;
- desligar outros projetos como pré-requisito operacional;
- importar uma tabela por vez e usar os Parquets/hashes para reduzir a comparação;
- migrar o MVP para serviços distribuídos.

## Consequences

O monólito e a atomicidade são preservados, mas o pico deixa de crescer com todas as tabelas e duas competências completas ao mesmo tempo. Entidades ORM para eventos são consultadas somente para os candidatos efetivamente gerados. O registro do OOM permanece no histórico de batches como evidência de falha recuperada.
