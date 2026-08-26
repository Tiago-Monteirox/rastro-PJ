# Backend CNPJ Regional — plano técnico de implementação

**Estado:** aprovado para implementação local  
**Versão:** 1.0 — aprovada  
**Data:** 24 de agosto de 2026  
**Responsável técnico:** Tiago, Tech Lead  
**Revisores:** Gabriel, QA Lead; Emili, Scrum Master e UX/UI  
**Marco interno:** 30 de setembro de 2026  
**Autorização registrada:** Tiago autorizou o início do desenvolvimento local em 24 de agosto de 2026. Publicação externa e envio ao GitHub permanecem fora do escopo desta autorização.

## 1. Objetivo do plano

Converter as decisões aprovadas em uma sequência implementável, testável e compatível com a capacidade da equipe. O plano cobre fundação do monólito, contratos dos pacotes, preparação regional, persistência, importação, eventos P0, métricas, consultas, telas mínimas e gate do MVP interno.

Este documento deriva de:

- [`backend-cnpj-regional-validacao-arquitetural.md`](backend-cnpj-regional-validacao-arquitetural.md);
- [`backend-cnpj-regional-decision-ledger.md`](backend-cnpj-regional-decision-ledger.md);
- [`modelagem-banco-dados.md`](modelagem-banco-dados.md);
- [`arquitetura-geral.canvas`](arquitetura-geral.canvas);
- [`../CONTEXT.md`](../CONTEXT.md);
- [`../PROJETO.md`](../PROJETO.md);
- ADRs [`0001`](adr/0001-o-historico-atravessa-a-fronteira-regional.md) a [`0018`](adr/0018-alertas-numerosos-bloqueiam-a-competencia.md).

O plano não reabre semântica de produto. Se dados reais contradisserem uma premissa, a tarefa volta ao ledger antes de alterar regra, contrato ou escopo.

## 2. Princípios de implementação

1. **Fatia vertical antes da escala:** uma competência real deve atravessar contrato, staging, PostgreSQL e uma consulta antes da janela completa.
2. **Comandos finos, serviços explícitos:** management commands cuidam de argumentos, progresso e erros; regras ficam em serviços testáveis.
3. **Sem comportamento crítico escondido:** importação, publicação, eventos e métricas não dependerão de signals do Django.
4. **Invariantes também no banco:** unicidade, revisão ativa, integridade temporal e valores válidos usarão constraints quando tecnicamente aplicável.
5. **Validação pesada antes da transação:** hashes, schemas e contagens serão verificados antes da publicação; a transação atômica será curta e explícita.
6. **Snapshots são evidência; eventos são projeções:** comparadores nunca substituem os estados de origem.
7. **Processamento maior que a memória:** não carregar uma fonte nacional inteira em DataFrame; DuckDB deverá derramar para disco com limites configuráveis.
8. **Privacidade verificável:** CPF mascarado será tratado como dado proibido fora do workspace temporário e terá testes negativos.
9. **Uma importação por vez:** sem Celery, RabbitMQ, cron ou concorrência de lotes no MVP.
10. **Otimização guiada por medição:** índices, tamanho de lote e mecanismo de carga serão escolhidos com a competência real, não por palpite.

## 3. Stack proposta

| Camada | Escolha proposta | Motivo | Gate |
|---|---|---|---|
| Linguagem | Python 3.13.13, fixado por imagem e arquivo de versão | Reprodutibilidade e compatibilidade | Patch fixado na fundação |
| Framework | Django 5.2.17 LTS | Requisito aprovado e monólito completo | Não migrar de série durante o MVP |
| Banco funcional | PostgreSQL 17 Alpine, imagem fixada por digest no Compose | Constraints, transações, índices e JSONB | Major fixado antes da primeira migration |
| ETL analítico | DuckDB 1.5.5 embarcado no processo Python | Leitura SQL, Parquet e spill para disco sem serviço adicional | Confirmar no spike da primeira competência |
| Driver PostgreSQL | Psycopg 3.2.13 | Driver atual e possibilidade de `COPY` | Mecanismo de carga depende de benchmark |
| Frontend | Django Templates, HTML, CSS e JavaScript simples | Mantém monólito e reduz curva da equipe | Sem SPA ou AngularJS |
| Testes | Runner nativo do Django com `SimpleTestCase`, `TestCase` e `TransactionTestCase` | Menos ferramentas e cobertura das transações reais | Relatório de cobertura pode ser agregado depois |
| Ambiente | Docker Compose local | Inicialização reproduzível de app e banco | Sem deploy de produção |

Versões exatas foram registradas no `uv.lock`; as imagens do Python, uv e PostgreSQL foram fixadas por digest na fundação.

### Configuração inicial recomendada do DuckDB

Valores iniciais, sujeitos à medição:

- `memory_limit`: 6 GiB;
- `threads`: 2;
- `temp_directory`: diretório explícito dentro do workspace ignorado pelo Git;
- compressão Parquet: Zstandard;
- schema de leitura: sempre explícito para códigos, datas e decimais;
- preflight de disco: referência conservadora inicial de 200 GiB livres para a preparação nacional completa.

Em um Mac de 16 GiB, dois threads e 6 GiB deixam margem para sistema operacional, Docker e PostgreSQL. Se o preflight falhar, a execução completa será bloqueada e o plano de armazenamento voltará para decisão; a janela não será reduzida silenciosamente.

## 4. Arquitetura interna do monólito

```text
config/                         configuração, URLs raiz e ASGI/WSGI
apps/
  geography/                   municípios, recorte e TOM–IBGE
  registry/                    empresas, estabelecimentos, sócios e snapshots
  pipeline/                    janelas, pacotes, lotes, staging e qualidade
  changes/                     comparadores, eventos e métricas
  portal/                      views, forms, URLs, templates e navegação
```

Esses diretórios são Django apps internos no mesmo processo e no mesmo banco. Não são serviços, APIs independentes ou unidades de deploy.

A visão geral navegável está no Canvas [`arquitetura-geral.canvas`](arquitetura-geral.canvas). A estrutura relacional completa está em [`modelagem-banco-dados.md`](modelagem-banco-dados.md).

### Responsabilidade por módulo

| Módulo | Possui | Não deve possuir |
|---|---|---|
| `geography` | `Municipality`, `GeographicScope`, associação dos 35 e validação TOM–IBGE | snapshots ou lógica de evento |
| `registry` | entidades cadastrais, snapshots e consultas de estado observado | download, staging ou publicação de lote |
| `pipeline` | janela, competência, revisão, manifesto, batch, staging lógico, qualidade, preparação e importação | regras de UI ou evento específico |
| `changes` | comparadores puros, precedência, `ChangeEvent` e métricas | leitura da fonte nacional |
| `portal` | camada web e autorização de acesso | regras de ETL, comparação ou persistência duplicadas |

### Organização interna implementada

Cada app manterá estrutura rasa. Serviços serão usados onde há um caso de uso transacional ou uma regra que cruza modelos. Não será criado um “repository pattern” genérico sobre o ORM.

```text
pipeline/
  management/commands/
    prepare_rf_window.py
    validate_window_package.py
    import_window_package.py
    recalculate_events.py
    recalculate_metrics.py
  services/
    rf_prepare.py
    package_validation.py
    window_import.py
    normalization.py
    parquet.py
  contracts/
    manifests.py
    schemas.py
```

## 5. Modelo físico proposto

Os nomes são propostas técnicas; as identidades e invariantes vêm do documento validado.

### Catálogo e janela

| Modelo | Finalidade | Restrições principais |
|---|---|---|
| `Municipality` | catálogo IBGE, TOM, nome e UF, inclusive para locais externos da coorte | IBGE textual único; TOM textual único; formatos válidos |
| `GeographicScope` | versão identificável do conjunto regional | código + versão únicos; hash dos municípios |
| `ScopeMunicipality` | associação entre recorte e município | escopo + município únicos; 35 associações no MVP |
| `HistoricalWindow` | período, coorte, recorte, contrato e estado da janela | somente uma janela ativa; início ≤ fim |
| `WindowCompetence` | posição esperada de cada `AAAA-MM` na janela | competência única na janela; ordem contínua |
| `SourceArtifact` | URL, nome, tamanho, hash e competência da fonte | identidade por fonte/competência/hash |
| `PackageArtifact` | caminho, hash, schema, contagem e estado do pacote | pacote pertence a uma janela e competência |

A competência será persistida como `DateField` normalizado para o primeiro dia do mês e exibida como `AAAA-MM`. Isso permite ordenação e constraints sem armazenar uma data diária fictícia do evento.

### Entidades e snapshots

| Modelo | Identidade estável | Snapshot por revisão |
|---|---|---|
| `Company` | CNPJ básico textual de 8 dígitos | `CompanySnapshot` com razão social, natureza, capital, porte, Simples e MEI |
| `Establishment` | CNPJ completo textual de 14 dígitos | `EstablishmentSnapshot` com situação, atividade, endereço, município e presença regional |
| `PartnerParticipation` | empresa + chave conforme tipo do sócio | `PartnerSnapshot` com nome, tipo, PJ/país, qualificação e entrada |

Cada snapshot referenciará uma `CompetenceRevision`, não apenas o mês. Assim, revisões substituídas continuam auditáveis sem competir com a revisão ativa.

### Importação, qualidade e revisão

| Modelo | Finalidade | Estado mínimo |
|---|---|---|
| `CompetenceRevision` | versão de uma competência dentro da janela | `STAGING`, `PUBLISHED`, `PUBLISHED_WITH_WARNINGS`, `SUPERSEDED`, `FAILED_QUALITY_GATE`, `FAILED` |
| `ImportBatch` | tentativa operacional e observabilidade | recebido, validando, carregando, publicando, concluído ou falhou |
| `DataQualityIssue` | regra, severidade, contagem e entidade afetada | fatal ou localizado; nunca evento cadastral |

### Projeções derivadas

| Modelo | Finalidade | Chave lógica |
|---|---|---|
| `ChangeEvent` | mudança entre duas revisões consecutivas | janela + revisões + entidade + dimensão + tipo |
| `RegionalMonthlyMetric` | indicador regional por competência | revisão + métrica + dimensões agregadas |
| `Watchlist` | usuário acompanha empresa, somente no ciclo oficial | usuário + empresa únicos |

Valores anterior e novo de `ChangeEvent` poderão usar JSONB com formato definido por tipo de evento. O contrato do evento, e não JSON livre, determinará quais chaves são válidas.

### Constraints e índices obrigatórios

- uma revisão ativa por janela e competência, por `UniqueConstraint` condicional quando aplicável;
- um snapshot de cada entidade por revisão;
- uma participação por empresa, chave societária e revisão;
- códigos CNPJ, IBGE e TOM com comprimento e caracteres válidos;
- recorte geográfico modelado por associação versionada, sem atributo global `is_in_scope` em município;
- capital social não negativo quando conhecido;
- `is_in_region` coerente com o município e o recorte durante a validação de pacote;
- unicidade lógica de evento para impedir duplicação em recálculo;
- índices derivados das consultas P0: CNPJ, razão social normalizada, nome fantasia normalizado, revisão ativa, município, CNAE, situação e intervalo dos eventos.

Índices de busca textual específicos serão escolhidos depois do `EXPLAIN` com dados reais; não serão adicionados todos antecipadamente.

## 6. Contratos de arquivo e diretórios

### Layout operacional proposto

```text
var/data/
  sources/<competence>/                    temporário, fonte nacional
  work/<window-id>/                        temporário, contém dados sensíveis transitórios
  packages/<window-id>/window-manifest.json
  packages/<window-id>/<competence>/package-manifest.json
  packages/<window-id>/<competence>/companies.parquet
  packages/<window-id>/<competence>/establishments.parquet
  packages/<window-id>/<competence>/partners.parquet
  reports/<window-id>/                     QA auxiliar, sem CPF mascarado
```

`var/data`, segredos, bancos DuckDB temporários e relatórios com dados reais ficarão ignorados pelo Git. Apenas schemas, exemplos sintéticos mínimos e referências públicas versionáveis poderão entrar no repositório.

### Versão e compatibilidade

- `contract_version` usa versão semântica interna, iniciando em `1.0.0` após o gate da competência real;
- mudança incompatível de coluna ou semântica incrementa major e exige regeneração;
- inclusão compatível e opcional incrementa minor;
- correção de descrição sem mudar dados incrementa patch;
- pacote declara contrato, janela, coorte, recorte, competência, fontes, contagens e SHA-256;
- importador rejeita contrato, coorte, janela ou sequência incompatível.

## 7. Fluxo de preparação da janela

O comando será uma casca sobre `PrepareHistoricalWindowService`. Argumentos mínimos propostos:

- arquivo de configuração da janela;
- diretório de fontes ou autorização explícita para download;
- diretório de saída;
- limite de memória, threads, temp e mínimo de disco;
- `--resume` para retomar fases idempotentes;
- `--validate-only` para verificar fontes e pacotes sem publicar nada.

### Fase P0 — preflight

1. Validar janela contínua, 35 municípios e referência TOM–IBGE.
2. Confirmar segredo HMAC sem imprimi-lo.
3. Verificar espaço livre, permissão dos diretórios e ausência de workspace versionado.
4. Resolver inventário esperado das fontes por competência.
5. Registrar URL, tamanho e hash de cada artefato obtido.

Falha no preflight não deve criar pacote parcial apresentado como válido.

### Fase P1 — descoberta da coorte

1. Ler os arquivos de estabelecimentos de cada competência com schema explícito.
2. Converter TOM para IBGE pela referência versionada.
3. Selecionar CNPJs completos com ao menos uma ocorrência nos 35 municípios.
4. Produzir a união determinística e ordenada da coorte.
5. Calcular `cohort_hash` sobre versão, recorte e identidades ordenadas.
6. Registrar TOM desconhecido, duplicidade e divergência como erro ou alerta conforme a regra aprovada.

Nenhum CNPJ será adicionado manualmente à coorte.

### Fase P2 — geração dos pacotes por competência

Para cada competência, em execução sequencial:

1. Ler empresas, estabelecimentos, Simples e sócios necessários.
2. Filtrar estabelecimentos pela coorte e empresas/sócios pelos CNPJs básicos derivados.
3. Normalizar códigos, datas, decimais, nomes comparáveis e endereços.
4. Gerar HMAC de PF dentro da empresa e descartar CPF mascarado imediatamente depois.
5. Calcular presença regional da fotografia.
6. Projetar somente as colunas dos contratos aprovados.
7. Calcular hash determinístico por registro.
8. Escrever Parquet tipado e comprimido em caminho temporário.
9. Validar schema, unicidade, contagens, códigos, ausência de CPF e hashes.
10. Renomear/mover atomicamente para o diretório final do pacote e escrever seu manifesto.

Um pacote só assume estado validado quando seus três Parquets e manifesto passam juntos.

### Fase P3 — manifesto da janela e retenção

1. Confirmar as 13 competências e a sequência completa.
2. Confirmar que todos os pacotes usam o mesmo contrato, coorte, recorte e fonte geográfica.
3. Gerar `window-manifest.json` por escrita temporária e substituição atômica.
4. Emitir relatório sem dado pessoal com contagens, hashes, alertas, duração, pico de disco e memória configurada.
5. Autorizar limpeza manual das fontes somente depois da validação integral.

### Retomada e idempotência

Cada fase terá marcador verificável por conteúdo, nunca apenas por existência de arquivo. `--resume` recalcula e compara hashes antes de reaproveitar uma saída. Arquivo temporário incompleto será removível sem afetar pacote validado.

## 8. Fluxo de importação da competência

O comando `import_window_package` chama o serviço `import_window_package`. O fluxo implementado separa validação, staging lógico, comparação e publicação.

### I0 — validação externa à transação de publicação

1. Ler manifesto da janela e do pacote.
2. Validar JSON, Parquet, hashes, contrato, coorte, recorte e competência.
3. Confirmar que a competência pertence à janela e que não atravessa lacuna.
4. Detectar no-op pelo hash ativo ou exigir revisão explícita para hash diferente.
5. Criar `ImportBatch` e `CompetenceRevision` em estado de staging.

### I1 — carga em staging lógico

Os registros serão carregados nas tabelas de snapshot ligados a uma `CompetenceRevision` ainda em estado `STAGING`. Consultas funcionais sempre exigirão revisões ativas; portanto, não será necessário manter uma segunda cópia física das mesmas tabelas apenas para staging. O `batch_id` preservará a tentativa operacional. O loader será uma interface com duas implementações candidatas:

- `orm_bulk`: `bulk_create` em lotes, menor acoplamento e melhor simplicidade;
- `postgres_copy`: Psycopg 3 `COPY FROM`, maior throughput esperado.

O spike da primeira competência escolherá com os mesmos critérios:

- tempo total de carga;
- pico de RAM do processo;
- tamanho de lote e pressão sobre PostgreSQL;
- clareza de rollback e retomada;
- cobertura de teste;
- ausência de conexão ou transação “idle in transaction”.

O mecanismo vencedor ficará encapsulado; comandos e regras não dependerão dele. `COPY` não será usado por uma conexão externa que finja participar de `transaction.atomic` do Django.

### I2 — validação de qualidade e projeções candidatas

1. Validar unicidade, FKs, campos obrigatórios e correspondência entre tabelas.
2. Registrar cada regra com `eligible_rows`, `affected_rows` e amostra limitada.
3. Bloquear erro estrutural desde a primeira ocorrência.
4. Para alerta localizado, calcular `max(10, ceil(eligible_rows × 0,001))`.
5. Acima do limite, marcar `FAILED_QUALITY_GATE`; até o limite, preparar publicação com alertas e excluir/suspender somente entidades afetadas.

Depois da qualidade, eventos e métricas candidatos serão calculados contra as revisões adjacentes e gravados com referência explícita às revisões envolvidas. Enquanto qualquer revisão do par estiver em `STAGING` ou `SUPERSEDED`, essas projeções não serão visíveis nas consultas funcionais.

### I3 — publicação atômica

Dentro de uma única fronteira `transaction.atomic`:

1. bloquear a linha da janela/competência para impedir concorrência;
2. confirmar novamente revisão ativa e sequência;
3. conferir contagens finais dos snapshots, eventos e métricas candidatos;
4. marcar a revisão anterior como `SUPERSEDED`, quando houver;
5. marcar a nova revisão `PUBLISHED` ou `PUBLISHED_WITH_WARNINGS`;
6. concluir o lote.

A troca de visibilidade ocorre pelo estado das revisões, não por copiar novamente milhões de snapshots dentro da transação. Eventos de um intervalo somente serão consultáveis quando suas duas revisões estiverem ativas.

Exceções serão capturadas fora do bloco atômico. O código não continuará consultando uma transação quebrada, nem atualizará objetos em memória como se o rollback não tivesse ocorrido. Efeitos externos pós-publicação usarão `on_commit` apenas quando necessários.

### I4 — pós-publicação e recuperação

- no-op registra tentativa sem duplicar dados;
- falha de staging preserva revisão ativa;
- falha na publicação faz rollback de snapshots, eventos, métricas e troca de revisão;
- correção recalcula a métrica do mês e os intervalos anterior e posterior;
- snapshots e projeções de staging abandonado ficam rastreáveis e poderão ser limpos por comando administrativo seguro.

## 9. Motor de comparação e métricas

### Interface dos comparadores

Os comparadores serão funções ou classes puras que recebem snapshots anterior e atual e devolvem candidatos a evento e ocorrências de qualidade. Não acessarão request, template ou filesystem.

```text
snapshot anterior + snapshot atual + contexto do intervalo
                         │
                         ▼
              candidatos por dimensão
                         │
                         ▼
                precedência explícita
                         │
                         ▼
              ChangeEvent determinístico
```

### Ordem de implementação P0

1. `REGISTRATION_STATUS_CHANGED` e `ESTABLISHMENT_CLOSED`;
2. `ADDRESS_CHANGED`, `ENTERED_REGION` e `LEFT_REGION`;
3. `MAIN_CNAE_CHANGED`;
4. `ESTABLISHMENT_OPENED` e `LATE_FIRST_SEEN`;
5. `SHARE_CAPITAL_CHANGED`;
6. `PARTNER_ADDED` e `PARTNER_REMOVED`;
7. precedência cruzada, idempotência e recálculo.

Essa ordem resolve primeiro identidades e dimensões reutilizadas nas regras seguintes.

### P1 implementado sobre os contratos preparados

Os snapshots e contratos carregam natureza jurídica, porte, Simples, MEI e qualificação. Os cinco comparadores P1 foram ativados sem redownload:

- `LEGAL_NATURE_CHANGED`;
- `COMPANY_SIZE_CHANGED`;
- `SIMPLES_STATUS_CHANGED`;
- `MEI_STATUS_CHANGED`;
- `PARTNER_QUALIFICATION_CHANGED`.

Os 15 tipos de evento estão presentes na janela oficial. Os códigos permanecem como contrato interno estável; o portal os apresenta com nomes de negócio e valores formatados.

### Métricas

Métricas serão recalculadas por revisão publicada, nunca incrementadas sem referência ao snapshot. Primeira entrega:

- empresas distintas presentes por competência;
- estabelecimentos regionais por competência;
- aberturas e baixas;
- eventos por tipo;
- distribuição por município, CNAE, situação e porte.

Somente fotografias com `is_in_region = true` entram em métricas regionais. Empresas serão contadas por CNPJ básico distinto.

Na implementação atual, seis famílias mensais são persistidas: totais de empresas e estabelecimentos, estabelecimentos por município, CNAE e situação, e empresas por porte. Aberturas, baixas, eventos por tipo, variações de CNAE, rankings de aumento de capital e ampliação societária são projeções derivadas e recalculáveis. Taxas relativas, coortes de sobrevivência, concentração setorial e análise de redes ficam como extensões pós-MVP.

## 10. Camada de consulta e interface

### Serviços de leitura

Views não montarão manualmente a semântica de revisão ativa. Query services centralizarão:

- competência ativa mais recente;
- pesquisa por CNPJ básico/completo, razão social e nome fantasia;
- detalhe de empresa com estabelecimentos incluídos e sociedade;
- timeline entre revisões ativas consecutivas;
- dashboard e filtros básicos;
- lotes, revisões e alertas.

`select_related`, `prefetch_related` e índices serão escolhidos com contagem de queries e `EXPLAIN`. Nenhum cache externo entra no MVP.

### Telas P0

1. página inicial com janela e última competência;
2. pesquisa e resultados;
3. detalhe de empresa;
4. timeline com antes/depois e intervalo;
5. dashboard regional básico;
6. acompanhamento administrativo de importações e qualidade.

Autenticação e watchlist podem ser antecipadas se não ameaçarem P0, mas o gate interno não depende delas.

## 11. Estratégia de testes

### Pirâmide mínima

| Nível | Ferramenta | Cobertura obrigatória |
|---|---|---|
| Unidade pura | `SimpleTestCase`/`unittest` | normalização, hashes, HMAC, contratos, qualidade e comparadores |
| Modelo/ORM | `TestCase` | constraints, queries, snapshots, eventos e métricas |
| Transação real | `TransactionTestCase` | commit, rollback, staging, revisão e publicação atômica |
| Comando | `call_command` + diretório temporário | argumentos, saída, erros, idempotência e retomada |
| Funcional | Django test client | pesquisa, detalhe, timeline, dashboard e administração |
| Aceitação | roteiro manual e evidências | 34 cenários do documento de validação |

### Fixtures

- fixtures sintéticas pequenas versionadas para todos os casos-limite;
- pacote Parquet sintético mínimo conforme contrato;
- amostra real regional fora do Git, identificada apenas por hash e procedimento de obtenção;
- nenhuma fixture com CPF completo ou mascarado;
- factories simples próprias antes de considerar dependência adicional.

### Testes negativos obrigatórios

- CPF mascarado ausente em Parquet, manifesto, banco, log e relatório;
- baseline sem eventos;
- ausência sem baixa/saída;
- lacuna bloqueia competência posterior;
- mesmo hash não duplica;
- revisão inválida preserva ativa;
- evento mais específico elimina duplicado;
- limite de alerta é calculado por regra;
- pacote incompatível falha antes da publicação.

### Qualidade do código

Antes de integrar uma tarefa:

- testes relacionados verdes;
- migration revisada quando houver;
- sem segredo ou artefato real versionado;
- comando possui ajuda e saída via `self.stdout`/`self.stderr`;
- erro operacional chega como falha clara do comando;
- documentação e evidência da task estão ligadas no Miro.

## 12. Estratégia de entrega e gates

### Caminho crítico

```text
G0 plano aprovado
  └─→ G1 fundação reproduzível
        └─→ G2 duas competências reais na amostra técnica
              └─→ G3 coorte e 13 pacotes oficiais validados
                    └─→ G4 13 competências publicadas + dez eventos P0
                          └─→ G5 pesquisa/timeline/dashboard/admin integrados
                                └─→ G6 regressão e MVP interno
```

UX, documentação e casos de teste caminham em paralelo, mas não removem dependências do caminho crítico.

### Gates objetivos

| Gate | Evidência de saída | Bloqueia |
|---|---|---|
| G0 — plano | checklist técnico aprovado por Tiago | qualquer implementação |
| G1 — fundação | Compose sobe; healthcheck, migration vazia e teste smoke passam | domínio e pipeline |
| G2 — fatia técnica | `2026-07` e `2026-08`, com os 35 municípios, atravessam preparação/importação e produzem comparação válida | escala para janela oficial |
| G3 — dados oficiais | coorte dos 35 e 13 pacotes usam o mesmo manifesto, contrato e hashes | carga oficial |
| G4 — núcleo histórico | 13 competências ativas, 12 intervalos e dez P0 recalculáveis | integração de produto |
| G5 — produto integrado | pesquisa, detalhe, timeline, dashboard e administração usam somente revisões ativas | regressão final |
| G6 — MVP interno | critérios P0 e cenários críticos aprovados, sem erro fatal conhecido | declaração de MVP |

**Estado em 25/08/2026:** G0–G5 concluídos tecnicamente. A janela oficial possui 13 revisões sanitizadas `r2`, 12 comparações, 278.301 eventos, 15.751 métricas e portal integrado. G6 possui candidata técnica interna aprovada após 68 testes e auditorias finais; homologações de Gabriel, Emili e professor continuam pendentes. Consulte [`evidencias/g3-g5-janela-oficial.md`](evidencias/g3-g5-janela-oficial.md), [`evidencias/g6-regressao-interna.md`](evidencias/g6-regressao-interna.md) e a [`matriz de aceitação`](matriz-aceitacao-mvp.md).

A fatia G2 foi ampliada para os 35 municípios e permanece uma validação técnica de duas competências; resultados históricos do produto exigem a janela oficial de 13 competências.

## 13. Cronograma proposto

O calendário assume aprovação do plano até 25 de agosto. Aprovação posterior exige replanejamento explícito; não autoriza cortar municípios, competências, integridade ou privacidade silenciosamente.

| Período | Objetivo principal | Gate esperado | Tiago | Gabriel | Emili |
|---|---|---|---|---|---|
| 24–25/08 | validar plano e preparar backlog | G0 | fechar decisões técnicas | revisar testabilidade | organizar Miro e ata |
| 25–28/08 | fundação, contratos e preflight | G1 | bootstrap, Compose, módulos, DuckDB | smoke tests e revisão de ambiente | wireframes baixos e rastreabilidade |
| 29/08–04/09 | fatia vertical real de duas competências | G2 | preparação, modelos, staging e publicação | testes de comandos e primeiras views | fluxo de importação e evidências |
| 05–11/09 | coorte oficial, 13 pacotes e núcleo histórico | G3 e início G4 | pipeline completo, qualidade e eventos base | integração/testes e correções | documentação dos dados e revisão UX |
| 12–18/09 | dez P0, pesquisa, detalhe e timeline | G4 | comparadores e query services | templates, filtros e timeline | protótipo refinado e teste de clareza |
| 19–25/09 | dashboard, administração e integração | G5 | métricas, performance e revisões | dashboard, admin funcional e regressão | acessibilidade essencial e evidências |
| 26–30/09 | congelamento, privacidade e aceitação | G6 | correções críticas e demonstração | regressão/aceite e relatório QA | documentação, roteiro e organização |

Downloads e processamento das competências poderão ocupar tempo de máquina em paralelo ao trabalho humano, sempre com execução manual, observável e uma preparação por vez.

## 14. Backlog técnico inicial

Tamanhos: **S** até uma sessão curta; **M** aproximadamente um dia focado; **L** dois ou mais dias e deve ser quebrado durante a sprint. Tamanho não é promessa de horas.

### EPIC E0 — governança e autorização

| ID | Tarefa | Responsável | Dependência | Aceite | Tam. |
|---|---|---|---|---|---|
| PI-000 | Validar este plano e registrar autorização | Tiago | — | gate assinado e estado atualizado | S |
| PI-001 | Converter fases em épicos e cards no Miro | Emili | PI-000 | IDs, donos, dependências e critérios ligados | M |
| PI-002 | Registrar riscos e decisões técnicas pendentes | Emili/Tiago | PI-000 | log de risco inicial publicado | S |
| PI-003 | Confirmar espaço livre e recursos do Mac | Tiago | PI-000 | relatório de disco/RAM sem dados sensíveis | S |

### EPIC E1 — fundação reproduzível

| ID | Tarefa | Responsável | Dependência | Aceite | Tam. |
|---|---|---|---|---|---|
| PI-010 | Inicializar projeto, lockfile e configuração por ambiente | Tiago | PI-000 | versões fixadas; segredos ausentes do Git | M |
| PI-011 | Criar Compose de app e PostgreSQL com healthcheck | Tiago | PI-010 | ambiente limpo sobe com um comando documentado | M |
| PI-012 | Criar apps internos e configuração mínima | Tiago | PI-010 | `check`, migration e teste smoke passam | M |
| PI-013 | Definir diretórios operacionais e `.gitignore` | Tiago/Gabriel | PI-010 | fontes, workspaces, secrets e dados reais ignorados | S |
| PI-014 | Criar base de testes e convenções | Gabriel | PI-012 | suíte vazia/smoke reproduzível no container | M |
| PI-015 | Documentar setup e troubleshooting inicial | Emili/Gabriel | PI-011 | outro integrante executa sem instrução oral | M |

### EPIC E2 — contratos, geografia e fixtures

| ID | Tarefa | Responsável | Dependência | Aceite | Tam. |
|---|---|---|---|---|---|
| PI-020 | Especificar schema `1.0.0` dos três Parquets | Tiago | PI-012 | nomes, tipos, nulabilidade e semântica testáveis | L |
| PI-021 | Especificar manifests de janela e pacote | Tiago | PI-020 | exemplos válido/inválido e SHA-256 definidos | M |
| PI-022 | Versionar referência dos 35 municípios TOM–IBGE | Tiago | PI-012 | 35 únicos e verificados; códigos textuais | M |
| PI-023 | Criar validador e carga do catálogo geográfico | Tiago/Gabriel | PI-022 | duplicidade, formato e UF inválidos falham | M |
| PI-024 | Criar fixtures sintéticas e pacote mínimo | Gabriel | PI-020, PI-021 | cobre empresa, filial, PF, PJ e estrangeiro sem CPF | L |
| PI-025 | Criar matriz contrato → requisito → teste | Gabriel/Emili | PI-020 | todos os campos têm finalidade e caso de teste | M |

### EPIC E3 — preparação da janela

| ID | Tarefa | Responsável | Dependência | Aceite | Tam. |
|---|---|---|---|---|---|
| PI-030 | Implementar inventário e hashes das fontes | Tiago | PI-021 | origem, tamanho, hash e competência rastreáveis | L |
| PI-031 | Implementar preflight de disco, segredo e diretórios | Tiago | PI-030 | falha antes de download/processamento inseguro | M |
| PI-032 | Implementar schema explícito e normalizadores | Tiago | PI-020 | códigos preservam zeros; datas/decimal determinísticos | L |
| PI-033 | Implementar descoberta da coorte e `cohort_hash` | Tiago | PI-022, PI-032 | união determinística em todas as competências | L |
| PI-034 | Implementar identidade societária e descarte do CPF | Tiago | PI-032 | teste prova ausência após transformação | L |
| PI-035 | Gerar Parquets e manifestos temporários/atômicos | Tiago | PI-033, PI-034 | pacote completo ou nenhum pacote válido | L |
| PI-036 | Implementar validação, relatório e `--resume` | Tiago/Gabriel | PI-035 | retomada compara conteúdo e não existência | L |
| PI-037 | Executar amostra real de duas competências/quatro cidades | Tiago/Gabriel | PI-036 | métricas de tempo/RAM/disco e pacote validado | L |
| PI-038 | Revisar privacidade dos artefatos gerados | Gabriel | PI-037 | nenhum CPF mascarado em saídas ou logs | M |

### EPIC E4 — persistência e importação

| ID | Tarefa | Responsável | Dependência | Aceite | Tam. |
|---|---|---|---|---|---|
| PI-040 | Implementar catálogo, janela, competência e revisão | Tiago | PI-012, PI-021 | migrations e constraints aprovadas | L |
| PI-041 | Implementar entidades e snapshots por revisão | Tiago | PI-040 | unicidade e consultas de revisão ativa testadas | L |
| PI-042 | Implementar batch, staging e qualidade | Tiago | PI-040 | falha nunca aparece em consulta funcional | L |
| PI-043 | Implementar validador do pacote no importador | Tiago/Gabriel | PI-021, PI-042 | incompatibilidades falham antes da carga | L |
| PI-044 | Medir `bulk_create` versus Psycopg `COPY` | Tiago | PI-037, PI-042 | benchmark documentado e loader escolhido | L |
| PI-045 | Implementar loader vencedor | Tiago | PI-044 | carga integral da amostra com RAM limitada | L |
| PI-046 | Implementar quality gate e issues | Tiago/Gabriel | PI-043, PI-045 | fatal, warning e limite têm testes | L |
| PI-047 | Implementar publicação atômica e bloqueio | Tiago | PI-046 | rollback real validado por `TransactionTestCase` | L |
| PI-048 | Implementar no-op, lacuna e revisão | Tiago | PI-047 | cenários C1–C6 passam | L |
| PI-049 | Criar tela/consulta administrativa básica | Gabriel | PI-042 | lote, revisão, progresso e erro visíveis | M |

### EPIC E5 — eventos e métricas P0

| ID | Tarefa | Responsável | Dependência | Aceite | Tam. |
|---|---|---|---|---|---|
| PI-050 | Criar contrato e unicidade de `ChangeEvent` | Tiago | PI-041 | evento liga revisões e entidade sem duplicação | M |
| PI-051 | Implementar situação e fechamento | Tiago | PI-050 | precedência e ausência cobertas | M |
| PI-052 | Implementar endereço e região | Tiago | PI-051 | entrada/saída vencem endereço correspondente | L |
| PI-053 | Implementar CNAE e abertura/late-first-seen | Tiago | PI-052 | baseline e data de início cobertos | L |
| PI-054 | Implementar capital e sociedade | Tiago | PI-050 | capital, add/remove e identidade por tipo cobertos | L |
| PI-055 | Implementar recálculo e idempotência dos dez P0 | Tiago/Gabriel | PI-051–054 | mesmo par gera mesmo conjunto | L |
| PI-056 | Implementar métricas regionais básicas | Tiago | PI-055 | empresa/estabelecimento e região não se misturam | L |

### EPIC E6 — consultas e telas P0

| ID | Tarefa | Responsável | Dependência | Aceite | Tam. |
|---|---|---|---|---|---|
| PI-060 | Implementar query services de revisão ativa | Tiago | PI-041, PI-048 | nenhuma tela usa revisão superseded | M |
| PI-061 | Implementar pesquisa e filtros básicos | Gabriel | PI-060 | CNPJ, razão social e fantasia funcionam | L |
| PI-062 | Implementar detalhe e quadro societário | Gabriel | PI-060 | empresa, estabelecimentos e sócios coerentes | L |
| PI-063 | Implementar timeline com antes/depois | Gabriel/Tiago | PI-055, PI-060 | intervalo e data de detecção não se confundem | L |
| PI-064 | Implementar dashboard e filtros | Gabriel/Tiago | PI-056, PI-060 | competência, município e CNAE cobertos | L |
| PI-065 | Refinar tela administrativa | Gabriel | PI-049, PI-060 | warnings e falhas compreensíveis | M |
| PI-066 | Revisar UX, responsividade essencial e termos | Emili/Gabriel | PI-061–065 | linguagem usa `CONTEXT.md` e fluxo é demonstrável | L |

### EPIC E7 — janela oficial e estabilização

| ID | Tarefa | Responsável | Dependência | Aceite | Tam. |
|---|---|---|---|---|---|
| PI-070 | Gerar coorte oficial dos 35 municípios | Tiago | G2 | `cohort_hash` e contagens auditados | L |
| PI-071 | Gerar e validar os 13 pacotes | Tiago | PI-070 | G3 completo, sem lacuna | L |
| PI-072 | Importar as 13 competências | Tiago/Gabriel | PI-048, PI-071 | 13 ativas, 12 intervalos e quality report | L |
| PI-073 | Medir e ajustar índices/lotes | Tiago | PI-072 | consultas comuns ≤ 2 s; uso documentado | L |
| PI-074 | Executar regressão e cenários de aceite | Gabriel | PI-063–065, PI-072 | relatório com evidências e defeitos | L |
| PI-075 | Fazer varredura final de privacidade e segredos | Gabriel/Tiago | PI-072 | nenhuma ocorrência proibida | M |
| PI-076 | Preparar manual, roteiro e demonstração | Emili/equipe | PI-074 | outro integrante reproduz fluxo principal | L |
| PI-077 | Congelar release candidata do MVP interno | Tiago | PI-073–076 | G6 aprovado ou versão marcada parcial | M |

### EPIC E8 — outubro e novembro

| ID | Tarefa | Responsável | Dependência | Aceite | Tam. |
|---|---|---|---|---|---|
| PI-080 | Implementar cinco comparadores P1 | Tiago | G6 | recálculo sem novo download | L |
| PI-081 | Implementar autenticação e controle administrativo | Gabriel/Tiago | G6 | CSRF e permissões testados | L |
| PI-082 | Implementar watchlist | Gabriel | PI-081 | usuário + empresa únicos | M |
| PI-083 | Ampliar acessibilidade, responsividade e identidade visual | Emili/Gabriel | G6 | checklist visual e acessível aprovado | L |
| PI-084 | Regressão final e documentação acadêmica | equipe | PI-080–083 | entrega oficial pronta | L |

## 15. Riscos técnicos e respostas

| Risco | Prob. | Impacto | Sinal de disparo | Resposta planejada |
|---|---|---|---|---|
| Espaço insuficiente para fontes e spill | Alta | Crítico | preflight abaixo do mínimo ou pico próximo ao disco livre | bloquear execução, limpar somente artefato autorizado e voltar ao plano de retenção; nunca reduzir janela silenciosamente |
| Preparação das 13 competências demora mais que a sprint | Alta | Alto | amostra extrapola além da janela disponível | iniciar fontes cedo, medir por fase, permitir retomada e paralelizar trabalho humano, não o ETL |
| Schema ou publicação da Receita varia entre meses | Média | Alto | coluna, encoding ou arquivo divergente | schema por versão, SourceArtifact, falha clara e adapter explícito por versão |
| `bulk_create` é lento ou consome memória | Média | Alto | benchmark de G2 excede meta | trocar somente o loader encapsulado por Psycopg `COPY` e repetir testes de transação |
| Quality gate bloqueia alertas legítimos | Baixa | Médio | limite versionado excedido em regra localizada consistente | revisar evidência das 13 competências; o limite geral ficou em 0,1% e `LATE_FIRST_SEEN` foi calibrado em 0,50% no ADR 0018 |
| Evento duplicado ou falso | Média | Alto | contagem anormal ou cenário de precedência falha | comparadores puros, unicidade no banco e testes de antes/depois/ausência |
| CPF mascarado vaza em artefato | Baixa | Crítico | scanner ou revisão encontra padrão proibido | interromper, apagar cópias autorizadas com segurança, corrigir pipeline, regenerar e registrar incidente |
| Tiago vira gargalo do caminho crítico | Alta | Alto | cards L acumulados ou revisão parada | pareamento com Gabriel, documentação de serviços e fatias demonstráveis semanais |
| Escopo visual compete com backend | Média | Alto | P0 técnico incompleto após 18/09 | congelar P1, manter Emili/Gabriel em fluxo mínimo e proteger caminho crítico |
| Fonte pública fica indisponível | Baixa/Média | Alto | download repetidamente falha | preservar hashes e fontes já obtidas, retomar sem corromper e registrar dependência externa |

## 16. Observabilidade e operação

Cada execução deverá registrar:

- `batch_id`, janela, competência e revisão;
- fase atual e timestamps de início/fim;
- fonte, arquivo e hash sem segredos;
- linhas lidas, selecionadas, válidas, rejeitadas e publicadas;
- `eligible_rows`, `affected_rows` e limite por regra;
- duração por fase;
- memória configurada, threads e diretório temporário;
- espaço livre inicial e final;
- resultado, erro normalizado e instrução de retomada.

Saída de management command usará `self.stdout` e `self.stderr`, respeitando verbosidade e sendo capturável em testes. Progresso detalhado ficará no `ImportBatch`; logs não conterão linha cadastral integral, CPF mascarado ou segredo HMAC.

## 17. Definition of Done

### Tarefa técnica

- critério de aceite do card atendido;
- testes aplicáveis escritos e verdes;
- migration, contrato ou ADR revisado quando houver;
- sem segredo ou dado real versionado;
- documentação e evidência ligadas no Miro;
- revisão por outra pessoa quando tocar pipeline, privacidade ou publicação.

### Epic

- todas as tarefas bloqueantes concluídas;
- fluxo demonstrável no Docker Compose;
- cenários de falha e retomada executados;
- débitos e riscos remanescentes registrados;
- nenhum P0 substituído por mock sem indicação explícita.

### MVP interno

- gates G0–G6 aprovados;
- 13 competências e 12 intervalos oficiais;
- dez eventos P0 recalculáveis;
- pesquisa, detalhe, timeline, dashboard e administração integrados;
- consultas comuns até dois segundos no ambiente medido;
- regressão, privacidade e aceitação documentadas;
- zero erro fatal conhecido;
- alertas dentro da política aprovada.

## 18. Decisões técnicas submetidas à validação

Ao aprovar este plano, Tiago aprova as seguintes direções, ainda sem autorizar alterações de escopo:

- [x] cinco Django apps internos: `geography`, `registry`, `pipeline`, `changes` e `portal`;
- [x] DuckDB embarcado para preparação, inicialmente limitado a 6 GiB e dois threads;
- [x] preflight conservador de 200 GiB antes da preparação nacional completa, ajustável somente por medição;
- [x] `DateField` no primeiro dia do mês como representação física da competência;
- [x] snapshots ligados à revisão, preservando revisões substituídas;
- [x] recorte geográfico versionado por `GeographicScope` e associação com municípios;
- [x] staging por `batch_id` e publicação curta em `transaction.atomic`;
- [x] evento com exatamente um alvo relacional e chaves determinísticas para eventos e métricas;
- [x] spike `bulk_create` versus Psycopg `COPY`, com loader encapsulado;
- [x] amostra técnica de duas competências e quatro cidades antes da janela oficial;
- [x] ordem de implementação dos dez eventos P0 definida na seção 9;
- [x] runner nativo do Django como base dos testes;
- [x] cronograma, gates, responsáveis e backlog das seções 12–14;
- [x] pinagem das versões exatas somente na fundação, usando releases compatíveis e reproduzíveis.

### Itens que não são autorizados pela validação do plano

- reduzir os 35 municípios ou as 13 competências;
- transportar CPF mascarado além do workspace;
- adicionar fila, cron, cloud, SPA ou API pública;
- publicar dados ou aplicação externamente;
- reutilizar código, credencial ou dump profissional;
- modificar evento, coorte, retenção ou quality gate sem retornar ao ledger.

## 19. Gate de início do desenvolvimento

O desenvolvimento somente começa depois que:

1. Tiago revisar este documento;
2. eventuais alterações forem incorporadas;
3. o estado mudar de “aguardando validação” para “aprovado para implementação”;
4. a autorização abaixo for marcada e datada.

- [x] **Aprovado por Tiago para iniciar implementação local.** Data: 24/08/2026.

O gate foi encerrado em 24 de agosto de 2026. O desenvolvimento local está autorizado; publicação externa continua dependendo de autorização específica.

## 20. Referências técnicas atuais

Documentação consultada para evitar decisões baseadas em APIs antigas:

- [Django 5.2 — custom management commands](https://github.com/django/django/blob/5.2.6/docs/howto/custom-management-commands.txt): descoberta de comandos, saída testável e `CommandError`;
- [Django 5.2 — transactions](https://github.com/django/django/blob/5.2.6/docs/topics/db/transactions.txt): `transaction.atomic`, rollback e limites transacionais;
- [Django 5.2 — constraints](https://github.com/django/django/blob/5.2.6/docs/ref/models/constraints.txt): `UniqueConstraint` e `CheckConstraint`;
- [DuckDB — larger-than-memory workloads](https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads.html): spill para disco e `temp_directory`;
- [DuckDB — configuration](https://duckdb.org/docs/current/configuration/pragmas.html): limites de memória e diretório temporário;
- [DuckDB — Parquet](https://duckdb.org/docs/current/data/parquet/overview.html): schemas, leitura e escrita Parquet;
- [Psycopg 3 — COPY](https://www.psycopg.org/psycopg3/docs/basic/copy.html): carga eficiente sujeita a commit ou rollback;
- [Psycopg 3 — transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html): contextos, savepoints e risco de conexão ociosa em transação.
