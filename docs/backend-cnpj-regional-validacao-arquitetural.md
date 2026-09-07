# Backend CNPJ Regional — validação de produto e arquitetura

**Estado:** implementação local em validação técnica; revisão dos demais stakeholders pendente  
**Responsável pela validação:** Tiago, Product Owner e Tech Lead  
**Revisores técnicos e funcionais:** Gabriel, pesquisa e QA; Emili, Scrum e documentação; novo integrante, UI/UX e Product Discovery; professor orientador

**Data:** 24 de agosto de 2026  
**Marco interno:** 30 de setembro de 2026  
**Entrega oficial:** novembro de 2026, em data a confirmar

**Referências:**

- [`PROJETO.md`](../PROJETO.md), visão, escopo, requisitos e cronograma;
- [`CONTEXT.md`](../CONTEXT.md), linguagem do domínio;
- [`backend-cnpj-regional-decision-ledger.md`](backend-cnpj-regional-decision-ledger.md), evidências e histórico das 26 decisões;
- [`backend-cnpj-regional-plano-implementacao.md`](backend-cnpj-regional-plano-implementacao.md), plano técnico aprovado para implementação local;
- [`modelagem-banco-dados.md`](modelagem-banco-dados.md), modelo relacional aprovado para implementação inicial;
- [`arquitetura-geral.canvas`](arquitetura-geral.canvas), visão geral em Obsidian Canvas;
- [`matriz-aceitacao-mvp.md`](matriz-aceitacao-mvp.md), estado dos 34 cenários;
- [`manual-operacional.md`](manual-operacional.md), execução e validação local;
- [`evidencias/g3-g5-janela-oficial.md`](evidencias/g3-g5-janela-oficial.md), volume oficial e produto integrado;
- [`evidencias/g6-regressao-interna.md`](evidencias/g6-regressao-interna.md), regressão técnica e limite do aceite;
- [`docs/adr/`](adr/), decisões arquiteturais de maior custo de reversão;
- `/Users/tiagomonteiro/Downloads/triangulo_mineiro_35_municipios_ibge.csv`, recorte municipal recebido;
- `/Users/tiagomonteiro/gcertifica/receita_federal/documentacao/LAYOUT_DADOS_ABERTOS_CNPJ.pdf`, layout público usado como referência;
- [arquivos públicos do CNPJ](https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9), [correspondência TOM–IBGE](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/orgaos-e-municipios) e [municípios do IBGE](https://servicodados.ibge.gov.br/api/v1/localidades/estados/31/municipios).

Para uma visão de dois minutos, leia as seções 1 e 2. Para uma revisão decisória, percorra os títulos da seção 6 e use as respostas curtas. Para aprofundamento técnico, consulte as seções 3, 7, 8 e 9.

## 1. Resumo executivo de negócio

### Problema

Consultas cadastrais convencionais mostram principalmente o estado atual de um CNPJ. Pequenas e médias empresas que dependem de clientes, fornecedores e parceiros não conseguem responder com facilidade quando houve mudança de situação, endereço, atividade, capital ou quadro societário, nem observar a evolução empresarial de sua região.

### Impacto para clientes e operação

O acompanhamento manual de vários CNPJs é repetitivo, lento e sujeito a esquecimento. Sem histórico, uma alteração relevante pode ser percebida tarde; sem agregação regional, gestores, contadores e equipes B2B perdem uma visão objetiva da movimentação econômica local. Se nada mudar, o usuário continuará consultando empresas individualmente e sem uma linha do tempo explicável.

### Resultado desejado

Transformar competências mensais dos dados abertos do CNPJ em uma aplicação local, pesquisável e rastreável que:

- represente os 35 municípios aprovados do Triângulo Mineiro;
- mostre fotografias cadastrais mensais de empresas, estabelecimentos e participações societárias;
- explique o que mudou entre competências consecutivas;
- apresente indicadores regionais sem confundir empresa com estabelecimento;
- preserve privacidade, proveniência, integridade temporal e capacidade de recálculo.

O produto não promete tempo real nem a data diária exata de toda alteração. Ele afirma apenas o que a fonte mensal permite comprovar.

### Critérios de sucesso

O MVP interno de 30 de setembro somente estará concluído quando:

1. as 13 competências de `2025-08` a `2026-08` estiverem preparadas, validadas e importadas;
2. empresas reais puderem ser pesquisadas por CNPJ, razão social e nome fantasia;
3. a página de empresa apresentar estabelecimentos, quadro societário e origem temporal dos dados;
4. a timeline produzir corretamente os dez eventos P0;
5. o dashboard filtrar ao menos por competência, município e CNAE;
6. lotes, revisões e alertas puderem ser acompanhados;
7. os comandos de preparação e importação forem reproduzíveis;
8. regras críticas, importador e aceitação manual possuírem testes documentados;
9. a solução completa iniciar localmente por Docker Compose;
10. não houver erro fatal conhecido e os alertas respeitarem a regra de qualidade.

Autenticação, watchlist, cinco eventos P1 e refinamentos completos permanecem no escopo oficial de novembro, mas não bloqueiam o marco interno.

## 2. Resumo técnico

A solução será um monólito Django 5.2 com PostgreSQL, interface renderizada por Django Templates, HTML, CSS e JavaScript simples, executado localmente por Docker Compose. Preparação, importação, regras de comparação, aplicação web e acesso ao banco permanecerão no mesmo projeto, organizados em módulos internos.

```text
Fontes nacionais oficiais — 13 competências
                 │
                 ▼
management command de preparação
  ├── valida fontes, recorte e correspondência TOM–IBGE
  ├── descobre a coorte regional de estabelecimentos
  ├── pseudonimiza sócios PF e descarta CPF mascarado
  └── gera manifesto da janela + 1 pacote Parquet por competência
                 │
                 ▼
management command de importação
  ├── valida contrato, hashes, sequência e qualidade
  ├── carrega staging
  └── publica atomicamente no PostgreSQL
                 │
                 ├── snapshots normalizados completos
                 ├── eventos derivados recalculáveis
                 ├── métricas regionais recalculáveis
                 └── lotes, revisões e ocorrências de qualidade
                 │
                 ▼
Django Views → Templates/HTML/CSS/JS → navegador local
```

### Contratos de dados

| Artefato | Identidade e conteúdo essencial | Exclusões relevantes |
|---|---|---|
| `establishments.parquet` | CNPJ completo e básico, matriz/filial, nome fantasia, situação, atividade principal, endereço, TOM, IBGE, presença regional, competência e hash | contatos, CNAEs secundários e situação especial |
| `companies.parquet` | CNPJ básico, razão social, natureza jurídica, capital decimal, porte, Simples, MEI, datas relacionadas, competência e hash | qualificação do responsável e ente federativo responsável |
| `partners.parquet` | empresa, chave da participação, tipo, nome, CNPJ apenas de PJ, país, qualificação, data de entrada, competência e hash | CPF completo ou mascarado, representante e faixa etária |
| manifesto JSON | janela, sequência, recorte, coorte, versões, fontes, arquivos, contagens, SHA-256 e alertas | conteúdo cadastral detalhado |

Os códigos CNPJ, IBGE e TOM serão texto. Parquet será a fonte canônica das tabelas; JSON UTF-8 será a fonte canônica dos manifestos. Relatórios CSV/JSON de QA serão apenas auxiliares.

### Persistência e derivação

O PostgreSQL armazenará fotografias normalizadas completas por entidade e competência publicada. Eventos e métricas serão derivados e recalculáveis. O estado atual será a fotografia da competência ativa mais recente, sem uma tabela paralela independente. Uma correção criará revisão nova, fará substituição atômica e recalculará a competência e os intervalos adjacentes.

### Privacidade e segurança

O CPF mascarado de sócio PF existirá somente no workspace temporário da preparação. Antes do pacote, será transformado por HMAC com segredo externo em identidade restrita à empresa e descartado. Não haverá busca por PF, correlação global, score ou perfilamento. O sistema oficial terá autenticação, CSRF, segredos fora do repositório e acesso administrativo controlado.

### Falha e operação

Um erro estrutural bloqueia desde a primeira ocorrência. Alertas localizados permitem `PUBLISHED_WITH_WARNINGS` até o limite geral por regra `max(10, ceil(0,1% das linhas elegíveis))`; `LATE_FIRST_SEEN` usa a calibração longitudinal versionada de 0,50% definida no ADR 0018. Acima do limite aplicável, a competência assume `FAILED_QUALITY_GATE`. Não haverá comparação através de lacunas. Execução será manual, sequencial e observável; cron, Celery e RabbitMQ ficam fora do MVP.

## 3. Evidências e estado atual

### Observações verificadas

- O CSV recebido contém 35 nomes e 35 códigos IBGE distintos, sem duplicidade.
- Os 35 pares foram conferidos com a relação oficial de municípios de Minas Gerais do IBGE, sem divergência.
- A correspondência oficial da Receita associou cada município a um TOM único; códigos como `0602` e `0742` comprovam que zeros iniciais são significativos.
- Em 24 de agosto de 2026, a origem pública disponibilizava 40 competências entre `2023-05` e `2026-08`, incluindo toda a janela do MVP.
- A competência `2026-08` tinha 37 arquivos e aproximadamente 7,16 GiB compactados.
- O pipeline profissional usado apenas como referência reserva, por padrão, 200 GiB livres para processar uma competência nacional e separa download, extração, transformação, carga e dump.
- O layout público atribui município, endereço, situação e atividade ao estabelecimento; dados corporativos e societários são relacionados pelo CNPJ básico.
- O CPF de PF na fonte aberta é mascarado, mas continua sendo dado pessoal pseudonimizado quando combinado a nome, empresa e qualificação.
- O backend acadêmico monolítico está implementado localmente e respeita as restrições deste documento.
- A janela sanitizada `2025-08..2026-08` possui 13 revisões ativas `r2`, 8.509.822 fotografias de empresa, 8.804.270 de estabelecimento e 4.018.362 societárias.
- Foram persistidos 278.301 eventos e 15.751 métricas derivados e recalculáveis.
- A suíte possui 68 testes aprovados em PostgreSQL, em 3,165 s; lint, 110 arquivos conformes à formatação, Django, migrações e Compose também foram aprovados.
- A auditoria dos pacotes ativos e a auditoria global do PostgreSQL terminaram sem bloqueio de privacidade.
- Os caminhos originais medidos ficaram abaixo de dois segundos. O novo recorte regional anual respondeu em 1,055 s; o recorte anual por município chegou a 8,658 s e permanece como dívida explícita de otimização.

### Interpretações aprovadas

- Treze fontes nacionais podem superar 90 GiB compactados e ocupar muito mais durante extração; a aplicação funcional deve consumir pacotes regionais, não operar rotineiramente a base nacional.
- Treze fotografias são necessárias para demonstrar 12 comparações mensais completas.
- A presença econômica regional deve partir de qualquer estabelecimento, e não apenas da matriz.
- Fotografias mensais determinam intervalos de detecção, não a data diária exata de toda mudança.
- O repositório profissional é evidência de viabilidade, não autorização para reutilizar código, credenciais, dumps ou tratamentos internos.

## 4. Escopo

### Incluído no MVP interno

- recorte oficial de 35 municípios e 13 competências consecutivas;
- preparação automatizada e manualmente iniciada da janela;
- pacotes regionais imutáveis e importação manual auditável;
- snapshots de empresas, estabelecimentos e participações societárias;
- pesquisa, detalhe, quadro societário e timeline;
- dez eventos P0;
- dashboard regional básico;
- acompanhamento administrativo de lotes, revisões e alertas;
- testes críticos e execução local por Docker Compose.

### Incluído até a entrega oficial

- cinco eventos P1: natureza jurídica, porte, Simples, MEI e qualificação societária;
- autenticação e watchlist;
- identidade visual, acessibilidade, responsividade e refinamentos de UX;
- ampliação da cobertura de testes, documentação e apresentação acadêmica.

### Explicitamente excluído

- ingestão nacional completa como operação da aplicação web;
- tempo real, cron, Celery, RabbitMQ ou Celery Beat;
- SPA, API pública, AngularJS, aplicativo móvel ou deploy em produção;
- notificações por e-mail, SMS ou WhatsApp;
- cobrança, assinatura, score, inteligência artificial ou enriquecimento privado;
- consulta por CPF, busca por nome de PF, grafo global de pessoas ou perfilamento;
- dados judiciais, financeiros, de bureaus ou integrações corporativas externas;
- reutilização não autorizada de ativos profissionais.

### Promessas de compatibilidade

- O motor aceitará qualquer janela contínua declarada em manifesto; 13 é restrição do MVP, não constante da regra geral.
- Uma expansão histórica recalculará a coorte da nova janela e regenerará pacotes sobrepostos; competências antigas não serão anexadas informalmente à coorte atual.
- Haverá inicialmente uma única janela ativa, substituída apenas após validação integral.
- Campos dos eventos P1 estarão presentes desde a primeira versão dos pacotes, evitando novo download apenas para ativar essas regras.
- Pacote com a mesma competência e o mesmo hash será no-op; hash diferente exigirá revisão explícita.
- Inclusão futura de campos excluídos exigirá versão nova do contrato e possível regeneração de pacotes.

## 5. Resumo das decisões

| # | Resultado de negócio | Decisão técnica | Responsável | Estado |
|---:|---|---|---|---|
| 1 | Um ano completo tem 12 comparações | Importar 13 competências de `2025-08` a `2026-08` | Tiago/PO | Aprovado |
| 2 | O MVP representa o recorte regional completo | Configurar e validar os 35 municípios | Tiago/PO | Aprovado |
| 3 | Filiais locais de matrizes externas contam | Determinar presença por qualquer estabelecimento | Tiago/PO | Aprovado |
| 4 | Movimentos regionais preservam continuidade | Manter todas as fotografias da coorte na janela | Tiago/PO/TL | Aprovado |
| 5 | Município possui identidade interoperável | IBGE canônico e TOM textual da fonte | Tiago/TL | Aprovado |
| 6 | O usuário opera extratos regionais | ETL monolítico em preparação e importação | Tiago/PO/TL | Aprovado |
| 7 | Cada mês é auditável e corrigível | Pacote imutável por competência e manifesto da janela | Tiago/PO/TL | Aprovado |
| 8 | Empresa e estabelecimento não se confundem | Ciclos, eventos e métricas separados | Tiago/PO | Aprovado |
| 9 | Toda fotografia oficial é completa e consecutiva | Staging e publicação atômica sem atravessar lacunas | Tiago/PO/TL | Aprovado |
| 10 | Incerteza não vira fato cadastral | Ausência gera qualidade, nunca baixa ou saída | Tiago/PO | Aprovado |
| 11 | Exceção isolada não paralisa a janela | Erro fatal e alerta localizado têm fluxos distintos | Tiago/PO/TL | Aprovado |
| 12 | Tipos são preservados e auditoria é legível | Parquet para tabelas e JSON para manifestos | Tiago/TL | Aprovado |
| 13 | CPF mascarado não atravessa a preparação | HMAC restrito à empresa e descarte antes do pacote | Tiago/PO/TL | Aprovado |
| 14 | O baseline não fabrica aberturas | Primeira competência sem eventos; abertura exige data coerente | Tiago/PO | Aprovado |
| 15 | Um fato aparece uma vez na timeline | Evento específico vence o genérico na mesma dimensão | Tiago/PO/TL | Aprovado |
| 16 | Todo evento pode ser explicado e recalculado | Snapshots completos; eventos e métricas derivados | Tiago/TL | Aprovado |
| 17 | Correções permanecem auditáveis | Revisão versionada e substituição atômica | Tiago/TL | Aprovado |
| 18 | O recorte temporal pode evoluir corretamente | Janela do MVP fixa e motor parametrizável | Tiago/PO/TL | Aprovado |
| 19 | Auditoria suficiente com retenção mínima | Fontes temporárias e pacotes ativos permanentes | Tiago/PO/TL | Aprovado |
| 20 | Setembro prova valor; novembro completa cobertura | Dez eventos P0 e cinco P1 | Tiago/PO | Aprovado |
| 21 | Estabelecimentos carregam somente dados úteis | Contrato reduzido de `establishments.parquet` | Tiago/PO/TL | Aprovado |
| 22 | A fotografia corporativa é coesa | Empresas incorporam Simples e MEI | Tiago/PO/TL | Aprovado |
| 23 | Participações mantêm identidade sem expor PF | Chave conforme tipo do sócio | Tiago/PO/TL | Aprovado |
| 24 | A timeline termina onde termina a evidência | Baseline inicial e borda final aberta | Tiago/PO/TL | Aprovado |
| 25 | Muitos alertas revelam falha sistêmica | Limite geral `max(10, ceil(0,1%))`; `LATE_FIRST_SEEN` calibrado em 0,50% | Tiago/TL + Gabriel/QA | Aprovado pelo PO |
| 26 | MVP significa fluxo completo | Gate objetivo com dados, UI, operação e testes | Tiago/PO | Aprovado |

## 6. Decisões detalhadas

### 1. Um ano completo exige 13 fotografias mensais

**Visão de negócio:** O usuário deve enxergar 12 meses completos de evolução, e não apenas 12 estados que produzem 11 comparações.

**Decisão técnica:** Importar `2025-08` a `2026-08` inclusive e comparar somente pares consecutivos, totalizando 13 snapshots e 12 intervalos.

**Evidências:** O intervalo inclusivo aprovado contém 13 competências.

**Justificativa:** Tendência mensal é medida pelos intervalos entre fotografias; a fotografia inicial é necessária para calcular o primeiro mês.

**Problema evitado:** Anunciar um ano de evolução com somente 11 transições.

**Alternativa considerada:** Usar 12 competências de `2025-09` a `2026-08`; perdeu por excluir agosto de 2025 e uma comparação.

**Trade-offs e impactos:** Aproximadamente 8% mais carga histórica do que uma janela de 12 competências.

**Resposta curta:** “Para mostrar 12 mudanças mensais, precisamos das duas pontas de cada intervalo: são 13 fotografias.”

- [x] Validado por Tiago, Product Owner, em 23 de agosto de 2026.

### 2. O MVP representa os 35 municípios do Triângulo Mineiro

**Visão de negócio:** A demonstração deve refletir o recorte regional aprovado, sem apresentar quatro cidades como se fossem toda a região.

**Decisão técnica:** Carregar a referência validada de 35 municípios; usar Uberlândia, Uberaba, Araguari e Ituiutaba somente como amostra técnica.

**Evidências:** O CSV possui 35 pares únicos e todos foram confirmados na relação oficial do IBGE.

**Justificativa:** A ampliação aumenta volume, mas quase não muda a regra de filtragem; preserva muito mais valor regional.

**Problema evitado:** Indicadores rotulados como regionais, mas baseados apenas nos maiores centros.

**Alternativa considerada:** Limitar o produto às quatro cidades; perdeu por reduzir representatividade sem simplificação equivalente do software.

**Trade-offs e impactos:** Mais registros, maior duração de preparação e necessidade de medir armazenamento e memória.

**Resposta curta:** “As quatro cidades aceleram testes; o resultado oficial sempre cobre os 35 municípios.”

- [x] Validado por Tiago, Product Owner, em 23 de agosto de 2026.

### 3. A presença regional nasce em qualquer estabelecimento

**Visão de negócio:** Uma filial local representa atividade regional mesmo quando a matriz da empresa fica em outro estado ou município.

**Decisão técnica:** Incluir a empresa quando qualquer estabelecimento tiver ocorrência em um dos 35 municípios em ao menos uma competência; selecionar primeiro CNPJs completos e então seus CNPJs básicos.

**Evidências:** Município e endereço pertencem ao registro de estabelecimento, não ao registro corporativo básico.

**Justificativa:** Presença econômica e sede jurídica são propriedades diferentes.

**Problema evitado:** Excluir redes, bancos, fornecedores e outras organizações com filial local e matriz externa.

**Alternativa considerada:** Filtrar apenas pela matriz; perdeu por medir sede, não atuação regional.

**Trade-offs e impactos:** Telas e métricas devem distinguir empresas de estabelecimentos; filiais externas irmãs não entram automaticamente.

**Resposta curta:** “Quem define presença local é o estabelecimento localizado aqui, seja matriz ou filial.”

- [x] Validado por Tiago, Product Owner, em 24 de agosto de 2026.

### 4. O histórico acompanha o estabelecimento através da fronteira regional

**Visão de negócio:** O usuário deve entender quando um estabelecimento entrou ou saiu da região, em vez de vê-lo simplesmente desaparecer.

**Decisão técnica:** Formar a coorte pela união dos CNPJs completos com qualquer ocorrência regional e preservar todas as suas fotografias disponíveis na janela; métricas contam somente ocorrências dentro do recorte.

**Evidências:** Um filtro mensal isolado remove a fotografia externa necessária para provar a mudança de localização.

**Justificativa:** Continuidade histórica exige observar os dois lados da fronteira.

**Problema evitado:** Confundir mudança para outra cidade com baixa ou falha de dados.

**Alternativa considerada:** Filtrar os 35 municípios de forma independente em cada mês; perdeu por destruir o histórico de entrada e saída.

**Trade-offs e impactos:** Duas passagens sobre as fontes e armazenamento de fotografias externas adicionais.

**Resposta curta:** “Guardamos o antes e o depois do estabelecimento; só os meses dentro da região contam nos indicadores regionais.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 5. O município conserva a identidade IBGE e traduz o código da Receita

**Visão de negócio:** Municípios devem ser reconhecidos de forma interoperável e sem depender de nomes ambíguos ou de um código particular da fonte.

**Decisão técnica:** Usar IBGE textual de sete dígitos como identidade canônica e TOM textual de quatro dígitos como identificador da Receita, ligados por referência versionada.

**Evidências:** O CSV e o IBGE usam sete dígitos; o CNPJ usa TOM, incluindo valores com zero inicial como `0602` e `0742`.

**Justificativa:** IBGE facilita documentação e integração; TOM preserva rastreabilidade da origem.

**Problema evitado:** Perda de zeros, relação por nome e acoplamento do domínio à Receita.

**Alternativa considerada:** Adotar TOM como chave principal; perdeu em interoperabilidade e clareza externa.

**Trade-offs e impactos:** A aplicação manterá e validará explicitamente a correspondência TOM–IBGE, inclusive para municípios externos encontrados na coorte.

**Resposta curta:** “IBGE identifica o município no produto; TOM explica como ele chegou da Receita.”

- [x] Validado por Tiago, Tech Lead, em 24 de agosto de 2026.

### 6. A preparação nacional e a importação regional são estágios do mesmo monólito

**Visão de negócio:** O produto deve usar dados reais sem exigir que o usuário opere dezenas de gigabytes nacionais no uso cotidiano.

**Decisão técnica:** Criar um comando automatizado de preparação da janela e outro de importação da competência, ambos manuais e pertencentes ao mesmo projeto Django.

**Evidências:** Uma competência compactada tem cerca de 7,16 GiB; o pipeline de referência reserva 200 GiB livres para o processamento nacional.

**Justificativa:** Separar aquisição pesada do uso funcional torna testes, falhas e reprocessamentos controláveis sem violar o requisito de monólito.

**Problema evitado:** Acoplar download e extração nacional à interface web ou depender de infraestrutura profissional.

**Alternativa considerada:** Restaurar ou tratar cada base nacional durante a importação funcional; perdeu por custo operacional e baixa testabilidade.

**Trade-offs e impactos:** Dois comandos documentados e uma fronteira intermediária de pacotes.

**Resposta curta:** “É um monólito com duas etapas operacionais: primeiro prepara o recorte; depois a aplicação importa e usa esse recorte.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 7. Cada competência viaja em um pacote imutável da mesma janela

**Visão de negócio:** Cada mês deve ser rastreável e corrigível sem esconder a identidade ou o estado dos demais meses.

**Decisão técnica:** Gerar um pacote imutável por competência e um manifesto que vincule período, sequência, coorte, recorte, versões, fontes e hashes.

**Evidências:** Importação e comparação são mensais; um pacote único ampliaria o impacto de qualquer correção.

**Justificativa:** Unidade mensal reduz o raio de falha enquanto o manifesto impede combinações incompatíveis.

**Problema evitado:** Misturar coortes ou regenerar silenciosamente toda a janela para corrigir um mês.

**Alternativa considerada:** Um artefato único com 13 competências; perdeu por aumentar reprocessamento e dificultar auditoria.

**Trade-offs e impactos:** Mais manifestos, arquivos e verificações de consistência.

**Resposta curta:** “Cada mês é independente para correção, mas o manifesto garante que todos pertencem à mesma história.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 8. Empresa e estabelecimento possuem ciclos de vida distintos

**Visão de negócio:** A baixa de uma filial não pode ser apresentada como encerramento de toda a empresa.

**Decisão técnica:** Separar identidades, snapshots, eventos e métricas corporativos dos pertencentes ao CNPJ completo; não criar `COMPANY_CREATED` ou `COMPANY_CLOSED` no MVP.

**Evidências:** Situação, abertura, baixa, endereço e CNAE pertencem ao estabelecimento; razão social, natureza, capital, porte e sociedade pertencem à empresa.

**Justificativa:** O modelo deve respeitar a propriedade dos atributos na fonte oficial.

**Problema evitado:** Alegações cadastrais falsas e indicadores inflados por mistura de matriz, filial e empresa.

**Alternativa considerada:** Usar “empresa” como entidade genérica; perdeu por apagar diferenças essenciais do domínio.

**Trade-offs e impactos:** Mais entidades e rótulos na interface, com ganho de precisão conceitual.

**Resposta curta:** “Empresa é o CNPJ básico; abertura, baixa e endereço pertencem a cada estabelecimento.”

- [x] Validado por Tiago, Product Owner, em 24 de agosto de 2026.

### 9. Uma competência oficial precisa ser íntegra e consecutiva

**Visão de negócio:** Um evento mensal só é confiável quando compara duas fotografias completas e consecutivas.

**Decisão técnica:** Validar em staging, publicar snapshots, eventos e métricas atomicamente e impedir que competências posteriores atravessem uma lacuna.

**Evidências:** Comparar dezembro diretamente com fevereiro atribuiria mudanças de dois intervalos a um único mês.

**Justificativa:** A promessa central é uma sequência mensal conhecida, não apenas uma coleção de estados disponíveis.

**Problema evitado:** Publicação parcial, métricas inconsistentes e eventos atribuídos ao intervalo errado.

**Alternativa considerada:** Aceitar cargas parciais ou pular competências inválidas; perdeu por quebrar a integridade temporal.

**Trade-offs e impactos:** Um pacote inválido bloqueia a publicação dos posteriores até a correção.

**Resposta curta:** “Sem fotografia completa do mês anterior, não existe comparação mensal confiável.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 10. Ausência cadastral não prova encerramento ou saída regional

**Visão de negócio:** O sistema somente deve afirmar baixa ou saída quando existir evidência cadastral explícita.

**Decisão técnica:** Registrar ausência como `DataQualityIssue`, suspender a comparação individual e exigir situação baixada para `ESTABLISHMENT_CLOSED` ou nova localização externa para `LEFT_REGION`.

**Evidências:** Uma linha pode faltar por problema de fonte, extração, coorte ou correção; ausência não informa situação nem endereço.

**Justificativa:** Incerteza operacional não pode ser convertida em fato de negócio.

**Problema evitado:** Alegar falsamente encerramento, baixa de filial ou saída regional.

**Alternativa considerada:** Interpretar desaparecimento como baixa ou saída; perdeu por não possuir prova suficiente.

**Trade-offs e impactos:** Algumas timelines terão lacunas e menos eventos, privilegiando precisão.

**Resposta curta:** “Se o registro sumiu, sabemos apenas que faltou; baixa e saída exigem um estado posterior que as comprove.”

- [x] Validado por Tiago, Product Owner, em 24 de agosto de 2026.

### 11. Falhas sistêmicas bloqueiam; ocorrências isoladas permanecem visíveis

**Visão de negócio:** Uma exceção isolada não deve esconder todos os dados válidos, mas corrupção estrutural não pode ser publicada silenciosamente.

**Decisão técnica:** Classificar ocorrências em erro fatal de competência ou alerta localizado; alertas geram `DataQualityIssue`, `PUBLISHED_WITH_WARNINGS` e suspensão apenas das entidades afetadas.

**Evidências:** Bloquear uma janela por uma linha é frágil; aceitar hash, esquema ou identidade estruturalmente inválidos compromete tudo.

**Justificativa:** A severidade precisa refletir alcance e isolabilidade do problema.

**Problema evitado:** Tanto indisponibilidade desnecessária quanto publicação silenciosa de corrupção sistêmica.

**Alternativa considerada:** Bloquear diante de qualquer inconsistência; perdeu por confundir exceção com perda de integridade.

**Trade-offs e impactos:** Exige catálogo explícito de regras, severidade, contagem e transparência na interface.

**Resposta curta:** “Falha estrutural para o mês inteiro; alerta visível e isolado para a entidade afetada.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 12. Parquet preserva os tipos; JSON explica o pacote

**Visão de negócio:** Pacotes devem ser compactos e consistentes, mas sua origem e integridade precisam continuar legíveis e auditáveis.

**Decisão técnica:** Usar Parquet com tipos explícitos nas tabelas, JSON UTF-8 nos manifestos e SHA-256 nos arquivos; códigos sempre como texto.

**Evidências:** CNPJ, TOM e IBGE preservam zeros; CSV introduz inferência de tipo, encoding e delimitador no grande volume.

**Justificativa:** Cada formato atende à sua função: Parquet transporta dados tipados; JSON comunica contrato e auditoria.

**Problema evitado:** Zeros perdidos, datas ambíguas e cargas diferentes entre competências.

**Alternativa considerada:** CSV comprimido como formato canônico; perdeu por transferir ambiguidades para toda leitura.

**Trade-offs e impactos:** Parquet exige biblioteca própria e não abre diretamente como texto; CSV/JSON poderão existir apenas como relatórios de QA.

**Resposta curta:** “Parquet protege os tipos e o volume; JSON torna a procedência verificável por pessoas.”

- [x] Validado por Tiago, Tech Lead, em 24 de agosto de 2026.

### 13. O CPF mascarado termina na preparação

**Visão de negócio:** O produto acompanha empresas, não pessoas, e deve detectar mudanças societárias com a menor exposição possível.

**Decisão técnica:** Criar por HMAC uma identidade PF restrita à empresa usando segredo externo, CNPJ básico, tipo, CPF mascarado e nome normalizado; descartar o CPF antes do Parquet.

**Evidências:** CPF mascarado combinado a outros atributos continua pseudonimizado e não é necessário na aplicação funcional.

**Justificativa:** A chave local permite comparar a participação sem transportar o identificador pessoal da fonte.

**Problema evitado:** CPF mascarado em pacotes, banco, logs, testes e apresentação, além de correlação global de pessoas.

**Alternativa considerada:** Transportar o CPF mascarado e pseudonimizar na importação; perdeu por ampliar cópias sem valor funcional.

**Trade-offs e impactos:** Mudança de segredo ou regra exige regenerar pacotes; correção de nome pode aparecer como remoção e inclusão; não haverá grafo entre empresas.

**Resposta curta:** “Usamos o CPF mascarado só por instantes para criar uma chave local; ele nunca chega ao produto.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 14. O baseline não fabrica aberturas

**Visão de negócio:** Empresas antigas não podem aparecer como recém-abertas apenas porque o sistema começou a observá-las.

**Decisão técnica:** Não produzir eventos no baseline; depois dele, emitir `ESTABLISHMENT_OPENED` apenas quando a primeira aparição e a data de início forem coerentes com o intervalo consecutivo.

**Evidências:** Todos os registros aparecem pela primeira vez para o produto em `2025-08`, embora muitos existam há anos.

**Justificativa:** Início da observação e início da atividade são fatos diferentes.

**Problema evitado:** Abertura em massa artificial e confusão entre abertura e entrada regional.

**Alternativa considerada:** Tratar toda primeira aparição como abertura; perdeu por criar evento sem evidência temporal.

**Trade-offs e impactos:** Data antiga gera `LATE_FIRST_SEEN`; o baseline não oferece eventos anteriores.

**Resposta curta:** “O primeiro mês é nossa fotografia inicial, não o nascimento de todas as empresas.”

- [x] Validado por Tiago, Product Owner, em 24 de agosto de 2026.

### 15. O evento mais específico representa cada dimensão alterada

**Visão de negócio:** A timeline deve mostrar cada fato uma vez e continuar revelando mudanças independentes ocorridas no mesmo intervalo.

**Decisão técnica:** Por entidade, dimensão e intervalo, emitir apenas o evento mais específico: fechamento vence situação genérica; entrada ou saída regional vence a alteração de endereço correspondente.

**Evidências:** Uma transição para baixada satisfaz ao mesmo tempo uma mudança genérica e um encerramento específico.

**Justificativa:** Classificações sobrepostas do mesmo fato não são acontecimentos diferentes.

**Problema evitado:** Timeline repetitiva, contagens infladas e dupla interpretação da mesma transição.

**Alternativa considerada:** Emitir todo tipo tecnicamente verdadeiro; perdeu por duplicar fatos.

**Trade-offs e impactos:** O comparador precisa de precedência explícita por dimensão; dimensões independentes ainda geram eventos separados.

**Resposta curta:** “Publicamos o nome mais informativo para cada fato, sem esconder outras dimensões que também mudaram.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 16. Fotografias completas sustentam eventos recalculáveis

**Visão de negócio:** Todo evento precisa ser explicável pelo antes e depois e corrigível sem perder sua evidência.

**Decisão técnica:** Persistir snapshots completos de empresa, estabelecimento e participação por competência; derivar e permitir recálculo de eventos e métricas.

**Evidências:** Auditoria, lacunas e evolução das regras exigem os dois estados de origem.

**Justificativa:** Snapshot é evidência; evento é interpretação reproduzível dessa evidência.

**Problema evitado:** Tornar o evento a única prova ou manter uma tabela atual divergente do histórico.

**Alternativa considerada:** Guardar apenas estado atual e eventos ou usar SCD Type 2; perdeu por falta de evidência no primeiro caso e complexidade excessiva no segundo.

**Trade-offs e impactos:** Repetição de atributos inalterados e maior consumo de PostgreSQL.

**Resposta curta:** “Guardamos as fotografias para poder explicar e recalcular qualquer evento.”

- [x] Validado por Tiago, Tech Lead, em 24 de agosto de 2026.

### 17. Correções criam revisões e não sobrescritas

**Visão de negócio:** Uma correção deve melhorar o dado oficial sem apagar o que foi publicado nem interromper consultas válidas durante o processo.

**Decisão técnica:** Mesmo hash é no-op; hash diferente para a mesma competência cria revisão em staging, substitui a ativa atomicamente, marca a anterior `SUPERSEDED` e recalcula intervalos adjacentes.

**Evidências:** Corrigir uma fotografia pode mudar métricas e os eventos anterior e posterior.

**Justificativa:** Versionamento preserva auditoria e atomicidade preserva disponibilidade e consistência.

**Problema evitado:** Sobrescrita silenciosa, perda de proveniência e eventos baseados em revisões incompatíveis.

**Alternativa considerada:** Apagar e reimportar no mesmo lugar; perdeu por criar intervalo sem versão válida e eliminar evidência.

**Trade-offs e impactos:** Mais metadados, retenção temporária de artefatos substituídos e fluxo explícito de correção.

**Resposta curta:** “A correção entra como revisão nova; só substitui a atual depois de estar integralmente válida.”

- [x] Validado por Tiago, Tech Lead, em 24 de agosto de 2026.

### 18. A janela do MVP é fixa; o motor histórico não

**Visão de negócio:** O produto poderá ganhar história anterior sem chamar um backfill parcial de histórico regional completo.

**Decisão técnica:** Validar 13 competências no MVP, mas parametrizar qualquer sequência contínua; expansão cria nova janela, recalcula a coorte completa e substitui a ativa apenas após validação.

**Evidências:** A fonte oferecia 40 competências e uma janela antiga pode revelar entidades que já haviam deixado a região antes de `2025-08`.

**Justificativa:** A coorte depende de toda a janela; alterar a janela altera quem pertence ao histórico.

**Problema evitado:** Omitir empresas antigas e misturar pacotes de coortes incompatíveis.

**Alternativa considerada:** Apenas anexar meses antigos à coorte do MVP; perdeu por recuperar somente o passado das entidades já conhecidas.

**Trade-offs e impactos:** Expansão exige reprocessar a coorte e regenerar pacotes sobrepostos.

**Resposta curta:** “O motor aceita outras janelas, mas cada janela refaz sua própria coorte para continuar completa.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 19. Auditoria suficiente, retenção mínima

**Visão de negócio:** O projeto precisa ser auditável para testes e apresentação sem acumular indefinidamente arquivos nacionais volumosos ou dados pessoais temporários.

**Decisão técnica:** Remover manualmente fontes e extrações nacionais após validação; preservar URL, competência, tamanho e hash, manter manifestos e pacotes ativos e reter pacotes substituídos completos ao menos até a entrega oficial.

**Evidências:** Treze competências compactadas podem superar 90 GiB; workspaces temporários contêm CPF mascarado antes do HMAC.

**Justificativa:** A fonte pública é reproduzível, enquanto pacote ativo e manifesto são as evidências operacionais diretas do produto.

**Problema evitado:** Esgotamento de disco, retenção excessiva de dado pessoal e descarte prematuro da evidência de apresentação.

**Alternativa considerada:** Guardar fontes, extrações e revisões completas indefinidamente; perdeu por custo e superfície de privacidade.

**Trade-offs e impactos:** Reprocessamento futuro pode exigir novo download; expurgo de revisão após novembro continuará manual e rastreado.

**Resposta curta:** “Preservamos o que prova o pacote e descartamos o bruto reproduzível depois de validar.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 20. Setembro entrega dez eventos de maior valor; novembro completa os demais

**Visão de negócio:** A meta interna deve provar o fluxo inteiro e reservar outubro para ampliar cobertura sem arriscar a entrega acadêmica.

**Decisão técnica:** Implementar sete eventos de estabelecimento e três de empresa/sociedade como P0; manter cinco eventos P1 obrigatórios para novembro com seus campos presentes desde o contrato inicial.

**Evidências:** Implementar e testar 15 regras simultaneamente aumenta casos-limite sem ganho equivalente para a primeira demonstração.

**Justificativa:** Os dez P0 cobrem os fatos mais visíveis: abertura, baixa, localização, endereço, atividade, capital e composição societária.

**Problema evitado:** Atrasar o produto integrado tentando concluir toda extensão de eventos de uma vez.

**Alternativa considerada:** Exigir os 15 tipos até setembro; perdeu por elevar risco de QA e integração.

**Trade-offs e impactos:** Natureza jurídica, porte, Simples, MEI e qualificação societária ficam para outubro/novembro.

**Resposta curta:** “Setembro prova a proposta com dez eventos; novembro completa os cinco sem refazer os dados.”

- [x] Validado por Tiago, Product Owner, em 24 de agosto de 2026.

### 21. A fotografia de estabelecimento contém somente os campos necessários ao produto

**Visão de negócio:** A aplicação deve explicar pesquisa e eventos sem transportar tudo o que a fonte disponibiliza.

**Decisão técnica:** Incluir identidade, matriz/filial, nome fantasia, situação com data e motivo, início, CNAE principal, endereço normalizado, TOM, IBGE, presença regional, competência e hash.

**Evidências:** Esses campos sustentam os sete eventos P0 e os filtros aprovados; contatos e CNAEs secundários não sustentam funcionalidade do MVP.

**Justificativa:** Contrato orientado à finalidade reduz volume, privacidade e superfície de testes.

**Problema evitado:** Códigos inconsistentes, comparações instáveis e exposição desnecessária de contatos.

**Alternativa considerada:** Copiar todas as colunas nacionais de estabelecimento; perdeu por confundir disponibilidade com necessidade.

**Trade-offs e impactos:** Campo excluído que se torne funcional exigirá versão nova e regeneração dos pacotes; o catálogo municipal cobre locais externos da coorte.

**Resposta curta:** “O pacote leva o necessário para pesquisar, localizar e explicar mudanças — nada sem finalidade.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 22. A fotografia de empresa incorpora Simples e MEI

**Visão de negócio:** O usuário deve encontrar em uma única fotografia os atributos pertencentes à entidade jurídica.

**Decisão técnica:** `companies.parquet` reunirá CNPJ básico, razão social, natureza, capital decimal, porte, indicadores e datas do Simples/MEI, competência e hash.

**Evidências:** Todos são identificados pelo CNPJ básico e sustentam eventos corporativos P0/P1.

**Justificativa:** São dimensões da mesma entidade, embora venham de fontes nacionais distintas.

**Problema evitado:** Regimes atribuídos a filiais, identidades duplicadas e redownload para implementar P1.

**Alternativa considerada:** Empresas e Simples em snapshots independentes ou tabela nacional integral; perdeu por junções e estados sem ganho de domínio.

**Trade-offs e impactos:** A preparação combinará fontes e preservará sua linhagem; alerta localizado do Simples não invalida automaticamente os outros atributos.

**Resposta curta:** “Simples e MEI pertencem à empresa e entram na mesma fotografia, com origem ainda auditável.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 23. A participação societária possui identidade estável conforme o tipo do sócio

**Visão de negócio:** O histórico deve distinguir inclusão, remoção e mudança de qualificação sem transformar a aplicação em cadastro de pessoas.

**Decisão técnica:** Transportar empresa, chave, tipo, nome, CNPJ apenas de PJ, país, qualificação, entrada, competência e hash. PF usa HMAC local; PJ usa CNPJ; estrangeiro sem documento usa empresa, tipo, nome normalizado e país.

**Evidências:** Qualificação e data de entrada podem mudar e não identificam a pessoa; PF, PJ e estrangeiro oferecem evidências diferentes.

**Justificativa:** Identidade por tipo preserva estabilidade e minimiza dado pessoal.

**Problema evitado:** Correlação global de PF e falsos pares de remoção/inclusão por mudança de atributo.

**Alternativa considerada:** Linha completa da Receita ou chave única por nome, qualificação e entrada; perdeu por privacidade e instabilidade.

**Trade-offs e impactos:** Correção de nome de PF pode trocar a chave; estrangeiro sem documento pode ser ambíguo e suspender a comparação.

**Resposta curta:** “Cada tipo usa a melhor identidade disponível; para PF ela só existe dentro da empresa.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 24. A timeline começa em um baseline e termina em uma borda aberta

**Visão de negócio:** A linha do tempo deve parar onde termina a evidência e não inventar precisão diária.

**Decisão técnica:** Primeira competência sem eventos; última como estado observado sem inferência posterior; eventos pertencem ao intervalo e `detected_at` registra apenas o cálculo.

**Evidências:** Snapshots mensais não provam fatos anteriores, posteriores ou o dia exato da transição, salvo data cadastral explícita.

**Justificativa:** A interface precisa diferenciar data da fonte, intervalo observado e momento de processamento.

**Problema evitado:** Eventos antes do baseline, baixas após a borda e importação exibida como data real do fato.

**Alternativa considerada:** Atribuir mudanças ao primeiro dia do mês e prolongar o último estado indefinidamente; perdeu por falsa precisão.

**Trade-offs e impactos:** A maioria dos eventos terá precisão mensal; nova competência só compara dentro de janela validada que contenha ambas.

**Resposta curta:** “Sabemos entre quais fotografias mudou; não inventamos o dia nem fatos depois da última.”

- [x] Validado por Tiago, Product Owner e Tech Lead, em 24 de agosto de 2026.

### 25. Alertas numerosos bloqueiam a competência

**Visão de negócio:** Poucas exceções podem ser transparentes; um volume anormal indica que o mês inteiro pode estar comprometido.

**Decisão técnica:** Erro estrutural bloqueia desde a primeira ocorrência. Cada regra localizada escala quando `affected_rows > max(10, ceil(eligible_rows × 0,001))`.

**Evidências:** Limite apenas absoluto ou apenas percentual distorce tabelas de tamanhos distintos; ausência de limite permite publicar falha sistêmica.

**Justificativa:** O piso evita hipersensibilidade em tabelas pequenas e 0,1% mantém proporcionalidade nas grandes. A série oficial mostrou que `LATE_FIRST_SEEN` exige limite específico de 0,50%, uniforme na janela e documentado no ADR 0018.

**Problema evitado:** Ajustar tolerância por mês, esconder problema generalizado ou bloquear grande volume por poucas linhas.

**Alternativa considerada:** Julgamento manual, percentual puro ou quantidade fixa; perderam em reprodutibilidade ou proporcionalidade.

**Trade-offs e impactos:** O valor é hipótese inicial; será medido nas 13 competências e só poderá mudar de forma documentada, versionada e uniforme.

**Resposta curta:** “Até o limite é exceção auditável; acima dele deixa de ser localizado e o mês não passa.”

- [x] Validado por Tiago, Product Owner e Tech Lead; revisão operacional de Gabriel, QA Lead, pendente.

### 26. O MVP interno exige o fluxo histórico completo

**Visão de negócio:** A meta pessoal de setembro deve reduzir de verdade o risco da entrega de novembro, e não apenas produzir uma tela navegável.

**Decisão técnica:** O gate exige 13 competências, pesquisa e detalhe, dez eventos P0, timeline, dashboard, administração de cargas, comandos reproduzíveis, testes críticos, Docker Compose e ausência de erro fatal conhecido.

**Evidências:** Um protótipo, quatro cidades, poucas competências ou telas desconectadas não exercitam os principais riscos do produto.

**Justificativa:** Um incremento ponta a ponta libera outubro para homologar, melhorar e completar P1.

**Problema evitado:** Declarar sucesso interno enquanto pipeline, dados reais ou qualidade continuam desconhecidos.

**Alternativa considerada:** Aceitar qualquer subconjunto demonstrável até 30 de setembro; perdeu por não reduzir risco técnico de forma confiável.

**Trade-offs e impactos:** Autenticação, watchlist, cinco eventos P1 e refinamento completo não bloqueiam setembro, mas continuam obrigatórios ou desejados para novembro.

**Resposta curta:** “Só chamamos de MVP quando dados reais percorrem todo o fluxo e o resultado está testado e demonstrável.”

- [x] Validado por Tiago, Product Owner, em 24 de agosto de 2026; os aceites de pesquisa e QA, documentação e UI/UX ocorrerão durante as sprints.

## 7. Riscos, dependências e aprovações abertas

### Decisões de produto

Não existem decisões materiais abertas para iniciar o backend do MVP. Continuam pendentes, sem bloquear o backend:

- nome do produto;
- logo, paleta e identidade visual;
- personas prioritárias para validação;
- conjunto final de indicadores adicionais do dashboard;
- data oficial de entrega em novembro.

### Decisões de engenharia

- Medir tempo, memória, espaço em disco, contagens e distribuição de alertas na primeira competência e novamente na janela completa.
- A versão inicial foi ensaiada nas 13 competências. O limite geral permanece em 0,1%; `LATE_FIRST_SEEN` foi calibrado e versionado em 0,50%, aplicado uniformemente à janela inteira.
- Definir no plano de implementação tipos físicos, chaves, índices, particionamento ou não particionamento, migrações e organização dos módulos sem alterar as invariantes deste documento.
- Demonstrar que consultas comuns atendem à meta de até dois segundos no Mac-alvo com o volume real.

Esses itens são validações técnicas, não autorização para mudar coorte, semântica de eventos, privacidade ou critérios de aceite.

### Segurança, privacidade e eventual validação jurídica

- O Product Owner aprovou minimização, HMAC por empresa e proibição de busca/perfilamento de PF.
- O segredo HMAC deverá permanecer fora do repositório, dos pacotes, dos logs e dos artefatos acadêmicos.
- Gabriel deverá testar a ausência de CPF completo ou mascarado em pacote, banco, log, relatório e interface.
- O projeto não recebeu parecer jurídico e não deve apresentar a solução acadêmica como certificação de conformidade legal. Se houver publicação, usuários externos ou uso comercial, será necessária nova avaliação de privacidade, segurança e base legal.

### Infraestrutura e implantação

- O ambiente autorizado nesta fase é o Mac local com Docker Compose; capacidade real de disco deverá ser verificada antes de baixar ou extrair cada fonte nacional.
- Importações serão sequenciais e iniciadas manualmente. Nenhuma aprovação foi dada para cron, filas, cloud ou produção.
- A aderência final ao requisito acadêmico de monólito e aos artefatos solicitados deverá ser confirmada com o professor.
- Aprovação de produto não equivale a aprovação de infraestrutura, publicação externa ou reutilização de ativos profissionais.

### Dependências externas

- Disponibilidade e integridade das 13 competências públicas da Receita.
- Estabilidade ou versionamento da correspondência oficial TOM–IBGE.
- Espaço local suficiente para download e extração temporária.
- Participação de Gabriel em pesquisa e QA, de Emili em Scrum e documentação e do novo integrante em discovery, fluxos e protótipos.

## 8. Impacto na implementação

Esta seção delimita superfícies afetadas; ela não constitui implementação nem substitui o plano técnico posterior.

### Aplicação e módulos

- Um projeto Django 5.2 monolítico com módulos internos para catálogo geográfico, janelas históricas, preparação, importação, cadastros, eventos, métricas, qualidade e interface.
- Dois management commands finos, delegando regras a serviços reutilizáveis equivalentes a `PrepareHistoricalWindowService` e `ImportSnapshotService`.
- Views e templates para pesquisa, detalhe, timeline, dashboard e administração das importações; autenticação e watchlist entram no ciclo oficial, sem bloquear setembro.

### Persistência e migrações

O modelo físico deverá representar pelo menos:

- `Municipality`, `HistoricalWindow` e versões do contrato;
- `Company`, `Establishment` e suas fotografias por competência;
- participação societária e sua fotografia por competência;
- `ChangeEvent`, `RegionalMonthlyMetric`, `ImportBatch` e `DataQualityIssue`;
- revisão ativa e substituída de cada competência.

Chaves, unicidades e relações deverão impedir duas fotografias ativas da mesma entidade na mesma competência e preservar códigos textuais. Não haverá tabela de “estado atual” independente.

### Contratos e artefatos

- Especificar schemas Parquet versionados para `companies`, `establishments` e `partners`.
- Especificar schema JSON do manifesto de janela e dos metadados de pacote.
- Produzir referência TOM–IBGE versionada, com indicador de pertencimento aos 35 municípios.
- Documentar algoritmo e versão do hash de registro, normalização, HMAC e precedência de eventos.

### Regras e recálculo

- Comparadores separados por entidade e dimensão.
- Geração inicial dos dez eventos P0 e posterior ativação dos cinco P1 sobre os mesmos snapshots.
- Recálculo determinístico de eventos e métricas após correção de competência.
- Estados explícitos de lote, incluindo staging, publicado, publicado com alertas, substituído e falha de qualidade.

### Testes e evidências

- Testes unitários para identidade, geografia, normalização, qualidade e cada regra de evento.
- Testes de integração dos pacotes, staging, atomicidade, idempotência, revisão e lacunas.
- Testes funcionais de pesquisa, detalhe, timeline, dashboard e administração.
- Roteiro manual de aceitação, matriz de rastreabilidade, evidências e relatório de regressão mantidos por Gabriel com participação de toda a equipe.
- Testes explícitos de privacidade em arquivos, banco, logs e interface.

### Procedimentos operacionais

- Manual de preparação, importação, correção, retomada após falha, inspeção de alertas e limpeza segura dos workspaces.
- Verificação de espaço em disco antes da preparação e confirmação de hashes antes da remoção das fontes.
- Demonstração reproduzível por Docker Compose sem dependência de credenciais ou repositórios profissionais.

## 9. Cenários de aceite e validação

### Fluxo principal e domínio

| # | Cenário | Resultado esperado |
|---:|---|---|
| A1 | Matriz em São Paulo e filial em Uberlândia | Empresa e filial entram na coorte; a matriz externa não entra apenas por compartilhar o CNPJ básico |
| A2 | Estabelecimento está externo, entra em Uberaba e permanece | Histórico externo é preservado; entrada gera `ENTERED_REGION`; métricas contam apenas os meses regionais |
| A3 | Estabelecimento muda de Uberlândia para Goiânia | Gera `LEFT_REGION`, não `ADDRESS_CHANGED` duplicado nem baixa |
| A4 | Estabelecimento muda de endereço dentro do mesmo município regional | Gera `ADDRESS_CHANGED`, sem entrada ou saída regional |
| A5 | Primeira aparição após o baseline com início dentro do intervalo | Gera `ESTABLISHMENT_OPENED` |
| A6 | Primeira aparição após o baseline com data de início antiga | Gera alerta `LATE_FIRST_SEEN`, não abertura |
| A7 | Situação passa explicitamente para baixada | Gera `ESTABLISHMENT_CLOSED`, sem mudança genérica duplicada |
| A8 | Capital social muda entre competências consecutivas | Gera `SHARE_CAPITAL_CHANGED` com antes, depois e intervalo |
| A9 | Sócio aparece ou desaparece com identidade estável | Gera respectivamente `PARTNER_ADDED` ou `PARTNER_REMOVED` |
| A10 | Apenas a qualificação do sócio muda | Não fabrica remoção/inclusão; produzirá `PARTNER_QUALIFICATION_CHANGED` quando P1 estiver ativo |
| A11 | Consulta por CNPJ, razão social ou nome fantasia | Retorna entidades da coorte e informa competência e origem |
| A12 | Dashboard por município e CNAE | Conta empresas e estabelecimentos separadamente e usa somente ocorrências regionais |

### Limites temporais e qualidade

| # | Cenário | Resultado esperado |
|---:|---|---|
| B1 | Importação de `2025-08` | Publica baseline e métricas, sem eventos derivados anteriores |
| B2 | Consulta de `2026-08` sem competência posterior | Mostra último estado observado, sem inferência depois da borda |
| B3 | `2026-09` passa a integrar uma nova janela validada | Permite comparar `2026-08 → 2026-09` dentro dessa janela |
| B4 | Empresa ou estabelecimento some por um mês | Registra qualidade e suspende a comparação; não gera fechamento ou saída |
| B5 | Janeiro falha e fevereiro está preparado | Fevereiro não é publicado nem comparado através da lacuna |
| B6 | Hash, schema, competência ou identidade estrutural é inválido | Falha desde a primeira ocorrência e preserva a última versão ativa |
| B7 | Regra localizada afeta até seu limite versionado: 0,1% geral ou 0,50% para `LATE_FIRST_SEEN` | Publica com alertas e suspende somente as entidades afetadas |
| B8 | A mesma regra ultrapassa o limite | Lote assume `FAILED_QUALITY_GATE` e não publica |
| B9 | Sócio estrangeiro sem documento é ambíguo | Registra alerta e suspende somente a comparação societária afetada |

### Idempotência, correção e recuperação

| # | Cenário | Resultado esperado |
|---:|---|---|
| C1 | Reimportar competência ativa com o mesmo hash | Operação no-op, sem duplicar snapshots, eventos ou métricas |
| C2 | Importar a mesma competência com hash diferente | Exige revisão explícita; versão ativa permanece disponível durante staging |
| C3 | Nova revisão válida é publicada | Substituição atômica, anterior marcada `SUPERSEDED` e intervalos adjacentes recalculados |
| C4 | Nova revisão falha | Revisão anterior continua ativa e nenhuma publicação parcial permanece |
| C5 | Usuário adiciona competências anteriores | Cria nova janela e recalcula a coorte; não anexa meses à coorte antiga |
| C6 | Pacote de outra coorte ou contrato é misturado | Manifesto e importador rejeitam a combinação |

### Privacidade, segurança e operação

| # | Cenário | Resultado esperado |
|---:|---|---|
| D1 | Inspeção de Parquet, manifesto, PostgreSQL, logs e relatório de QA | Nenhum CPF completo ou mascarado é encontrado |
| D2 | Tentativa de pesquisar por nome de sócio PF | Funcionalidade inexistente ou bloqueada; sócio aparece apenas no contexto da empresa |
| D3 | Mesma PF participa de empresas distintas | Chaves não permitem correlação global automática |
| D4 | Execução local limpa | Docker Compose inicia aplicação e PostgreSQL com instruções documentadas |
| D5 | Consulta comum no volume integral | Responde em até dois segundos no ambiente local-alvo |
| D6 | Preparação termina e pacotes são validados | Fontes podem ser removidas manualmente; URL, tamanho, competência e hash permanecem |
| D7 | Processo de importação falha | Estado, progresso, duração e erro ficam auditáveis; transação não corrompe a competência ativa |

### Gate do MVP interno

O aceite de 30 de setembro exige que todos os P0 sejam demonstrados sobre as 13 competências reais, com os cenários críticos acima automatizados ou documentados. Quatro cidades, menos competências, dados fictícios ou telas desconectadas serão registrados como versão parcial.

## 10. Validação dos stakeholders

### Situação das validações

| Área | Responsável | Estado | Evidência ou próxima ação |
|---|---|---|---|
| Semântica e escopo de produto | Tiago, Product Owner | Validado | 26 decisões aprovadas em 23–24/08/2026 |
| Direção arquitetural | Tiago, Tech Lead | Validado para planejamento | ADRs 0001–0018 aceitos |
| Qualidade e testabilidade | Gabriel, QA Lead | Pendente | Revisar cenários, limite inicial e matriz de testes |
| Documentação e processo | Emili | Pendente | Revisar atas, termos e artefatos acadêmicos |
| UI/UX e Product Discovery | Novo integrante | Pendente | Revisar dores, personas, fluxos, wireframes e protótipo |
| Aderência acadêmica | Professor orientador | Pendente | Confirmar monólito, escopo e entregáveis |
| Capacidade do ambiente local | Tiago | Validada internamente | 13 competências preparadas/importadas e consultas comuns abaixo de dois segundos; revisão de Gabriel pendente |
| Publicação externa ou produção | Não solicitada | Fora do escopo | Exigiria nova aprovação técnica, de segurança e privacidade |

### Checklist do documento

- [x] Problema, público, impacto e resultado desejado estão explícitos.
- [x] As 26 decisões têm responsável, evidência, alternativa e trade-off.
- [x] Identidade, ciclo de vida, propriedade dos dados e limites temporais estão definidos.
- [x] Contratos, persistência, recálculo, falha, idempotência e revisão estão definidos.
- [x] Privacidade, segurança e retenção estão explícitas.
- [x] Escopo interno, escopo oficial e exclusões estão separados.
- [x] `PROJETO.md`, `CONTEXT.md`, ledger e ADRs foram cruzados e atualizados.
- [ ] Gabriel valida a estratégia e os cenários de QA.
- [ ] Emili valida processo e documentação.
- [ ] O novo integrante valida discovery, linguagem de interface e experiência.
- [ ] Professor valida aderência acadêmica.
- [x] A janela oficial confirma as hipóteses de capacidade, qualidade e desempenho no Mac-alvo.

### Gate para implementação

As decisões de produto estão prontas para virar um plano técnico. A implementação não deve alterar silenciosamente estas invariantes; qualquer contradição descoberta em dados reais volta ao ledger e ao stakeholder responsável.

- [x] Tiago autorizou iniciar o plano e o desenvolvimento local do backend em 24 de agosto de 2026.
