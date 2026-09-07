# Plano — CNPJ alfanumérico e fontes públicas

**Estado:** Fase 0 implementada e validada; demais fases mantidas em roadmap

**Data:** 26 de agosto de 2026

**Responsável técnico:** Tiago, PO, Tech Lead e desenvolvedor full stack

**QA:** Gabriel

**Scrum e documentação:** Emili

**UI/UX e Product Discovery:** novo integrante, nome a registrar

**Marco interno:** 30 de setembro de 2026

**Entrega acadêmica oficial:** novembro de 2026

## 1. Objetivo

Preparar estruturalmente o produto para o CNPJ alfanumérico e, somente depois desse gate,
experimentar fontes públicas gratuitas que enriqueçam a análise das empresas com presença no
Triângulo Mineiro.

Este ciclo autoriza exclusivamente a **Fase 0**. CEIS, CNEP, TCU, Lista Suja, CAFIMP e outros
conectores permanecem documentados, mas não serão implementados antes de nova aprovação.

## 2. Decisões vigentes

- a aplicação permanece um monólito Django com PostgreSQL;
- o CNPJ canônico é armazenado sem máscara e em letras maiúsculas;
- os oito primeiros caracteres formam o CNPJ básico;
- os doze primeiros caracteres do CNPJ completo podem ser letras ou números;
- os dois últimos caracteres são dígitos verificadores numéricos;
- CNPJs numéricos existentes continuam válidos;
- integrações futuras usarão somente download público em lote, API pública documentada ou
  exportação manual reproduzível;
- CAPTCHA, serviço de quebra de CAPTCHA, base paga e consulta individual em massa ficam fora;
- cruzamentos futuros usarão somente CNPJ completo ou CNPJ básico exatos, nunca nome aproximado;
- pessoas físicas das novas fontes serão descartadas na preparação e não serão persistidas.

## 3. Fase 0 — compatibilidade com CNPJ alfanumérico

### 3.1. Domínio do CNPJ

Criar um componente central que:

- normalize entrada com ou sem máscara;
- converta letras minúsculas para maiúsculas;
- rejeite caracteres não permitidos;
- valide CNPJ básico com oito caracteres alfanuméricos;
- valide CNPJ completo com doze caracteres alfanuméricos e dois DVs numéricos;
- calcule os DVs pelo algoritmo oficial de módulo 11 e conversão ASCII menos 48;
- extraia o CNPJ básico;
- formate o CNPJ completo sem assumir que ele contém somente números.

### 3.2. Banco de dados

- substituir as constraints numéricas de `Company.cnpj_basic`;
- substituir a constraint de `Establishment.cnpj`;
- substituir a constraint de `PartnerSnapshot.partner_cnpj_basic`;
- manter `max_length=8` e `max_length=14`;
- preservar unicidade, índices e relacionamentos existentes;
- garantir armazenamento canônico em maiúsculas.

### 3.3. Preparação e importação da Receita

- validar a coorte regional com o formato alfanumérico;
- normalizar raiz, ordem e dígitos verificadores antes de gerar registros e hashes;
- validar o DV do CNPJ completo durante a preparação e durante a importação;
- aceitar identificador de sócio PJ com oito ou quatorze caracteres;
- fazer os formatos de oito e quatorze caracteres gerarem a mesma identidade societária quando
  representam a mesma raiz;
- rejeitar estruturalmente CNPJ inválido, sem correção silenciosa;
- preservar hashes e pacotes numéricos já existentes.

### 3.4. Portal

- pesquisar por CNPJ básico ou completo, com ou sem máscara e sem diferença entre maiúsculas e
  minúsculas;
- adaptar filtros de eventos e da linha do tempo;
- manter URLs de detalhe e watchlist compatíveis com letras;
- formatar a apresentação sem remover caracteres alfanuméricos;
- preservar a pesquisa textual por razão social e nome fantasia.

### 3.5. Gate G0

A Fase 0 termina somente quando:

1. `00.000.000/E08G-12`, primeiro exemplo oficial emitido, for aceito;
2. CNPJs numéricos atuais continuarem válidos;
3. DV incorreto, letra no DV e caractere proibido forem rejeitados;
4. identificadores de sócio PJ com oito e quatorze caracteres produzirem a mesma raiz e chave;
5. pacote sintético alfanumérico atravessar preparação, Parquet, importação e consulta;
6. os 13 pacotes numéricos existentes continuarem compatíveis;
7. reimportação idêntica continuar sendo `no-op`;
8. busca, detalhe, eventos e watchlist aceitarem o formato novo;
9. migrações, checks do Django, lint e suíte completa passarem.

## 4. Fase 1 — laboratório de fontes públicas

**Estado:** roadmap, não autorizada neste ciclo.

Criar posteriormente um módulo interno `apps/enrichment` para realizar experimentos sem publicar
resultados no portal. O fluxo planejado é:

```text
fonte oficial
    → artefato original e SHA-256
    → parser específico
    → normalização e exclusão de PF
    → validação de CNPJ
    → cruzamento exato com a revisão regional ativa
    → relatório de viabilidade
    → decisão de promover ou descartar a fonte
```

A quantidade atual de empresas não será fixada no código. Cada experimento consultará a revisão
publicada usada como coorte e registrará sua contagem no relatório.

## 5. Fase 2 — experimentos priorizados

**Estado:** roadmap, não autorizada neste ciclo.

| Ordem | Fonte | Aquisição prevista | Gate específico |
|---:|---|---|---|
| 1 | CEIS e CNEP | planilhas completas do Portal da Transparência | manter cadastros e sanções separados |
| 2 | Lista Suja e CEAC | CSV ou XLSX oficial do MTE | distinguir cadastro e ajustamento de conduta |
| 3 | TCU — licitantes inidôneos | webservice oficial com carga completa | não executar uma chamada por CNPJ |
| 4 | CAFIMP | planilha manual “listar todos/gerar planilha” | adiar se exigir CAPTCHA ou acesso privilegiado |

Cada relatório deverá registrar fonte, URL, data de aquisição, hash, versão do parser, linhas
totais, PF descartadas, PJ válidas, CNPJs inválidos, correspondências, duplicidades, situação
temporal, custo de processamento e amostra conferida manualmente.

Uma fonte será promovida somente se sua aquisição for reproduzível, o casamento for exato, a
reimportação for idempotente, as rejeições forem explicadas e houver valor informacional regional.

## 6. Fase 3 — persistência das fontes aprovadas

**Estado:** roadmap, não autorizada neste ciclo.

Persistir snapshots completos e normalizados de PJ por fonte. Os registros de origem serão
imutáveis e os vínculos regionais serão derivados e recalculáveis. A modelagem candidata contém:

- `PublicDataSource`;
- `PublicSourceSnapshot`;
- `PublicEvidenceSnapshot`;
- `PublicEvidenceMatch`;
- `PublicSourceIssue`.

Campos centrais serão tipados. JSON será reservado a metadados extras de auditoria e nunca será
apresentado cru na interface.

## 7. Fase 4 — interface de evidências públicas

**Estado:** roadmap, não autorizada neste ciclo.

Adicionar à página da empresa uma seção de evidências que mostre fonte, categoria, vigência,
órgão, processo, período, estabelecimento afetado, data do snapshot e link oficial. Ausência de
resultado será descrita como “nenhum registro encontrado nas fontes consultadas”, nunca como prova
de regularidade ou segurança.

## 8. Fase 5 — roadmap posterior

- CEPIM e acordos de leniência;
- PNCP e Compras.gov;
- RNTRC/ANTT;
- ANP;
- SIF/MAPA;
- Cadastur;
- PGFN, com tratamento semântico próprio;
- IBAMA, distinguindo autuação, embargo e decisão definitiva;
- TCE-MG, condicionado a uma fonte pública reproduzível;
- eventos temporais das evidências;
- filtros por fonte, período, município e CNAE;
- alertas na watchlist;
- evidências indiretas de sócios PJ, sempre rotuladas como indiretas;
- exportações CSV e PDF.

Permanecem fora do roadmap imediato certidões com CAPTCHA, consultas por CPF, scraping de
processos judiciais, bases privadas, casamento aproximado por nome e score automático de risco.

## 9. Sequência de commits planejada

```text
docs: record public enrichment roadmap
test(cnpj): define alphanumeric compatibility
feat(registry): add alphanumeric CNPJ domain
feat(pipeline): accept alphanumeric CNPJ data
feat(portal): support alphanumeric CNPJ queries
docs(cnpj): record compatibility evidence
```

Os conectores terão commits próprios somente depois de aprovados.

## 10. Evidências da Fase 0

Implementação concluída em 26 de agosto de 2026:

- domínio central normaliza, valida, extrai e formata CNPJ numérico ou alfanumérico;
- constraints do PostgreSQL aceitam a forma canônica alfanumérica e preservam os tamanhos atuais;
- preparação, Parquet, importação e identidade de sócio PJ usam o mesmo domínio;
- pesquisa, detalhe, eventos e watchlist aceitam raiz ou CNPJ completo alfanumérico;
- o vetor oficial `00.000.000/E08G-12` e o vetor sintético `AB.CDE.F12/3456-80` são cobertos;
- DV incorreto, letra na posição de DV, caractere proibido e forma não canônica no banco são
  rejeitados;
- a migração `registry.0003` foi aplicada sem reescrever fotografias históricas;
- os pacotes numéricos oficiais permaneceram compatíveis: a reimportação das 13 competências foi
  `no-op`, lote `2fd0d25e-9405-412d-bf55-d61961a316ca`, preservando 278.301 eventos e 21.169
  alertas de qualidade;
- suíte completa, checks do Django, verificação de migrações, lint e formatação passaram.

Nenhum conector de fonte pública foi criado nesta fase. O gate G0 está concluído; qualquer início
da Fase 1 depende de nova aprovação.
