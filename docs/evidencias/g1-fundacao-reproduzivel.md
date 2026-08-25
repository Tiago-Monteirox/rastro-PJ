# Evidência G1 — fundação reproduzível

**Estado:** concluído  
**Data:** 24 de agosto de 2026  
**Ambiente:** Mac local com Docker Compose  
**Publicação externa:** não realizada

## Resultado

O monólito Django foi inicializado com cinco apps internos e PostgreSQL como único banco funcional. O lockfile fixa as dependências Python e as imagens base foram fixadas por versão ou digest.

Versões verificadas:

- Python 3.13.13 na imagem e no ambiente local;
- Django 5.2.17;
- PostgreSQL 17 Alpine;
- Psycopg 3.2.13;
- DuckDB 1.5.5;
- uv 0.11.19.

## Evidências executadas

| Verificação | Resultado |
|---|---|
| `docker compose config --quiet` | aprovado |
| `python manage.py check` | zero problemas |
| `python manage.py makemigrations --check --dry-run` | nenhuma alteração pendente |
| migrations em PostgreSQL limpo | todas aplicadas |
| suíte Django em PostgreSQL | 15 testes aprovados |
| `ruff check` | aprovado |
| `ruff format --check` | aprovado |
| `GET /health/` | HTTP 200, aplicação e banco `ok` |
| `GET /` | HTTP 200, página inicial renderizada |

Os testes cobrem, entre outros pontos:

- preservação de zero inicial no código TOM;
- formatos IBGE e CNPJ no banco;
- associação única entre município e recorte;
- uma única janela ativa;
- hashes obrigatórios em janela validada/publicada;
- uma única revisão publicada por competência;
- contagens coerentes nas ocorrências de qualidade;
- snapshot único por entidade e revisão;
- capital social não negativo;
- ausência de campo CPF na participação PF;
- exatamente um alvo relacional por evento;
- revisões distintas no evento;
- healthcheck e página inicial.

## Defeito encontrado durante o gate

A primeira versão do check de hashes permitia `NULL` por causa da lógica ternária do SQL. Um teste falhou no PostgreSQL, a constraint passou a exigir `IS NOT NULL` explicitamente e a suíte foi executada novamente com 15 aprovações. O teste permanece como regressão.

## Capacidade e bloqueio preventivo

Foram observados aproximadamente 183 GiB livres no disco. Isso atende ao desenvolvimento do monólito, mas fica abaixo do preflight conservador de 200 GiB aprovado para a preparação nacional das 13 competências. Nenhum download ou processamento nacional completo foi iniciado.

## Próximo gate

G2 começou pelos contratos `1.0.0`, referência validada dos 35 municípios, fixtures sintéticas e uma fatia vertical real de duas competências. A execução posterior ampliou a amostra para todos os 35 municípios e aprovou o gate; consulte [`g2-fatia-real-julho-agosto.md`](g2-fatia-real-julho-agosto.md).
