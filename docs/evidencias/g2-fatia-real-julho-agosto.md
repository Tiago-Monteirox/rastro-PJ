# Evidência G2 — fatia real julho/agosto

**Estado:** concluído  
**Data:** 24 de agosto de 2026  
**Ambiente:** Mac local com Docker Compose  
**Fontes:** competências oficiais `2026-07` e `2026-08`  
**Recorte:** os 35 municípios, ampliando a amostra técnica originalmente prevista  
**Publicação externa:** não realizada

## Resultado

A janela real `rf-g2-2026-07-2026-08` atravessou download, verificação SHA-256 das 64 fontes, descoberta da coorte, normalização, geração/validação dos seis Parquets, importação atômica, comparação, quality gate, métricas e publicação. A janela sintética anterior foi marcada `SUPERSEDED` somente no commit final.

Coorte união: **706.151 estabelecimentos**. Julho isolado possuía 701.264; a união acrescentou 4.887 estabelecimentos que tocaram o recorte somente em agosto.

| Competência | Empresas | Estabelecimentos | Sócios | Estado | Warnings |
|---|---:|---:|---:|---|---:|
| 2026-07 | 678.288 | 701.425 | 317.156 | `PUBLISHED_WITH_WARNINGS` | 7 |
| 2026-08 | 682.914 | 706.151 | 318.761 | `PUBLISHED_WITH_WARNINGS` | 1.249 |
| Total | 1.361.202 | 1.407.576 | 635.917 | — | 1.256 |

## Desempenho observado

| Operação | Resultado |
|---|---:|
| primeira preparação correta de julho | 381,62 s |
| preparação final julho + agosto | 766,01 s |
| retomada validada, incluindo hash de 15,3 GB de fontes | 62,77 s |
| importação atômica final | 663,29 s |
| pico observado do importador final | aproximadamente 2,85 GiB |
| reimportação idêntica | no-op em 2,46 s |
| tamanho dos pacotes G2 | 233 MiB |
| tamanho do PostgreSQL após G2 e tentativas revertidas | aproximadamente 2,4 GiB |

O benchmark isolado da materialização Arrow gravou e revalidou 100 mil empresas em 0,598 s. A versão anterior com `executemany` permaneceu 1.616 s sem produzir o artefato final e foi interrompida com segurança.

## Eventos e métricas

Foram publicados **16.706 eventos**, em 15 tipos:

| Evento | Quantidade |
|---|---:|
| `ADDRESS_CHANGED` | 1.146 |
| `COMPANY_SIZE_CHANGED` | 72 |
| `ENTERED_REGION` | 161 |
| `ESTABLISHMENT_CLOSED` | 2.492 |
| `ESTABLISHMENT_OPENED` | 3.485 |
| `LEFT_REGION` | 116 |
| `LEGAL_NATURE_CHANGED` | 327 |
| `MAIN_CNAE_CHANGED` | 950 |
| `MEI_STATUS_CHANGED` | 2.012 |
| `PARTNER_ADDED` | 1.162 |
| `PARTNER_QUALIFICATION_CHANGED` | 202 |
| `PARTNER_REMOVED` | 785 |
| `REGISTRATION_STATUS_CHANGED` | 1.096 |
| `SHARE_CAPITAL_CHANGED` | 637 |
| `SIMPLES_STATUS_CHANGED` | 2.063 |

Também foram persistidas 2.422 métricas mensais regionais.

## Continuidade do sócio PJ

Julho possui 10.443 relações PJ e agosto 10.532. A normalização por raiz produziu:

- 10.407 identidades comuns entre as competências;
- 125 identidades presentes somente em agosto;
- 36 identidades presentes somente em julho;
- zero `partner_cnpj_basic` fora do formato de oito dígitos.

A continuidade foi de 99,66%. Portanto, a mudança da Receita de CNPJ completo para raiz não gerou uma ruptura massiva. Dos eventos publicados e comparáveis, houve 76 adições e 36 remoções PJ; o restante das diferenças pertence a empresas que não eram comparáveis nos dois lados.

## Qualidade e privacidade

Warnings persistidos:

| Regra | Quantidade |
|---|---:|
| `AMBIGUOUS_PARTNER` | 8 |
| `LATE_FIRST_SEEN` | 1.241 |
| `SOURCE_ENCODING_REPLACEMENTS` | 5 |
| `SOURCE_ZERO_DATE` | 2 |

`LATE_FIRST_SEEN` corresponde a 0,176% dos 706.151 estabelecimentos. Essa fatia sustentou o limite provisório de 0,25%; a série oficial de 12 comparações posteriormente fechou a calibração uniforme em 0,50%, conforme o ADR 0018. As entidades continuam suspensas e não fabricam eventos. As demais regras mantêm 0,1%.

A varredura dos 33 campos textuais dos três Parquets encontrou **zero CPF mascarado**. Em julho, 306.527 participações PF foram persistidas sem CPF e todas as 10.436 relações PJ inspecionadas possuíam raiz válida. A geração e a importação também executam a guarda recursiva de privacidade durante o hash canônico.

## Defeitos encontrados e regressões mantidas

1. Bytes indefinidos em Windows-1252 bloqueavam a leitura: transcodificação streaming preserva a linha e contabiliza `U+FFFD`.
2. `registration_status_date = 0` em 1.122/1.123 linhas bloqueava a fonte: sentinela vira `NULL` auditado; outras datas inválidas continuam fatais.
3. Julho entrega sócio PJ com 14 dígitos e agosto com oito: identidade canônica usa a raiz.
4. A coorte união contém empresas ainda inexistentes em julho: snapshots não fabricam passado; estabelecimento presente sem empresa continua fatal.
5. `record_hash` incluía competência e alterava 100% das linhas: passou a representar somente conteúdo.
6. O loader inicial atingiu aproximadamente 5,5 GiB e foi encerrado pelo limite global do Docker: a transação reverteu; carga por tabela e comparação seletiva reduziram o pico para aproximadamente 2,85 GiB.
7. O quality gate genérico bloqueou `LATE_FIRST_SEEN`: a calibração específica foi documentada, testada e aplicada uniformemente à janela.

Ao final, **52 testes** e o lint passaram. As falhas de OOM e quality gate permanecem registradas como batches `FAILED`; a importação final e a reimportação no-op permanecem `COMPLETED`.

## Decisão do gate

**G2 aprovado.** A escala para G3 está liberada com os 35 municípios, 13 competências oficiais, retomada por fingerprint/hash e as mesmas regras de contrato, privacidade e quality gate.
