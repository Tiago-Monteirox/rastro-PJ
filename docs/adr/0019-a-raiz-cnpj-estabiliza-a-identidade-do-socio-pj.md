---
status: accepted
---

# A raiz CNPJ estabiliza a identidade do sócio PJ

A identidade canônica de um sócio pessoa jurídica nacional usa o CNPJ básico de oito caracteres alfanuméricos. Quando a Receita entregar o CNPJ completo com 14 caracteres, a preparação conservará apenas os oito primeiros; quando entregar oito, usará o valor diretamente. A chave da participação continuará restrita à empresa investida e será derivada dessa raiz normalizada.

## Context

Nos ZIPs oficiais observados, julho de 2026 entrega o identificador dos sócios PJ nacionais com 14 caracteres e agosto de 2026 passa a entregá-lo com oito. Usar o texto bruto faria a mesma relação societária trocar de identidade na fronteira do leiaute e produziria falsos eventos de remoção e adição. A partir do CNPJ alfanumérico, qualquer uma dessas posições pode conter letras quando prevista pelo formato oficial.

## Considered Options

- usar o identificador bruto de cada competência;
- recorrer ao nome quando a fonte trouxer somente oito caracteres;
- normalizar os formatos de 14 e oito caracteres para o CNPJ básico.

## Consequences

A comparação julho–agosto permanece estável e o contrato passa a expor `partner_cnpj_basic`, nunca um CNPJ completo cujo estabelecimento não seja semanticamente relevante para a participação. Pessoas físicas continuam usando HMAC e nenhum CPF completo ou mascarado persiste.
