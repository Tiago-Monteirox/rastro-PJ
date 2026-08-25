---
status: accepted
---

# A raiz CNPJ estabiliza a identidade do sócio PJ

A identidade canônica de um sócio pessoa jurídica nacional usa a raiz CNPJ de oito dígitos. Quando a Receita entregar 14 dígitos, a preparação conservará apenas os oito primeiros; quando entregar oito, usará o valor diretamente. A chave da participação continuará restrita à empresa investida e será derivada dessa raiz normalizada.

## Context

Nos ZIPs oficiais observados, julho de 2026 entrega o identificador dos sócios PJ nacionais com 14 dígitos e agosto de 2026 passa a entregá-lo com oito. Usar o texto bruto faria a mesma relação societária trocar de identidade na fronteira do leiaute e produziria falsos eventos de remoção e adição.

## Considered Options

- usar o identificador bruto de cada competência;
- recorrer ao nome quando a fonte trouxer somente oito dígitos;
- normalizar os formatos de 14 e oito dígitos para a raiz CNPJ.

## Consequences

A comparação julho–agosto permanece estável e o contrato passa a expor `partner_cnpj_basic`, nunca um CNPJ completo cujo estabelecimento não seja semanticamente relevante para a participação. Pessoas físicas continuam usando HMAC e nenhum CPF completo ou mascarado persiste.
