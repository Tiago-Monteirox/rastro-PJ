# Evidência G3–G5 — janela oficial e produto integrado

**Estado:** G3, G4 e G5 concluídos tecnicamente  
**Data da consolidação:** 25/08/2026  
**Janela:** `2025-08..2026-08`  
**Recorte:** Triângulo Mineiro, 35 municípios  
**Ambiente:** Mac local, Docker Compose, Django 5.2 e PostgreSQL

Este registro consolida evidências técnicas internas. A regressão G6 foi fechada em documento próprio e não antecipa a homologação de Gabriel, Emili ou do professor.

## G3 — dados oficiais

A preparação oficial gerou 13 pacotes imutáveis, todos ligados ao mesmo manifesto de janela, coorte, recorte e contrato. A janela contém as competências consecutivas de agosto de 2025 a agosto de 2026 e forma 12 comparações.

| Evidência | Resultado |
|---|---:|
| competências | 13 |
| comparações possíveis | 12 |
| empresas na coorte | 707.670 |
| linhas em `companies.parquet` | 8.509.822 |
| linhas em `establishments.parquet` | 8.804.270 |
| linhas em `partners.parquet` | 4.018.362 |
| linhas Parquet totais | 21.332.454 |
| Parquets | 39 |
| manifestos auditados | 14 |

A presença regional foi determinada por qualquer estabelecimento que tenha ocorrido em um dos 35 municípios em alguma competência. A matriz não precisa estar na região. O histórico preserva fotografias externas do estabelecimento pertencente à coorte, mas métricas regionais só contam a competência em que `is_in_region` é verdadeiro.

IBGE textual de sete dígitos é a identidade canônica municipal; TOM textual de quatro dígitos preserva a identidade recebida da Receita. A validação conserva zeros à esquerda e exige os 35 pares únicos do recorte.

## G4 — núcleo histórico

Os pacotes sanitizados foram publicados como revisão `r2` em cada uma das 13 competências. O lote que publicou as substitutas foi `33209e01-dd28-4191-b658-fcbe6eee9c66`, concluído com fase `revision_published`.

| Persistência da janela ativa | Contagem |
|---|---:|
| revisões ativas `r2` | 13 |
| fotografias de empresa | 8.509.822 |
| fotografias de estabelecimento | 8.804.270 |
| fotografias societárias | 4.018.362 |
| eventos derivados | 278.301 |
| métricas derivadas | 15.751 |

As fotografias completas são a fonte persistente. Eventos e métricas permanecem derivados e recalculáveis. O recálculo de métricas produziu as 15.751 linhas esperadas; 39 delas pertencem a `REGIONAL_COMPANIES_BY_SIZE`, cobrindo os três agrupamentos de porte nas 13 competências. Na competência mais recente, a soma dos portes representa 682.799 empresas regionais distintas.

O comparador implementa os dez eventos P0 e os cinco eventos P1 definidos para novembro:

- estabelecimento: abertura, baixa, situação, endereço, CNAE principal, entrada e saída regional;
- empresa: capital social, natureza jurídica, porte, Simples e MEI;
- sociedade: inclusão, remoção e mudança de qualificação.

O baseline não fabrica eventos. A abertura usa o intervalo `(competência anterior, competência atual]`; uma aparição com início antigo gera `LATE_FIRST_SEEN`. Ausência é ocorrência de qualidade, não baixa ou saída. O recálculo usa somente competências adjacentes e não infere fatos depois de `2026-08`.

## Correção de privacidade e revisão

A fonte passou a fornecer somente a raiz de oito dígitos para todo sócio PJ nacional a partir de agosto. A normalização aceita tanto os 14 dígitos históricos quanto a raiz nova e persiste sempre os oito primeiros, evitando falsa remoção/inclusão por mudança de formato.

Para PF, o CPF mascarado existe somente no workspace de preparação. A chave societária é HMAC restrita à empresa; CPF, representante, CPF do representante e faixa etária não entram no pacote ou banco funcional.

A auditoria também encontrou a possibilidade de uma sequência semelhante a documento pessoal ocorrer incidentalmente em campos humanos. A revisão `r2` sanitiza esses trechos sem excluir a empresa de sua coorte. Depois da publicação das substitutas:

- snapshots das revisões inseguras foram expurgados;
- pacotes substituídos inseguros foram removidos;
- revisão, pacote hash, batch e ocorrências de qualidade foram preservados;
- fontes nacionais permaneceram somente no workspace temporário aprovado.

Esse comportamento é a exceção de privacidade definida nos ADRs 0016 e 0025.

### Auditorias

- pacotes ativos: 14 manifestos, 39 Parquets, 21.332.454 linhas e 429 combinações arquivo/coluna, sem ocorrência proibida;
- PostgreSQL persistente: auditoria global corrigida encerrada com `blocking_total=0`;
- eventos `SHARE_CAPITAL_CHANGED`: números de capital foram tratados como dimensão monetária, não como documento pessoal;
- revisões ativas: nenhum nome, texto de busca, endereço, sócio, JSON de evento ou metadado auditado apresentou bloqueio.

## Idempotência e revisão explícita

Quando todas as competências e hashes do manifesto já correspondem às revisões ativas, a importação:

1. valida novamente janela, pacotes, hashes e artefatos;
2. preserva as revisões ativas e derivados;
3. conclui um `ImportBatch` próprio;
4. grava `phase = "no_op"` e `counters.no_op = true`;
5. retorna `imported = false` sem duplicar snapshots, eventos ou métricas.

Hash diferente exige `--allow-revision`. O teste de integração comprova staging, substituição atômica, revisão anterior `SUPERSEDED`, recálculo dos intervalos adjacentes e preservação da ativa se o quality gate reprovar a candidata.

A reimportação oficial executada em 25/08/2026 foi concluída em aproximadamente 2,61 s:

| Campo do batch | Valor |
|---|---|
| `id` | `842ce935-854b-4d8c-81c0-be67a0a0bf3d` |
| `status` | `COMPLETED` |
| `phase` | `no_op` |
| `counters.no_op` | `true` |
| competências | 13 |
| eventos preservados | 278.301 |
| alertas preservados | 21.169 |
| manifesto alterado | `false` |

## G5 — produto integrado

O portal local usa somente a janela ativa e suas revisões publicadas:

- dashboard em `/`;
- busca com CNPJ, razão social, nome fantasia, município, situação e CNAE em `/empresas/`;
- detalhe, estabelecimentos, sociedade e timeline em `/empresas/<cnpj-basico>/`;
- eventos filtráveis em `/eventos/`;
- watchlist autenticada em `/monitoradas/`;
- lotes, revisões, proveniência e alertas em `/importacoes/`;
- healthcheck em `/health/`.

As telas são Django Templates com HTML, CSS e JavaScript simples, dentro do mesmo monólito das regras e do ORM. Não existe SPA ou API pública.

## Desempenho observado no volume oficial

| Consulta | Tempo observado |
|---|---:|
| dashboard padrão | 95 ms |
| dashboard com filtros | 204 ms |
| busca sem termo | 6 ms |
| busca com termo | 12 ms |
| detalhe da empresa | 26 ms |
| eventos padrão | 363 ms |
| eventos por CNPJ, após correção | 55 ms |

Todos os caminhos medidos ficaram abaixo da meta de dois segundos. Esses valores são observações do Mac-alvo, não promessa de latência em outra máquina nem percentil estatístico de produção.

## Qualidade técnica

| Verificação | Resultado |
|---|---|
| suíte Django em PostgreSQL | 67/67 aprovados em 3,193 s |
| `ruff check .` | aprovado |
| `ruff format --check .` | 104 arquivos conformes |
| `manage.py check` | aprovado |
| `makemigrations --check --dry-run` | nenhuma migração pendente |
| `docker compose config --quiet` | aprovado |

Os testes temporais cobrem baseline, apenas pares adjacentes, intervalo de abertura, `LATE_FIRST_SEEN`, ausência sem evento e borda aberta por ausência de comparação posterior. A expansão completa para uma nova janela anterior ou futura continua como cenário de aceite pendente, sem alterar a extensibilidade prevista pelo contrato.

## Situação dos gates

| Gate | Estado em 25/08/2026 | Observação |
|---|---|---|
| G3 — dados oficiais | concluído tecnicamente | 13 pacotes e privacidade validados |
| G4 — núcleo histórico | concluído tecnicamente | 13 `r2`, 12 intervalos, 15 tipos de evento e derivados persistidos |
| G5 — produto integrado | concluído tecnicamente | portal conectado à janela ativa e desempenho abaixo da meta |
| G6 — MVP interno | candidata técnica interna aprovada | 67 testes e auditorias finais aprovados; homologações externas à execução técnica permanecem pendentes |

Consulte a [regressão G6](g6-regressao-interna.md) e a [matriz de 34 cenários](../matriz-aceitacao-mvp.md) para distinguir cobertura automatizada, verificação oficial, cobertura parcial e homologação pendente.
