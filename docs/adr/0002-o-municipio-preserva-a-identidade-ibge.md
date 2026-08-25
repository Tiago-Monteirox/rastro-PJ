---
status: accepted
---

# O município preserva a identidade IBGE

O código IBGE de sete dígitos será a identidade canônica do município. O código TOM de quatro dígitos permanecerá como identificador textual da fonte CNPJ, ligado ao IBGE pela correspondência oficial da Receita; nenhum dos códigos será inferido por nome, truncamento ou conversão numérica.

## Considered Options

- usar o código IBGE como identidade e TOM como referência da fonte;
- usar o código TOM como identidade principal;
- relacionar municípios pelo nome normalizado.

## Consequences

O projeto deverá versionar e validar a correspondência dos 35 municípios. A duplicidade de códigos, a ausência de mapeamento ou uma UF diferente de MG deverá invalidar a importação antes de qualquer alteração no estado válido.
