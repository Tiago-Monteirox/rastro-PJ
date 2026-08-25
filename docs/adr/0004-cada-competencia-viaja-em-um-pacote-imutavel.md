---
status: accepted
---

# Cada competência viaja em um pacote imutável

A preparação produzirá 13 pacotes independentes, um para cada competência, unidos por um manifesto que fixa a janela, a coorte, o recorte e as versões. Um pacote importado não será alterado; uma correção produzirá novo artefato identificável, sem reescrever silenciosamente a janela inteira.

## Considered Options

- um pacote imutável por competência e um manifesto da janela;
- um único pacote com as 13 competências.

## Consequences

Falhas, reprocessamentos e auditorias ficam isolados por competência. Em troca, a aplicação deverá validar que todos os pacotes pertencem à mesma janela e coorte e deverá administrar múltiplos hashes e manifestos.
