---
status: accepted
---

# Hash de registro representa conteúdo

O `record_hash` será calculado sobre os atributos cadastrais normalizados, excluindo `record_hash` e `competence`. A competência continua obrigatória e participa da identidade da linha no snapshot, mas não do digest de conteúdo usado para detectar mudanças entre meses.

## Context

Na primeira preparação real de julho e agosto de 2026, incluir a competência fazia 100% dos hashes divergirem mesmo quando os atributos permaneciam idênticos. Isso impedia leitura seletiva das mudanças e obrigava o comparador a materializar milhões de registros sem ganho semântico.

## Considered Options

- manter a competência dentro do digest;
- abandonar o hash e comparar sempre todos os campos de todas as linhas;
- separar identidade temporal do snapshot e hash do conteúdo cadastral.

## Consequences

Registros inalterados mantêm o mesmo hash em competências consecutivas. Aparições e desaparecimentos continuam detectáveis pela identidade de negócio, enquanto a unicidade do Parquet permanece composta pela entidade e pela competência. A mudança exige regenerar pacotes produzidos pela definição anterior.
