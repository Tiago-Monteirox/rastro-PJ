# Manual operacional local

**Escopo:** ambiente local do MVP monolítico  
**Janela oficial ativa:** `2025-08..2026-08`  
**Pacote oficial sanitizado:** `var/data/packages/official-2025-08-2026-08-sanitized/window-manifest.json`

Este manual descreve somente operações suportadas pelo repositório. Não contém senhas e não autoriza publicação externa, exclusão de fontes ou criação silenciosa de uma revisão.

## 1. Endereços e portas

| Recurso | Endereço local | Observação |
|---|---|---|
| Dashboard | <http://localhost:8000/> | página inicial |
| Pesquisa | <http://localhost:8000/empresas/> | CNPJ, razão social, nome fantasia e filtros regionais |
| Eventos | <http://localhost:8000/eventos/> | filtros por tipo, entidade, competência e CNPJ |
| Monitoradas | <http://localhost:8000/monitoradas/> | exige login |
| Importações | <http://localhost:8000/importacoes/> | exige login |
| Healthcheck | <http://localhost:8000/health/> | verifica aplicação e banco |
| Admin Django | <http://localhost:8000/admin/> | exige usuário administrativo |
| PostgreSQL no Mac | `localhost:5433` | encaminhado para `db:5432` no Compose |

Para DBeaver, leia banco, usuário e senha do arquivo `.env` local. Não presuma que os exemplos de `.env.example` são as credenciais efetivamente usadas pelo volume atual.

## 2. Subir e conferir o ambiente

```bash
docker compose up -d db web
docker compose ps
curl --fail --silent http://localhost:8000/health/
```

O healthcheck esperado é `{"status": "ok", "database": "ok"}`. Se o serviço web não responder:

```bash
docker compose logs --tail 200 web
docker compose logs --tail 200 db
```

Para acompanhar logs continuamente, use `make logs`; interromper a visualização não encerra os containers.

## 3. Criar acesso local

```bash
docker compose run --rm web python manage.py createsuperuser
```

Informe a senha interativamente. Não a coloque em Markdown, commit, screenshot ou evidência acadêmica.

## 4. Validação antes de importar

Confira primeiro o espaço disponível:

```bash
df -h
docker system df
```

Valide a geografia canônica sem escrever:

```bash
docker compose run --rm web python manage.py load_geographic_scope \
  data/reference/triangulo_mineiro_35_municipios.csv --dry-run
```

Valide os 13 pacotes, manifestos, contratos e hashes da janela oficial:

```bash
docker compose run --rm web python manage.py validate_window_package \
  var/data/packages/official-2025-08-2026-08-sanitized/window-manifest.json
```

O código IBGE textual de sete dígitos é a identidade canônica do município. O TOM textual de quatro dígitos é preservado como identificador da fonte Receita; ambos mantêm zeros iniciais.

### Preparar novamente a janela oficial

Esta operação é pesada e não é necessária para navegar no banco já importado. Ela exige as 13 fontes completas, o mesmo segredo HMAC estável no `.env` e espaço aprovado no preflight. `--resume` só reaproveita coorte e pacote quando entradas e hashes ainda conferem.

```bash
caffeinate -i docker compose run --rm web python manage.py prepare_rf_window \
  --competence 2025-08 --competence 2025-09 --competence 2025-10 \
  --competence 2025-11 --competence 2025-12 --competence 2026-01 \
  --competence 2026-02 --competence 2026-03 --competence 2026-04 \
  --competence 2026-05 --competence 2026-06 --competence 2026-07 \
  --competence 2026-08 \
  --sources-root var/data/sources \
  --output var/data/packages/official-2025-08-2026-08-sanitized \
  --work-root var/data/work/official-2025-08-2026-08 \
  --scope-code triangulo-mineiro-35 --scope-version 1 \
  --window-code rf-triangulo-2025-08-2026-08 --resume
```

Nunca troque `RF_PARTNER_HMAC_SECRET` durante a retomada da mesma janela: isso mudaria a identidade societária PF e poderia fabricar eventos.

## 5. Importação oficial e idempotência

Importação normal:

```bash
docker compose run --rm web python manage.py import_window_package \
  var/data/packages/official-2025-08-2026-08-sanitized/window-manifest.json
```

Se os hashes já estiverem publicados, o comando deve terminar como no-op auditável. Ele não pode duplicar snapshots, eventos ou métricas. Use `--allow-revision` somente quando um pacote corrigido tiver hash diferente e sua publicação como nova revisão tiver sido deliberadamente aprovada:

```bash
docker compose run --rm web python manage.py import_window_package \
  CAMINHO_DO_MANIFESTO_CORRIGIDO --allow-revision
```

Não execute duas importações simultâneas. Para manter uma tarefa longa ativa enquanto o Mac estiver ligado e conectado à energia:

```bash
caffeinate -i docker compose run --rm web python manage.py import_window_package \
  CAMINHO_DO_MANIFESTO
```

## 6. Recálculo de derivados

Eventos e métricas são derivados das fotografias completas. Eles podem ser recalculados sem redownload:

```bash
docker compose run --rm web python manage.py recalculate_events
docker compose run --rm web python manage.py recalculate_metrics
docker compose run --rm web python manage.py recalculate_quality_metadata
```

Execute um comando por vez. A primeira competência é baseline e não gera eventos; somente pares consecutivos participam do recálculo.

## 7. Verificações de release

```bash
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web python manage.py test
uv run ruff check .
uv run ruff format --check .
docker compose config --quiet
```

Resultado interno de referência em 25/08/2026: 67 testes aprovados em 3,193 s, 104 arquivos conformes ao formatador e nenhum erro de lint, Django, migração ou Compose.

## 8. Sanidade do banco oficial

Consulte a janela ativa pelo ORM para não misturar revisões publicadas de janelas históricas já substituídas:

```bash
docker compose exec web python manage.py shell -c "from apps.pipeline.models import \
CompetenceRevision, HistoricalWindow; w=HistoricalWindow.objects.get(status='ACTIVE'); \
print(list(CompetenceRevision.objects.filter(window_competence__historical_window=w, \
status__in=CompetenceRevision.ACTIVE_STATUSES).values('revision_number', 'status') \
.order_by('window_competence__competence')))"
```

O portal deve consultar somente a janela `ACTIVE` e revisões `PUBLISHED` ou `PUBLISHED_WITH_WARNINGS`. Para inspecionar a trilha operacional, use a tela autenticada de importações ou o admin, preservando batch, revisão, artefatos e ocorrências de qualidade.

As contagens de referência da janela ativa `r2` são:

| Entidade derivada ou fotografia | Contagem |
|---|---:|
| fotografias de empresa | 8.509.822 |
| fotografias de estabelecimento | 8.804.270 |
| fotografias societárias | 4.018.362 |
| eventos | 278.301 |
| métricas | 15.751 |

Diferença nessas contagens após uma reimportação idêntica é falha de idempotência e deve bloquear a entrega.

## 9. Privacidade e retenção

Antes de considerar uma revisão publicável, verifique:

- nenhum CPF completo ou mascarado em Parquet, manifesto, PostgreSQL, logs ou relatório;
- nenhuma chave ou coluna de CPF nos contratos funcionais;
- chave PF produzida por HMAC restrita à empresa e segredo ausente dos artefatos;
- sócio PJ nacional normalizado para raiz CNPJ de oito caracteres alfanuméricos;
- campos humanos sanitizados contra sequências incidentais semelhantes a documentos;
- revisão substituta validada antes de qualquer expurgo.

O expurgo de conteúdo pessoal proibido é uma exceção obrigatória à retenção. Metadados, hashes, batches e ocorrências permanecem; snapshots e pacotes substituídos inseguros são removidos somente depois da publicação e auditoria da revisão sanitizada. Não existe limpeza automática no MVP.

Fontes nacionais ainda são workspace temporário. A remoção deve ocorrer apenas depois de confirmar pacote ativo, hashes, auditoria e possibilidade de redownload. Este manual não fornece comando recursivo de exclusão porque o alvo precisa ser resolvido e revisado em cada operação.

## 10. Parar o ambiente

```bash
docker compose down
```

Esse comando preserva o volume `postgres_data`. Não use `docker compose down -v` no ambiente oficial: a opção `-v` remove o banco local.

## 11. Recuperação de falha

1. Não apague a janela ativa nem o volume.
2. Consulte `docker compose logs --tail 200 web` e a tela de importações.
3. Confirme o `ImportBatch`, a fase, o código e a mensagem de erro.
4. Valide novamente o manifesto antes de repetir o comando.
5. Se o hash mudou, investigue a origem e só então decida por uma revisão explícita.
6. Confirme que a revisão ativa anterior continua publicada.

Falhas de manifesto, contrato, hash ou quality gate devem deixar a última revisão válida intacta e registrar um batch `FAILED`; nunca se corrige um pacote editando linhas diretamente no PostgreSQL.
