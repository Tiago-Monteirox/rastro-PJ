---
status: accepted
---

# O baseline não fabrica aberturas

A primeira competência publicada estabelecerá o estado inicial sem gerar eventos. Nas competências posteriores, uma primeira aparição somente será `ESTABLISHMENT_OPENED` quando a data de início da atividade confirmar que o estabelecimento surgiu naquele intervalo consecutivo.

## Considered Options

- usar baseline sem eventos e exigir evidência temporal para abertura;
- tratar toda primeira aparição como abertura.

## Consequences

Primeiras aparições com data antiga serão alertas `LATE_FIRST_SEEN`; estabelecimentos antes externos que passem ao recorte gerarão `ENTERED_REGION`. O dashboard evita uma abertura em massa artificial no início da janela.
