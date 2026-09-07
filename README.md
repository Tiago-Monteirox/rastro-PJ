# Rastro PJ

Monólito local em Django 5.2 e PostgreSQL para reconstruir fotografias mensais do CNPJ, detectar mudanças cadastrais e produzir indicadores dos 35 municípios aprovados do Triângulo Mineiro.

## Estado atual

A janela oficial `2025-08..2026-08` está preparada e publicada localmente:

- 13 competências consecutivas e 12 intervalos de comparação;
- coorte determinada pela ocorrência de qualquer matriz ou filial nos 35 municípios;
- 13 revisões ativas `r2`, produzidas pelos pacotes sanitizados;
- 8.509.822 fotografias de empresa;
- 8.804.270 fotografias de estabelecimento;
- 4.018.362 fotografias de participação societária;
- 278.301 eventos derivados e recalculáveis;
- 15.751 métricas regionais persistidas.
- projeção cartográfica publicada com 3.483.375 ocorrências ativas;
- 3.316.568 ocorrências localizadas pelo CNEFE, cobertura global de 95,21%;
- limites oficiais dos 35 municípios e navegação cartográfica nas 13 competências.

As contagens de fotografias e observações cartográficas são somas das 13 competências, não quantidades de empresas únicas. O portal, a pesquisa, o detalhe, a timeline, os eventos, o dashboard, o mapa analítico, a watchlist e o acompanhamento de importações estão integrados ao mesmo monólito. O dashboard aceita competência inicial e final, município e CNAE; também apresenta os maiores aumentos de capital social e as maiores ampliações líquidas do quadro societário no recorte.

A suíte atual possui 105 testes e foi aprovada em PostgreSQL. `ruff check`, `ruff format --check`, `manage.py check`, `makemigrations --check --dry-run` e a validação do Compose também passaram. As revisões de pesquisa e QA, documentação, UI/UX e do professor permanecem pendentes e não são substituídas por essas verificações internas.

## Indicadores e eventos

As 15 regras de mudança estão ativas. No portal, seus códigos técnicos permanecem no backend para estabilidade e auditoria, mas são traduzidos para nomes de negócio e comparações legíveis de antes e depois.

Seis famílias de métricas mensais são materializadas no PostgreSQL: totais de empresas e estabelecimentos regionais, estabelecimentos por município, CNAE e situação cadastral, e empresas por porte. Aberturas, baixas, eventos por tipo, variação de CNAE, aumento de capital e ampliação societária são projeções derivadas dos snapshots e eventos publicados; por isso podem ser recalculadas sem duplicar a fonte de verdade.

Indicadores avançados como taxas relativas, coortes de sobrevivência, concentração setorial e análise de redes entre empresas continuam fora do compromisso do MVP. Eles podem ser incorporados depois de definir interpretação de negócio e custo de consulta.

## Requisitos

- Docker Desktop com Docker Compose;
- espaço local suficiente para o volume PostgreSQL e os pacotes regionais;
- preflight de 200 GiB livres antes da preparação das fontes nacionais completas;
- `uv` para executar as verificações Python no Mac.
- token público `pk.` do Mapbox para a camada visual; indicadores, rankings e tabela funcionam sem ele.

Antes de baixar ou preparar fontes, confira o disco com `df -h`. O volume oficial já importado é muito maior que o ambiente sintético usado nos testes.

## Primeira execução

```bash
cp .env.example .env
docker compose build
docker compose run --rm web python manage.py migrate
docker compose up -d web
```

Acesse:

- aplicação e dashboard: <http://localhost:8000/>;
- pesquisa de empresas: <http://localhost:8000/empresas/>;
- eventos: <http://localhost:8000/eventos/>;
- empresas monitoradas: <http://localhost:8000/monitoradas/>;
- mapa analítico regional: <http://localhost:8000/mapa/>;
- importações: <http://localhost:8000/importacoes/>;
- healthcheck: <http://localhost:8000/health/>;
- administração Django: <http://localhost:8000/admin/>.

Mapa, importações e monitoradas exigem autenticação. Crie um usuário local, sem registrar a senha na documentação:

```bash
docker compose run --rm web python manage.py createsuperuser
```

Para habilitar o mapa-base, configure em `.env` um token público dedicado, com privilégios mínimos e URL permitida `http://localhost:8000`:

```dotenv
MAPBOX_PUBLIC_TOKEN=pk.seu-token-publico-restrito
```

Nunca use um token `sk.`. A aplicação rejeita tokens que não comecem por `pk.` e mantém a tabela alternativa quando a credencial está ausente ou inválida.

O PostgreSQL é publicado no Mac em `localhost:5433` por padrão; dentro do Compose, a aplicação usa `db:5432`. Nome do banco, usuário e senha devem ser lidos do arquivo `.env` local. Os valores de `.env.example` são apenas padrões de desenvolvimento e não comprovam os valores do ambiente em execução.

## Verificação

```bash
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web python manage.py test
uv run ruff check .
uv run ruff format --check .
docker compose config --quiet
```

Os testes usam PostgreSQL, não SQLite, para exercitar índices parciais, regexes, transações e constraints do modelo real.

## Estrutura

```text
config/             configuração e URLs raiz
apps/geography/     municípios e recortes versionados
apps/cartography/   fontes, resolução de endereços, projeções e consultas do mapa
apps/pipeline/      preparação, janelas, revisões, lotes, qualidade e importação
apps/registry/      empresas, estabelecimentos, sócios e snapshots
apps/changes/       eventos derivados e métricas regionais
apps/portal/        views, templates, healthcheck e watchlist
docs/               decisões, arquitetura, modelagem, operação e evidências
var/data/           fontes e pacotes locais; nunca versionados
```

## Comandos cotidianos

```bash
make up          # sobe aplicação e banco
make down        # encerra os containers
make logs        # acompanha o servidor Django
make migrate     # aplica migrations
make test        # executa a suíte no PostgreSQL
make lint        # confere estilo e formatação
make prepare-map # prepara ou confirma a projeção cartográfica
```

## Pipeline histórico

```bash
# geografia canônica: IBGE identifica; TOM preserva o identificador da Receita
docker compose run --rm web python manage.py load_geographic_scope \
  data/reference/triangulo_mineiro_35_municipios.csv

# inventário e download retomável de uma competência oficial
docker compose run --rm web python manage.py inventory_rf_sources 2026-08
docker compose run --rm web python manage.py download_rf_sources \
  2026-08 var/data/sources --workers 4

# janela sintética pequena para desenvolvimento e QA
docker compose run --rm web python manage.py generate_synthetic_window \
  var/data/packages/synthetic-g2
docker compose run --rm web python manage.py validate_window_package \
  var/data/packages/synthetic-g2/window-manifest.json
docker compose run --rm web python manage.py import_window_package \
  var/data/packages/synthetic-g2/window-manifest.json
```

O comando `prepare_rf_window` descobre a coorte regional e gera um pacote Parquet imutável por competência. A preparação e a importação são automatizadas, mas iniciadas manualmente. Consulte [o contrato 1.0.0](docs/contratos/pacotes-1.0.0.md) e o [manual operacional](docs/manual-operacional.md).

O pacote oficial ativo encontra-se em `var/data/packages/official-2025-08-2026-08-sanitized/window-manifest.json`. Uma reimportação idêntica é um no-op auditável: cria o registro operacional correspondente, sem duplicar fotografias, eventos ou métricas. Uma mudança de hash exige `--allow-revision` e publicação atômica de uma nova revisão.

## Projeção cartográfica

Os 35 CSVs municipais do CNEFE 2022 devem ficar em `var/data/cartography/cnefe-2022/`, nomeados pelo código IBGE, como `3170206.csv`. As malhas municipais são obtidas da API gratuita do IBGE e persistidas fora do Git.

```bash
make prepare-map
```

O comando inventaria e valida as fontes, resolve endereços distintos, aplica a cascata `endereço CNEFE → CEP → não localizado`, materializa as 13 competências, executa o quality gate e publica tudo atomicamente. A reexecução com os mesmos hashes é um no-op. Mapbox não recebe endereços e não é usado para geocodificação; apenas renderiza no navegador os dados consultados no Django.

## Privacidade

CPF completo ou mascarado é proibido no PostgreSQL, nos pacotes, manifestos, relatórios e logs. Sócios PF recebem uma chave HMAC restrita à empresa durante a preparação; o documento mascarado é descartado antes do pacote. Sócios PJ nacionais usam a raiz CNPJ de oito caracteres alfanuméricos, inclusive quando a fonte fornece o CNPJ completo de 14 caracteres.

Os pacotes `r2` também sanitizam sequências incidentais semelhantes a documentos em campos humanos. Depois da validação das substitutas, os snapshots e pacotes substituídos com conteúdo proibido foram expurgados; metadados, hashes, lotes e ocorrências de auditoria foram preservados conforme os ADRs 0016 e 0025.

## Limites

- execução somente local, sem publicação externa;
- sem cron, Celery, RabbitMQ, Temporal, PostGIS, SPA ou API pública;
- consultas mensais não prometem tempo real nem a data diária exata da mudança;
- fontes nacionais permanecem temporárias e exigem limpeza manual segura após as validações previstas;
- aprovação interna técnica não equivale à homologação acadêmica ou jurídica.

Leia também o [escopo aprovado](PROJETO.md), o [plano técnico](docs/backend-cnpj-regional-plano-implementacao.md), o [plano de CNPJ alfanumérico e fontes públicas](docs/plano-cnpj-alfanumerico-e-fontes-publicas.md), a [matriz de aceite](docs/matriz-aceitacao-mvp.md), as [evidências da janela oficial](docs/evidencias/g3-g5-janela-oficial.md) e a [regressão interna G6](docs/evidencias/g6-regressao-interna.md).
