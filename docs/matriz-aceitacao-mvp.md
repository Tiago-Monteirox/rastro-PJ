# Matriz de aceitação do MVP

**Versão da matriz:** 07/09/2026
**Total:** 47 cenários
**Janela de referência:** `2025-08..2026-08`  
**Ambiente:** Mac local, Docker Compose, Django 5.2 e PostgreSQL

Esta matriz materializa os 34 cenários cadastrais originais e os 13 cenários da projeção cartográfica. Ela separa teste automatizado, verificação interna no volume oficial e homologação externa. “Aprovado” nesta tabela significa evidência técnica interna; não significa aceite de pesquisa e QA, documentação, UI/UX ou do professor.

## Legenda

- **Aprovado — automatizado:** existe teste direto e a suíte de 116 testes passou.
- **Aprovado — oficial:** verificado internamente sobre a janela real ativa.
- **Parcial:** parte crítica está coberta, mas falta uma variação ou evidência formal.
- **Pendente:** ainda precisa de execução ou aceite específico.

## A. Fluxo principal e domínio

| ID | Cenário e resultado esperado | Estado | Evidência interna |
|---|---|---|---|
| A1 | Matriz externa e filial regional: empresa e filial entram na coorte; a matriz externa não entra apenas pelo CNPJ básico | Parcial | `test_company_snapshot_allows_future_cohort_members_but_not_orphan_establishments` protege a identidade da coorte; falta caso de aceite isolado com matriz externa |
| A2 | Estabelecimento externo entra em Uberaba: preserva histórico, gera `ENTERED_REGION` e só conta métricas quando regional | Aprovado — automatizado | janela sintética e `test_two_competences_publish_ten_events_and_reimport_is_no_op` exercitam o evento; métricas e filtro regional passam nos testes do portal |
| A3 | Mudança de Uberlândia para Goiânia: `LEFT_REGION`, sem endereço duplicado ou baixa | Aprovado — automatizado | conjunto dos dez P0 e regra de precedência validados na janela sintética |
| A4 | Mudança de endereço dentro do mesmo município regional: somente `ADDRESS_CHANGED` | Aprovado — automatizado | comparador sintético e detalhe/timeline exercitados pela suíte |
| A5 | Primeira aparição posterior ao baseline com início no intervalo: `ESTABLISHMENT_OPENED` | Aprovado — automatizado | `test_opening_date_uses_left_open_right_closed_competence_interval` |
| A6 | Primeira aparição com início antigo: `LATE_FIRST_SEEN`, sem abertura | Aprovado — automatizado | `test_late_first_seen_is_generated_instead_of_false_opening` |
| A7 | Situação muda explicitamente para baixada: `ESTABLISHMENT_CLOSED`, sem evento genérico duplicado | Aprovado — automatizado | janela sintética publica o conjunto P0 esperado e testa precedência |
| A8 | Capital social muda: evento registra antes, depois e intervalo | Aprovado — oficial | comparador automatizado; 278.301 eventos oficiais incluem evidências temporais de capital |
| A9 | Sócio aparece ou desaparece: `PARTNER_ADDED` ou `PARTNER_REMOVED` | Aprovado — automatizado | janela sintética publica ambos e mantém chaves determinísticas |
| A10 | Só muda qualificação: não fabrica inclusão/remoção e gera `PARTNER_QUALIFICATION_CHANGED` | Aprovado — automatizado | `test_five_delivery_events_use_fields_already_present_in_snapshots` |
| A11 | Pesquisa por CNPJ, razão social ou nome fantasia retorna coorte, competência e origem | Aprovado — oficial | testes funcionais do portal; busca observada em 6 ms sem termo e 12 ms com termo |
| A12 | Dashboard por intervalo, município e CNAE separa empresas/estabelecimentos, usa presença regional e ordena crescimento de capital/sociedade | Aprovado — oficial | `test_dashboard_filters_published_snapshot_by_competence_municipality_and_cnae` e `test_dashboard_ranks_growth_in_a_temporal_and_municipal_cut`; resultado validado na janela oficial |

## B. Limites temporais e qualidade

| ID | Cenário e resultado esperado | Estado | Evidência interna |
|---|---|---|---|
| B1 | `2025-08` publica baseline e métricas, sem evento anterior | Aprovado — automatizado | `test_event_recalculation_uses_baseline_and_only_adjacent_competences` e janela oficial com 13 revisões |
| B2 | `2026-08` sem competência posterior não produz inferência depois da borda | Aprovado — automatizado | recálculo compara somente pares adjacentes e termina na última revisão publicada |
| B3 | Nova janela validada com `2026-09` permite `2026-08 → 2026-09` | Parcial | motor e manifesto não fixam 13 no núcleo; falta executar uma nova janela real contendo `2026-09` |
| B4 | Entidade some por um mês: qualidade, sem fechamento ou saída falsa | Parcial | `test_missing_establishment_is_quality_issue_not_business_event`; falta caso equivalente isolado para empresa |
| B5 | Competência falha e a posterior está pronta: não publica através da lacuna | Parcial | sequência consecutiva é validada pelo manifesto e recálculo só usa adjacentes; falta teste negativo dedicado de publicação após lacuna |
| B6 | Hash, schema, competência ou identidade inválida falha sem alterar versão ativa | Aprovado — automatizado | testes de hash adulterado, contrato incompatível, coluna ausente, identidade duplicada e rollback |
| B7 | Alerta localizado dentro do limite publica com transparência e isola afetados | Aprovado — automatizado | testes dos limites calibrados de `SOURCE_ZERO_DATE` e `LATE_FIRST_SEEN` |
| B8 | Mesma regra acima do limite reprova o quality gate | Aprovado — automatizado | `test_warning_volume_above_approved_limit_blocks_publication` e teste de revisão reprovada |
| B9 | Sócio estrangeiro sem documento ambíguo suspende somente a comparação societária | Parcial | `AMBIGUOUS_PARTNER` participa do quality gate e rollback; falta cenário unitário abaixo do limite com isolamento individual |

## C. Idempotência, correção e recuperação

| ID | Cenário e resultado esperado | Estado | Evidência interna |
|---|---|---|---|
| C1 | Mesmo pacote e hash: no-op, sem duplicar snapshots, eventos ou métricas | Aprovado — oficial | teste de integração e batch `842ce935-854b-4d8c-81c0-be67a0a0bf3d`, `COMPLETED/no_op` em 2,61 s, com 13 competências e 278.301 eventos preservados |
| C2 | Mesmo mês com hash diferente exige revisão explícita e preserva ativa durante staging | Aprovado — automatizado | `test_changed_package_requires_and_publishes_explicit_atomic_revision` |
| C3 | Revisão válida substitui atomicamente a anterior e recalcula intervalos adjacentes | Aprovado — oficial | as 13 revisões sanitizadas `r2` estão ativas; revisões antigas foram marcadas `SUPERSEDED` antes do expurgo de conteúdo proibido |
| C4 | Revisão inválida preserva versão ativa e não deixa publicação parcial | Aprovado — automatizado | `test_failed_revision_quality_gate_preserves_active_revision_and_events` |
| C5 | Competências anteriores formam nova janela e nova coorte, sem anexar à antiga | Pendente | contrato suporta outra sequência; falta ensaio ponta a ponta de expansão histórica |
| C6 | Pacote de outra coorte ou contrato é rejeitado | Aprovado — automatizado | contrato/hash incompatível e reaproveitamento condicionado ao estado/coorte possuem testes |

## D. Privacidade, segurança e operação

| ID | Cenário e resultado esperado | Estado | Evidência interna |
|---|---|---|---|
| D1 | Parquet, manifesto, PostgreSQL, logs e QA não contêm CPF completo ou mascarado | Aprovado — oficial | 14 manifestos, 39 Parquets, 21.332.454 linhas e 429 combinações arquivo/coluna auditados sem violação; auditoria global do PostgreSQL terminou com `blocking_total=0` |
| D2 | Pesquisa por nome de sócio PF é inexistente/bloqueada; sócio aparece na empresa | Parcial | portal não oferece rota de busca por PF e o detalhe omite chave/documento; falta teste negativo nomeado para tentativa de busca de PF |
| D3 | Mesma PF em empresas distintas não recebe chave global correlacionável | Aprovado — automatizado | `test_pf_partner_identity_is_secret_and_scoped_to_company` e constraint do registro societário |
| D4 | Docker Compose inicia aplicação e PostgreSQL com instruções reproduzíveis | Aprovado — oficial | healthcheck, Django e Compose aprovados; portal acessível em `localhost:8000` e banco em `localhost:5433` |
| D5 | Consultas comuns respondem em até dois segundos no volume integral | Parcial | caminhos originais permanecem abaixo de 2 s e o recorte regional anual marcou 1,055 s; o novo recorte municipal anual marcou 8,658 s e requer otimização |
| D6 | Depois de validar os pacotes, fontes podem ser removidas preservando URL, tamanho, mês e hash | Parcial | pacotes ativos e manifestos estão preservados; fontes nacionais continuam em retenção temporária e a limpeza final é manual |
| D7 | Falha de importação deixa estado, progresso, duração e erro auditáveis sem corromper ativa | Aprovado — automatizado | testes de manifesto adulterado e revisão reprovada confirmam batch `FAILED` e rollback |

## E. Mapa analítico regional

| ID | Cenário e resultado esperado | Estado | Evidência interna |
|---|---|---|---|
| E1 | Página e três endpoints cartográficos exigem autenticação; concentração usa uma competência e dinâmica declara a comparação consecutiva | Aprovado — automatizado | `test_page_and_every_api_require_authentication`, `test_bootstrap_uses_one_competence_and_all_eight_filters` e testes do modo dinâmico |
| E2 | Modo, município, CNAE principal, matriz/filial, porte, perfil tributário, precisão e período de abertura respeitam suas combinações válidas sem filtro silenciosamente ignorado | Aprovado — automatizado | os oito filtros da concentração são exercitados em conjunto; modo, município, porte, período e formatos desconhecidos são validados pelo contrato |
| E3 | Resumo entrega seis indicadores, rankings e limites dos 35 municípios sem confundir empresa com estabelecimento | Aprovado — oficial | projeção integral e smoke autenticado sobre `2026-08`; 270.411 estabelecimentos, 261.687 empresas e 35 municípios |
| E4 | Correspondência de endereço é determinística, insensível a acentos e restrita a município, CEP, logradouro e número normalizados | Aprovado — automatizado | testes de normalização, chave de busca e melhor nível CNEFE em `test_matching.py` |
| E5 | Múltiplos candidatos até 100 m escolhem um ponto CNEFE real; dispersão superior a 100 m recua para CEP | Aprovado — automatizado | testes de ambiguidade e de representante real em `test_matching.py` |
| E6 | Cascata endereço → CEP → não localizado preserva método e nível; nenhum registro sem evidência recebe coordenada fabricada | Aprovado — automatizado | constraints, testes de matching/modelo e quality gate integral |
| E7 | Endpoint detalhado retorna no máximo 5.000 grupos e amplia a agregação por CEP ou município sem truncar o universo | Aprovado — automatizado | `test_excess_detail_is_aggregated_without_silent_truncation`; o ponto do CEP permanece uma coordenada CNEFE real, e o benchmark de Uberlândia retornou 4.185 CEPs |
| E8 | Clique em um grupo preserva a coordenada original, método e nível; mostra nome com link para a empresa; detalhes são paginados em 25 e não expõem dados pessoais | Aprovado — oficial | testes de identidade da coordenada, grupo de precisão, paginação e ausência de CPF/quadro societário; smoke test real do popup e do link empresarial |
| E9 | Sem projeção, sem biblioteca ou sem token público, a aplicação mantém estado explicativo, indicadores e tabela; token secreto nunca chega ao HTML | Aprovado — automatizado | testes de projeção ausente, token `sk.` rejeitado e fallback textual da página |
| E10 | Preparação manual é idempotente, reiniciável e só troca a projeção em publicação atômica após o quality gate | Aprovado — oficial | execução integral em 10 min 01,86 s, interrupção preservada como `FAILED` e reexecução no-op em 0,40 s |
| E11 | Preparação usa menos de 2 GiB/30 min e consultas aquecidas respeitam p95 de 1,0 s no resumo e 1,5 s nos demais endpoints | Aprovado — oficial | RSS de aproximadamente 430 MiB; p95 de 0,536 s, 0,103 s, 0,251 s e 0,020 s |
| E12 | Fontes CNEFE e malhas possuem inventário, SHA-256, validação estrutural e cobertura mínima de 90% global/70% por município | Aprovado — oficial | 13/13 competências, 35/35 limites, 95,21% global, nenhuma falha municipal ou estrutural; consulte G7 |
| E13 | Modo experimental compara competências consecutivas, separa variação do estoque de eventos confirmados, rejeita baseline/filtro incompatível e mantém o mapa padrão intacto | Aprovado — oficial | testes de crescimento, retração, baseline, contrato e pontos; `2026-07 → 2026-08` conferido no volume real e resumo aquecido abaixo de 1 s |

## Resultado por tipo de evidência

- suíte atual: **116/116 testes aprovados** em PostgreSQL, em 4,733 s; a regressão cadastral G6 permanece registrada separadamente com seus 68 testes históricos;
- qualidade estática e configuração: Ruff, Django, migrações e Compose aprovados;
- dados oficiais: **13 competências, 12 comparações e 13 revisões ativas `r2`**;
- privacidade persistente: **zero bloqueio** na auditoria final do PostgreSQL e dos pacotes ativos;
- desempenho: caminhos originais e recorte regional anual atendem à meta; recorte municipal anual está registrado como parcial;
- inspeção visual: realizada informalmente pelo Product Owner no frontend provisório; não substitui homologação UX;
- aprovações de Gabriel, Emili, do novo integrante de UI/UX e do professor: **pendentes**.

## Pendências rastreáveis

1. Formalizar A1 com matriz externa e filial regional em uma fixture dedicada.
2. Completar B4 para ausência de empresa, B5 para lacuna e B9 para ambiguidade societária localizada.
3. Executar B3/C5 quando houver uma nova janela real ou fixture completa de expansão temporal.
4. Adicionar teste funcional negativo explícito de pesquisa por PF para D2.
5. Executar a limpeza manual das fontes nacionais temporárias no momento aprovado para D6.
6. Otimizar as projeções do dashboard para recortes municipais longos e revalidar D5.
7. Coletar homologação de Gabriel, Emili, do novo integrante de UI/UX e do professor sem antecipar seus aceites.
8. Configurar um token público Mapbox restrito e executar a homologação visual externa do mapa; a operação degradada sem token já está aprovada.
