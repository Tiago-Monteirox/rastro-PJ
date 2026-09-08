# G7 — Mapa analítico regional

**Data da execução:** 7 de setembro de 2026
**Ambiente:** macOS, Django 5.2.17, PostgreSQL 17 em Docker Compose
**Escopo:** 35 municípios, 13 competências de `2025-08` a `2026-08`

## Objetivo

Demonstrar que o Rastro PJ consegue transformar endereços cadastrais publicados pela Receita em uma projeção cartográfica derivada, gratuita, auditável e consultável sem alterar as fotografias normalizadas de origem.

## Fontes registradas

| Fonte | Versão | Municípios | SHA-256 do manifesto |
|---|---|---:|---|
| CNEFE | 2022 | 35 | `184d0ba825f825712e803bb206df3fe6d5625e2f0c707ce34f364eddf56beb59` |
| Malha municipal IBGE | 2022, qualidade mínima | 35 | `5b9e1c0ea583975a5f5883770b532466b7f3432c2a7e5593d448831c4d6405e4` |
| População residente, tabela SIDRA 4709, variável 93 | Censo 2022 | 35 | `a97ec2409fd4c761647d092cf01d057bf25610122cc4b983288c38cb71beefcc` |
| Catálogo de subclasses CNAE | API v2 do IBGE | 1.332 códigos | sincronização idempotente no PostgreSQL |

Os 35 CSVs CNEFE possuem 961.993 linhas e 151 MiB extraídos. A malha possui 35 GeoJSON e 140 KiB. Arquivos permanecem em `var/data/cartography/`, fora do Git.

## Execução

```bash
make sync-cnae
make sync-population
make prepare-map
```

Projeção publicada:

- ID: `a5c4eee0-4b21-4184-8b2d-63f6f3dff687`;
- algoritmo: `1.0.1`;
- duração integral: 10 min 01,86 s;
- RSS máximo medido na indexação CNEFE: 450.838.528 bytes, aproximadamente 430 MiB;
- reexecução idempotente: 0,40 s, sem nova escrita.

Uma execução anterior interrompida permaneceu como `FAILED`; em nenhum momento substituiu a projeção publicada.

## Resultado do quality gate

| Medida | Resultado |
|---|---:|
| ocorrências elegíveis | 3.483.375 |
| correspondência no endereço | 2.278.263 |
| aproximação por CEP | 1.038.305 |
| não localizadas | 166.807 |
| total localizado | 3.316.568 |
| cobertura global | 95,21% |
| competências completas | 13/13 |
| limites municipais | 35/35 |
| falhas municipais | 0 |
| erros estruturais | 0 |

Menores coberturas acumuladas:

| Município | Ocorrências | Cobertura |
|---|---:|---:|
| Frutal | 106.099 | 71,48% |
| Araporã | 12.787 | 81,93% |
| Ituiutaba | 144.818 | 91,42% |
| Araguari | 207.326 | 94,22% |
| Uberaba | 650.031 | 94,22% |

Frutal permanece acima do limite bloqueante aprovado de 70%. A projeção passou pelo limite global de 90%, pelas verificações de coordenadas e níveis CNEFE e pela correspondência entre janela, revisão, empresa e estabelecimento.

Na competência mais recente, `2026-08`:

- 270.411 estabelecimentos ativos;
- 261.687 empresas distintas;
- 35 municípios com presença;
- 257.371 localizados;
- cobertura de 95,18%.

## Desempenho aquecido

Vinte execuções locais por cenário, com PostgreSQL e cache aquecidos:

| Consulta | Mediana | p95 | Limite |
|---|---:|---:|---:|
| resumo, seis indicadores, rankings e polígonos | 0,532 s | 0,536 s | 1,0 s |
| agregação regional | 0,100 s | 0,103 s | 1,5 s |
| Uberlândia no zoom intermediário, com 4.185 CEPs e ponto real representativo | 0,215 s | 0,251 s | 1,5 s |
| página do maior grupo de precisão, com 1.697 estabelecimentos e 25 por página | 0,014 s | 0,020 s | 1,5 s |

O endpoint detalhado nunca retorna mais de cinco mil localizações. Quando o conjunto excede o limite, responde com agregação por CEP; se essa camada também exceder, responde por município e informa o motivo.

## Experimento de dinâmica territorial

O modo experimental compara a competência de referência somente à publicada imediatamente antes dela. Na comparação `2026-07 → 2026-08`, sem filtros adicionais:

| Medida | Resultado |
|---|---:|
| estoque ativo anterior | 266.808 |
| estoque ativo atual | 270.411 |
| variação do estoque | +3.603 (+1,35%) |
| aberturas confirmadas | 3.379 |
| baixas confirmadas | 2.089 |
| saldo de ciclo de vida | +1.290 |
| outros efeitos cadastrais | +2.313 |

A decomposição fecha: `3.603 = (3.379 − 2.089) + 2.313`. O resíduo não recebe causa automática; pode reunir movimentação regional, alterações de situação ou categoria, aparições tardias e efeitos dos filtros.

Cinco execuções aquecidas do resumo regional variaram de 0,836 s a 0,847 s. Uberlândia variou de 0,460 s a 0,477 s e o CNAE `4711-3/02`, de 0,016 s a 0,021 s. Todos permaneceram abaixo do limite de 1 segundo.

O contrato automatizado cobre crescimento, retração, eventos confirmados, baseline, modo inválido, combinação incompatível e supressão de pontos individuais. A tabela municipal apresenta os mesmos valores do mapa.

## Experimento de densidade cadastral populacional

A referência demográfica é obtida manualmente na API SIDRA, validada contra os 35 códigos IBGE do recorte e persistida antes da consulta. O frontend não chama o IBGE. A carga só é considerada disponível quando um mesmo ano cobre integralmente o recorte.

Resultado da sincronização do Censo 2022:

| Medida | Resultado |
|---|---:|
| municípios com população | 35/35 |
| população residente do recorte | 1.679.956 |
| Uberlândia | 713.224 |
| Uberaba | 337.836 |
| Araguari | 117.808 |

No modo de concentração, o usuário pode alternar a métrica municipal entre volume absoluto e estabelecimentos ativos por mil habitantes. O resumo, o ranking, os polígonos, o popup municipal e a tabela carregam a população e o valor relativo. A interface informa separadamente a competência cadastral e o ano do Censo.

A métrica é `estabelecimentos elegíveis ÷ população residente × 1.000`. Ela mede presença cadastral relativa; não representa demanda, faturamento, emprego, produtividade, consumidores nem potencial de mercado. Para impedir comparações ambíguas, a opção por mil habitantes é incompatível com o modo de dinâmica territorial.

Dez execuções aquecidas do resumo regional normalizado variaram de 0,809 s a 0,826 s, abaixo do limite de 1 segundo. O contrato automatizado rejeita fonte incompleta, ano inconsistente, métrica desconhecida e combinação temporal incompatível; o modo absoluto permanece disponível quando a referência ainda não foi sincronizada.

## Segurança, privacidade e degradação

- página e três endpoints cartográficos exigem autenticação;
- acesso anônimo foi redirecionado para login;
- as respostas não incluem CPF, quadro societário ou campos pessoais;
- detalhes contêm somente atributos empresariais necessários e são paginados em 25 itens;
- token `sk.` é rejeitado antes da renderização e nunca chega ao HTML;
- ausência do token `pk.` mantém filtros, indicadores, rankings e tabela municipal;
- Mapbox não recebe endereços, não geocodifica e não é consumido pelos testes;
- Mapbox GL JS v3 só é instanciado quando há token público, pois exige credencial válida e contabiliza um map load por instância, inclusive com estilo local;
- a mesma precisão pública é aplicada a MEI e não MEI, conforme risco aceito para uso local.

## Smoke test no navegador

A página autenticada foi aberta no Chrome em `http://localhost:8000/mapa/` com token público Mapbox configurado localmente antes do incremento demográfico. A interface apresentou os oito filtros cadastrais, indicadores, legenda de concentração, legenda de precisão, polígonos e pontos sem expor a credencial no Git. O novo seletor de métrica, os indicadores demográficos, o ranking relativo e a tabela ampliada possuem validação automatizada de backend e HTML; a homologação visual humana específica deste incremento permanece pendente.

O recorte `Uberlândia + abertura na competência`, em `2026-08`, foi aplicado pela interface e produziu:

- 705 estabelecimentos ativos e 704 empresas distintas;
- um município com presença;
- 696 matrizes e nove filiais;
- cobertura geográfica de 96,03%;
- URL e controles preservando os filtros após recarga;
- CNAEs apresentados com código formatado e descrição oficial;
- popup do ponto com a empresa `68.452.618 KARINA DIAS JORGE SANTOS` e link para `/empresas/68452618/`;
- tabela detalhada coerente com o popup, incluindo CNAE e precisão espacial.

O teste revelou que as coordenadas retornadas pelo evento de clique do Mapbox sofrem quantização. O GeoJSON passou a preservar a coordenada original do PostgreSQL em propriedades próprias, usadas na consulta detalhada; o cenário real foi reexecutado com um estabelecimento retornado.

Também foi preservado e automatizado o estado degradado: sem token, filtros, indicadores, rankings e a tabela continuam operacionais.

## Verificação automatizada

```bash
docker compose run --rm web python manage.py test
uv run ruff check .
uv run ruff format --check .
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
node --check apps/portal/static/portal/establishment-map.js
docker compose config --quiet
```

Resultado final: 121 testes aprovados em PostgreSQL em 3,787 s, sem falha de lint, formatação, Django, migração, JavaScript ou Compose.

## Conclusão

A POC cartográfica satisfaz internamente os critérios funcionais, de dados, segurança, desempenho, idempotência e operação degradada. A revisão de UI/UX da equipe, a configuração de um token público Mapbox restrito e a homologação acadêmica continuam como validações humanas externas à implementação.
