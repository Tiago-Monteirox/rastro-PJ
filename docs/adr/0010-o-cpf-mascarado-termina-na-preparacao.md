---
status: accepted
---

# O CPF mascarado termina na preparação

A preparação converterá a participação de sócio PF em uma identidade pseudônima por HMAC restrita à empresa e eliminará o CPF mascarado antes de gerar os pacotes. A chave não permitirá relacionar a mesma pessoa globalmente entre empresas.

## Considered Options

- pseudonimizar durante a preparação e omitir o CPF dos pacotes;
- transportar CPF mascarado e pseudonimizar somente na importação.

## Consequences

Os pacotes, o PostgreSQL, os logs e os relatórios não conterão CPF completo ou mascarado. A chave dependerá de segredo externo e regra estável; sua alteração exigirá regenerar os pacotes, e correções de nome poderão aparecer como remoção e inclusão.
