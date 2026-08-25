---
status: accepted
---

# Uma competência oficial precisa ser íntegra e consecutiva

Um pacote somente se tornará competência publicada depois de validação e publicação atômicas. Nenhuma comparação ou publicação atravessará uma competência esperada ausente ou inválida; pacotes posteriores poderão aguardar preparados até que a lacuna seja corrigida.

## Considered Options

- publicar atomicamente e exigir sequência completa;
- aceitar carga parcial;
- pular uma competência inválida e comparar as adjacentes disponíveis.

## Consequences

Falhas não alteram a última fotografia válida, e eventos preservam intervalos mensais conhecidos. Em troca, uma única competência inválida bloqueia temporariamente a publicação das posteriores.
