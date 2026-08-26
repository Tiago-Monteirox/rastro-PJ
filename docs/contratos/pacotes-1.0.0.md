# Contrato dos pacotes históricos 1.0.0

**Estado:** implementado e validado com janela sintética; aguardando gate com duas competências oficiais  
**Formato:** Parquet ZSTD + manifestos JSON UTF-8  
**Privacidade:** CPF completo ou mascarado é proibido em qualquer artefato persistente

## Unidade de publicação

Uma janela contém competências mensais contínuas e uma coorte imutável de CNPJs completos. Cada competência possui um diretório com três Parquets e `package-manifest.json`; a raiz possui `window-manifest.json`.

A coorte é a união dos estabelecimentos que tocaram o recorte regional em qualquer competência da janela. Cada snapshot contém todos os registros oficiais então existentes para essa coorte; membros que ainda não existiam não recebem linhas artificiais em competências anteriores.

```text
window-manifest.json
AAAA-MM/
  companies.parquet
  establishments.parquet
  partners.parquet
  package-manifest.json
```

O manifesto da janela fixa `window_id`, período, recorte, coorte, contrato e hashes dos manifestos mensais. O manifesto mensal repete essas identidades, registra fontes, alertas e os metadados de cada Parquet. Caminhos absolutos ou fora da raiz são rejeitados.

## `companies.parquet`

Identidade: `cnpj_basic + competence`.

| Coluna | Tipo | Nulo |
|---|---|---:|
| `cnpj_basic` | VARCHAR | não |
| `legal_name` | VARCHAR | não |
| `legal_name_search` | VARCHAR | não |
| `legal_nature_code` | VARCHAR | sim |
| `share_capital` | DECIMAL(18,2) | sim |
| `company_size_code` | VARCHAR | sim |
| `simples_optant` | BOOLEAN | sim |
| `simples_option_date` | DATE | sim |
| `simples_exclusion_date` | DATE | sim |
| `mei_optant` | BOOLEAN | sim |
| `mei_option_date` | DATE | sim |
| `mei_exclusion_date` | DATE | sim |
| `competence` | DATE | não |
| `record_hash` | VARCHAR/SHA-256 | não |

## `establishments.parquet`

Identidade: `cnpj + competence`. Somente os CNPJs completos pertencentes à coorte atravessam a fronteira regional; outros estabelecimentos da mesma empresa não são incluídos.

| Coluna | Tipo | Nulo |
|---|---|---:|
| `cnpj`, `cnpj_basic` | VARCHAR | não |
| `branch_type` | VARCHAR | não |
| `trade_name`, `trade_name_search` | VARCHAR | não |
| `registration_status_code` | VARCHAR | não |
| `registration_status_date` | DATE | sim |
| `registration_status_reason_code` | VARCHAR | sim |
| `activity_start_date` | DATE | sim |
| `main_cnae_code` | VARCHAR | sim |
| `street_type`, `street_name`, `street_number` | VARCHAR | não |
| `address_complement`, `neighborhood`, `postal_code` | VARCHAR | não |
| `state_code` | VARCHAR | não |
| `municipality_tom_code` | VARCHAR | não |
| `municipality_ibge_code` | VARCHAR | não |
| `municipality_name` | VARCHAR | não |
| `is_in_region` | BOOLEAN | não |
| `competence` | DATE | não |
| `record_hash` | VARCHAR/SHA-256 | não |

`municipality_name` tornou-se obrigatório antes do primeiro gate real para permitir materializar, sem placeholder, municípios externos observados antes de uma entrada ou depois de uma saída regional. TOM identifica o texto da fonte; IBGE é a identidade canônica.

## `partners.parquet`

Identidade: `cnpj_basic + partner_key + competence`.

| Coluna | Tipo | Nulo |
|---|---|---:|
| `cnpj_basic` | VARCHAR | não |
| `partner_key` | VARCHAR/SHA-256 ou HMAC-SHA-256 | não |
| `partner_type` | `PF`, `PJ` ou `FOREIGN` | não |
| `display_name` | VARCHAR | não |
| `partner_cnpj_basic` | VARCHAR(8) | sim; somente PJ |
| `country_code` | VARCHAR | sim |
| `qualification_code` | VARCHAR | sim |
| `entry_date` | DATE | sim |
| `competence` | DATE | não |
| `record_hash` | VARCHAR/SHA-256 | não |

Para PF, `partner_key` é HMAC-SHA-256 restrito à empresa. O identificador mascarado da fonte existe apenas em memória durante essa transformação e não entra em Parquet, manifesto, PostgreSQL, evento ou log. Para PJ nacional, `partner_key` usa a raiz CNPJ de oito caracteres alfanuméricos, e `partner_cnpj_basic` guarda somente essa raiz. Competências que entregam CNPJ completo são normalizadas para a raiz; competências que já entregam os oito caracteres permanecem inalteradas. Assim, a mudança observada no leiaute da Receita entre julho e agosto de 2026 não produz falsas entradas ou saídas de sócios. Colisões ou identificadores ausentes viram alertas sem expor o valor de origem.

## Validações bloqueantes

- contrato e schema exatos;
- sequência mensal contínua e identidades compatíveis;
- SHA-256 e tamanho de manifestos, fontes e artefatos;
- competência uniforme em todas as linhas;
- identidade não nula e não duplicada;
- hash canônico de cada registro;
- vínculo empresa–estabelecimento–participação;
- correspondência TOM–IBGE e presença regional coerente com o recorte;
- ausência de colunas ou padrões proibidos de CPF;
- publicação atômica, com reimportação idêntica em no-op.

Na preparação, os CSVs originais da Receita são transcodificados em streaming de Windows-1252 para UTF-8 antes da leitura tipada. Bytes indefinidos isolados são substituídos pelo caractere Unicode de reposição e contabilizados como `SOURCE_ENCODING_REPLACEMENTS` no manifesto do pacote; a linha completa nunca é descartada. O adapter foi fixado após a primeira competência real rejeitar tanto a hipótese de Latin-1 estrito quanto Windows-1252 estrito. Os Parquets resultantes usam somente texto Unicode válido.

Nos campos de data, os sentinelas `0` e `00000000` representam ausência e são normalizados como `NULL`. Ocorrências de `0` são contabilizadas como `SOURCE_ZERO_DATE` por tabela e campo; outros valores não vazios que não sejam datas válidas continuam fatais. A competência oficial de julho de 2026 motivou essa regra ao apresentar 1.122 ocorrências em `registration_status_date` dentro da coorte regional.

Os registros validados são materializados em lote colunar via Apache Arrow e inseridos em uma tabela DuckDB criada a partir deste contrato. Essa otimização não altera schemas, hashes canônicos, validações ou a publicação atômica dos Parquets.

`record_hash` representa somente o conteúdo cadastral normalizado: os campos `record_hash` e `competence` são excluídos do digest canônico. A competência continua obrigatória na linha e na identidade do snapshot. Assim, conteúdo inalterado conserva o mesmo hash entre meses e a comparação materializa apenas mudanças, aparições e desaparecimentos.

## Comandos de evidência

```bash
python manage.py validate_window_package CAMINHO/window-manifest.json
python manage.py import_window_package CAMINHO/window-manifest.json
python manage.py recalculate_metrics
```

O código executável do contrato está em `apps/pipeline/contracts/`; este documento explica a interface sem substituí-lo.
