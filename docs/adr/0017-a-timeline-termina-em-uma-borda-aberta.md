---
status: accepted
---

# A timeline termina em uma borda aberta

A primeira competência será o baseline sem eventos, e a última representará somente o estado mais recente observado. Eventos pertencerão ao intervalo entre duas competências consecutivas; nenhuma alteração será inferida depois da borda final.

## Considered Options

- representar mudanças no intervalo observado e manter a borda final aberta;
- atribuir toda mudança a um dia convencional e considerar o último estado válido indefinidamente.

## Consequences

Datas explícitas da Receita poderão servir como evidência, enquanto `detected_at` registrará apenas o instante do cálculo. Uma competência futura somente produzirá comparação com a anterior dentro de uma janela validada que contenha ambas. A timeline terá precisão mensal quando a fonte não fornecer uma data efetiva.
