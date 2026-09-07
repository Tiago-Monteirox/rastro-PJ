# Rastro PJ — Visão do Produto e Escopo

> Documento vivo do projeto integrador. O nome **Rastro PJ** está definido; identidade visual,
> logo e sistema de design serão desenvolvidos pela equipe.
>
> O refinamento do backend foi consolidado em [`docs/backend-cnpj-regional-validacao-arquitetural.md`](docs/backend-cnpj-regional-validacao-arquitetural.md).
> O plano técnico aprovado está em [`docs/backend-cnpj-regional-plano-implementacao.md`](docs/backend-cnpj-regional-plano-implementacao.md).
> A modelagem aprovada para a implementação inicial está em [`docs/modelagem-banco-dados.md`](docs/modelagem-banco-dados.md), com a visão geral em [`docs/arquitetura-geral.canvas`](docs/arquitetura-geral.canvas).
> A situação implementada está em [`docs/evidencias/g3-g5-janela-oficial.md`](docs/evidencias/g3-g5-janela-oficial.md), a regressão em [`docs/evidencias/g6-regressao-interna.md`](docs/evidencias/g6-regressao-interna.md), os 34 cenários em [`docs/matriz-aceitacao-mvp.md`](docs/matriz-aceitacao-mvp.md) e a operação em [`docs/manual-operacional.md`](docs/manual-operacional.md).

## 1. Resumo executivo

O projeto será uma plataforma local de inteligência cadastral que utiliza dados abertos mensais do Cadastro Nacional da Pessoa Jurídica (CNPJ), publicados pela Receita Federal, para reconstruir o histórico de empresas de uma região e detectar alterações relevantes entre competências.

O sistema terá dois eixos complementares:

1. **Inteligência regional:** indicadores sobre empresas, estabelecimentos, abertura, baixa e movimentação cadastral na região ao longo de 12 meses completos.
2. **Monitoramento individual:** pesquisa de empresas, acompanhamento de uma carteira e linha do tempo com o antes e o depois de cada mudança detectada.

O produto será executado inicialmente apenas em ambiente local, como uma aplicação monolítica em Django. A preparação regional e a importação das competências serão processos automatizados iniciados manualmente por comandos administrativos, sem edição manual dos dados, cron ou infraestrutura distribuída no MVP.

Existem dois marcos de entrega:

- **30 de setembro de 2026:** meta interna para concluir um MVP utilizável de ponta a ponta;
- **novembro de 2026:** entrega acadêmica oficial, após um período reservado para testes, correções, melhorias, documentação e preparação da apresentação.

### Estado técnico em 26 de agosto de 2026

A implementação local antecipou o cronograma inicial. A janela oficial de 13 competências está publicada em revisões sanitizadas `r2`, as 12 comparações estão disponíveis, o portal monolítico está integrado e a regressão técnica de 83 testes foi aprovada. As contagens ativas somam 8.509.822 fotografias de empresa, 8.804.270 de estabelecimento, 4.018.362 societárias, 278.301 eventos e 15.751 métricas.

Esse estado representa validação técnica interna, não a entrega acadêmica. O dashboard já permite recortes por intervalo, município e CNAE e produz rankings derivados de aumento de capital e ampliação societária. Identidade visual, artefatos de UX e as homologações funcionais, documentais, de experiência e acadêmicas continuam pendentes conforme as responsabilidades da equipe.

## 2. Problema

Empresas que mantêm relações com clientes, fornecedores e parceiros dependem de informações cadastrais atualizadas. Entretanto, acompanhar periodicamente cada CNPJ é uma atividade manual, repetitiva e sujeita a atrasos.

As consultas convencionais geralmente mostram apenas o estado atual da empresa. Elas não respondem facilmente perguntas como:

- Quando a situação cadastral mudou?
- A empresa mudou de endereço ou de atividade principal?
- O capital social aumentou ou diminuiu?
- Algum sócio entrou ou saiu?
- Quais setores cresceram ou encolheram na região?
- Quais cidades apresentaram maior movimentação empresarial no período?

## 3. Proposta de valor

Transformar publicações mensais da Receita Federal em um histórico empresarial compreensível, pesquisável e rastreável.

Em vez de apresentar apenas dados cadastrais atuais, o sistema mostrará:

- o que mudou;
- o valor anterior;
- o novo valor;
- a competência em que a mudança foi detectada;
- a origem pública dos dados.

O sistema não prometerá dados em tempo real. Uma alteração será descrita como **detectada entre duas competências mensais**, sem afirmar que ocorreu exatamente na data da publicação.

## 4. Público-alvo inicial

O público inicial será formado por pequenas e médias empresas que vendem a prazo ou dependem de fornecedores e parceiros empresariais.

Possíveis usuários:

- profissionais administrativos e financeiros;
- escritórios de contabilidade;
- compradores e gestores de fornecedores;
- equipes comerciais B2B;
- corretores de seguros;
- consultorias empresariais.

## 5. Recorte geográfico

O projeto adotará um recorte regional para tornar a base histórica viável em um computador pessoal e, ao mesmo tempo, produzir informações relevantes para a comunidade local.

### Recorte oficial aprovado

O MVP contemplará os seguintes 35 municípios do Triângulo Mineiro:

- Água Comprida;
- Araguari;
- Araporã;
- Cachoeira Dourada;
- Campina Verde;
- Campo Florido;
- Canápolis;
- Capinópolis;
- Carneirinho;
- Cascalho Rico;
- Centralina;
- Comendador Gomes;
- Conceição das Alagoas;
- Conquista;
- Delta;
- Fronteira;
- Frutal;
- Gurinhatã;
- Indianópolis;
- Ipiaçu;
- Itapagipe;
- Ituiutaba;
- Iturama;
- Limeira do Oeste;
- Monte Alegre de Minas;
- Pirajuba;
- Planura;
- Prata;
- Santa Vitória;
- São Francisco de Sales;
- Tupaciguara;
- Uberaba;
- Uberlândia;
- União de Minas;
- Veríssimo.

Uberlândia, Uberaba, Araguari e Ituiutaba poderão ser usadas como amostra técnica para desenvolvimento e testes rápidos. Essa amostra não altera o escopo oficial nem poderá ser apresentada como resultado regional completo.

A presença regional será determinada pelos estabelecimentos, pois é neles que a base do CNPJ registra município e endereço. Uma empresa será incluída quando qualquer matriz ou filial estiver localizada em um dos 35 municípios em ao menos uma competência da janela ativa. No MVP, serão consideradas as 13 competências aprovadas. A localização da matriz fora da região não excluirá uma filial regional.

Cada município será identificado no produto pelo código IBGE textual de sete dígitos. O código TOM textual de quatro dígitos será mantido como identificador da fonte CNPJ, com correspondência obtida da tabela oficial da Receita Federal.

## 6. Janela temporal

- **Período aprovado:** agosto de 2025 a agosto de 2026.
- **Fotografias:** 13 competências mensais consecutivas.
- **Comparações:** 12 intervalos entre competências consecutivas.
- **Atualização:** importação manual de cada competência.

As 13 competências representam as duas extremidades necessárias para demonstrar 12 meses completos de tendências, sazonalidade e evolução cadastral.

A primeira competência será o baseline histórico e não produzirá eventos. As 12 competências seguintes formarão os intervalos nos quais alterações poderão ser detectadas.

A última competência será tratada como borda final aberta: ela descreve o último estado observado, mas não comprova sua continuidade nem qualquer alteração posterior. Uma nova competência consecutiva poderá estender a comparação somente dentro de uma nova janela validada.

O motor histórico aceitará outras sequências contínuas declaradas por manifesto; 13 é uma regra de validação da janela do MVP, não um número fixo no código. Uma expansão para competências anteriores formará uma nova janela, recalculará a coorte sobre todo o período e regenerará os pacotes sobrepostos. Inicialmente, somente uma janela poderá estar ativa.

## 7. Fonte e recorte dos dados

A fonte primária será o conjunto de dados abertos do CNPJ publicado pela Receita Federal.

Serão utilizados somente os campos necessários ao produto:

- CNPJ básico e CNPJ completo;
- matriz ou filial;
- razão social e nome fantasia;
- natureza jurídica;
- porte;
- capital social;
- situação cadastral, motivo e data;
- data de início da atividade;
- CNAE principal;
- endereço, município e UF;
- opção pelo Simples e pelo MEI, quando pertinente;
- nome, tipo, qualificação e data de entrada de sócios;
- CPF mascarado apenas no workspace temporário da preparação descrita na seção de privacidade.

O recorte será iniciado pelos estabelecimentos localizados nos municípios aprovados. Os respectivos CNPJs básicos serão usados para selecionar os registros de empresa, Simples e quadro societário necessários. Estabelecimentos externos da mesma empresa não serão incluídos automaticamente apenas por compartilharem o CNPJ básico.

A extração usará duas etapas. Primeiro será formada a união dos CNPJs completos que tiveram ao menos uma ocorrência regional nas competências da janela. Depois serão recuperadas todas as fotografias disponíveis desses estabelecimentos durante o período, inclusive antes de sua entrada ou depois de sua saída da região. Registros externos mantidos para continuidade histórica não participarão das métricas regionais enquanto estiverem fora dos 35 municípios.

A preparação do MVP produzirá 13 pacotes imutáveis, um por competência, unidos por um manifesto da janela histórica. Outras janelas produzirão um pacote por competência declarada. O manifesto impedirá combinar competências preparadas com coortes, recortes ou versões incompatíveis.

As tabelas dos pacotes usarão Parquet com tipos explícitos. Os manifestos usarão JSON UTF-8 e declararão arquivos, hashes SHA-256, contagens, origem, versões, janela, coorte e alertas. CNPJ, IBGE, TOM e outros códigos serão sempre tratados como texto.

O contrato de `establishments.parquet` conterá:

- identidade: CNPJ completo, CNPJ básico e indicador de matriz ou filial;
- apresentação: nome fantasia;
- situação cadastral: código, data e motivo;
- atividade: data de início e CNAE principal;
- endereço normalizado: tipo e nome do logradouro, número, complemento, bairro, CEP e UF;
- município: código TOM e código IBGE;
- regionalização: indicador de ocorrência no recorte geográfico;
- auditoria: competência e hash determinístico do registro.

O catálogo TOM–IBGE usado na preparação deverá contemplar qualquer município externo encontrado nas fotografias da coorte, pois o histórico acompanha o estabelecimento antes da entrada ou depois da saída regional. Somente os 35 municípios aprovados serão marcados como pertencentes ao recorte. Telefones, e-mails, CNAEs secundários e situação especial não integrarão a fotografia de estabelecimento no MVP.

O contrato de `companies.parquet` conterá:

- identidade: CNPJ básico;
- apresentação: razão social;
- atributos corporativos: natureza jurídica, capital social com tipo decimal e porte;
- regimes: indicadores do Simples e do MEI com suas datas de opção e exclusão;
- auditoria: competência e hash determinístico do registro.

Simples e MEI serão incorporados à fotografia normalizada da empresa, pois são identificados pelo CNPJ básico e sustentam eventos P1. Qualificação do responsável e ente federativo responsável não integrarão o contrato inicial por não sustentarem eventos, filtros ou indicadores aprovados.

O contrato de `partners.parquet` conterá:

- CNPJ básico da empresa;
- chave estável da participação societária;
- tipo do sócio: PF, PJ ou estrangeiro;
- nome de exibição;
- raiz CNPJ de oito caracteres alfanuméricos do sócio somente quando ele for PJ nacional;
- país, quando aplicável;
- qualificação e data de entrada;
- competência e hash determinístico do registro.

Para PF, a chave será o HMAC restrito à empresa definido na política de privacidade. Para PJ nacional, a identidade será sua raiz CNPJ de oito caracteres alfanuméricos: fontes que entreguem o CNPJ completo de 14 caracteres serão normalizadas para os oito primeiros, enquanto fontes que já entreguem a raiz permanecerão inalteradas. Para sócio estrangeiro sem documento, a chave será derivada da empresa, do tipo, do nome normalizado e do país; colisões ou ambiguidades serão alertas de qualidade e suspenderão somente a comparação afetada. Qualificação e data de entrada não integrarão a identidade. CPF mascarado, representante legal, CPF do representante e faixa etária não entrarão no pacote.

Ficam inicialmente excluídos:

- telefone;
- e-mail;
- fax;
- CPF completo;
- representante legal;
- CPF do representante legal;
- faixa etária do sócio;
- enriquecimentos provenientes de fontes privadas ou internas.

O projeto não deverá copiar código, credenciais, dumps ou tratamentos internos de ambientes profissionais sem autorização. Sempre que possível, será produzido um extrato regional exclusivamente a partir dos campos públicos da Receita Federal.

## 8. Funcionalidades do MVP

### 8.1. Acesso e navegação

- autenticação de usuário;
- página inicial com resumo do período;
- navegação entre dashboard, pesquisa, empresas monitoradas, eventos e importações.

### 8.2. Pesquisa e consulta de empresa

- pesquisa por CNPJ;
- pesquisa por razão social;
- pesquisa por nome fantasia;
- filtros por município, situação cadastral e CNAE;
- visualização da competência mais recente disponível;
- diferenciação entre empresa e estabelecimento.

### 8.3. Detalhes da empresa

- identificação cadastral;
- situação atual;
- endereço atual;
- CNAE principal;
- capital social;
- porte e natureza jurídica;
- matriz e filiais, se incluídas no recorte;
- quadro societário público;
- linha do tempo das alterações.

### 8.4. Monitoramento

- adicionar empresa à lista de monitoramento;
- remover empresa da lista;
- listar empresas acompanhadas;
- destacar empresas monitoradas que apresentaram alterações recentes.

### 8.5. Eventos cadastrais

Eventos pertencem à entidade cujo atributo mudou. A baixa de uma filial não representa o encerramento da empresa.

Ausência de empresa ou estabelecimento em uma competência não gerará evento cadastral. Ela será registrada como ocorrência de qualidade de dados e suspenderá a comparação daquela entidade até existirem novamente fotografias consecutivas.

`ESTABLISHMENT_OPENED` exigirá primeira aparição posterior ao baseline e data de início da atividade compatível com o intervalo. Uma primeira aparição com data antiga será alerta `LATE_FIRST_SEEN`, não abertura. Existência externa anterior seguida de localização regional será `ENTERED_REGION`.

Eventos P0 de estabelecimento — obrigatórios no MVP interno de setembro:

- `ESTABLISHMENT_OPENED`;
- `ESTABLISHMENT_CLOSED`;
- `REGISTRATION_STATUS_CHANGED`;
- `ADDRESS_CHANGED`;
- `MAIN_CNAE_CHANGED`;
- `ENTERED_REGION`;
- `LEFT_REGION`.

Eventos P0 de empresa e sociedade — obrigatórios no MVP interno de setembro:

- `SHARE_CAPITAL_CHANGED`;
- `PARTNER_ADDED`;
- `PARTNER_REMOVED`.

Eventos P1 — obrigatórios para a entrega oficial de novembro:

- `LEGAL_NATURE_CHANGED`;
- `COMPANY_SIZE_CHANGED`;
- `SIMPLES_STATUS_CHANGED`;
- `MEI_STATUS_CHANGED`;
- `PARTNER_QUALIFICATION_CHANGED`.

Os campos necessários aos eventos P1 estarão presentes nos pacotes e fotografias desde o primeiro contrato. Assim, novas regras poderão recalcular os eventos sem repetir a preparação nacional.

Cada evento deverá registrar:

- tipo e identidade da entidade afetada;
- tipo do evento;
- competência anterior;
- nova competência;
- valor anterior;
- novo valor;
- data de detecção;
- lote de importação que originou o evento.

O evento será atribuído ao intervalo ordenado entre as duas competências comparadas, pois as fotografias mensais não revelam por si só o dia exato da alteração. Datas cadastrais explícitas da Receita serão preservadas como evidência quando existirem. A data de detecção representará somente o instante em que o importador calculou o evento. Nenhuma baixa, saída regional ou remoção de sócio será inferida após a última competência.

`ESTABLISHMENT_CLOSED` exigirá transição explícita para situação baixada. `LEFT_REGION` exigirá fotografia posterior com município fora do recorte aprovado.

Para a mesma entidade, dimensão e intervalo, somente o evento mais específico será publicado. Encerramento substituirá a mudança genérica para baixada; entrada ou saída regional substituirá a alteração de endereço correspondente. Mudanças em dimensões independentes continuarão gerando eventos separados.

### 8.6. Dashboard regional

- total de empresas distintas por competência;
- total de estabelecimentos por competência;
- estabelecimentos abertos e baixados por mês;
- alterações por tipo;
- evolução por município;
- CNAEs com maior crescimento ou redução;
- distribuição por situação cadastral;
- distribuição por porte;
- empresas com alterações recentes;
- filtros por período, município e CNAE.

### 8.7. Importação administrativa manual

- preparação da janela histórica por meio de um management command do Django;
- geração automatizada dos pacotes regionais a partir das fontes nacionais oficiais;
- geração de um manifesto da janela e de um pacote imutável por competência;
- importação de cada competência por outro management command do Django;
- indicação dos arquivos de entrada pelo terminal, sem edição manual de registros;
- validação dos arquivos antes de alterar a base válida;
- carga inicial em staging e publicação atômica da competência;
- bloqueio de publicação quando houver lacuna anterior na janela;
- criação e atualização de um `ImportBatch`;
- exibição no terminal da quantidade processada e dos erros;
- consulta do resultado da importação pelo sistema;
- distinção entre erros fatais e alertas de qualidade localizados;
- prevenção de importação duplicada;
- possibilidade de reprocessamento controlado;
- no-op idempotente para pacote com hash já publicado;
- criação de nova revisão quando a mesma competência possuir hash diferente;
- registro do hash e da origem dos arquivos;
- inspeção dos manifestos JSON e geração de relatórios auxiliares para QA.

## 9. Requisitos não funcionais iniciais

- **Desempenho:** consultas comuns devem responder em até dois segundos no ambiente local e no volume planejado.
- **Idempotência:** importar novamente a mesma competência e os mesmos arquivos não deve duplicar dados ou eventos.
- **Revisão controlada:** um hash diferente para competência já publicada deve exigir correção explícita, versionada e atômica, sem sobrescrita silenciosa.
- **Integridade:** uma falha de importação não deve corromper a última competência válida.
- **Atomicidade:** snapshots, eventos e métricas de uma competência devem ser publicados como uma unidade ou não ser publicados.
- **Continuidade:** comparações devem ocorrer somente entre competências consecutivas publicadas.
- **Integridade geográfica:** códigos IBGE e TOM devem preservar zeros iniciais, ser únicos no recorte e corresponder a municípios de Minas Gerais.
- **Rastreabilidade:** toda informação deve indicar competência, fonte e lote de importação.
- **Segurança:** autenticação, proteção contra CSRF, segredos fora do repositório e controle de acesso às importações.
- **Privacidade:** dados pessoais devem ser limitados ao necessário e nunca utilizados para pesquisa ou perfilamento de pessoas.
- **Usabilidade:** interface responsiva e compreensível em notebook e celular.
- **Manutenibilidade:** regras de comparação isoladas e cobertas por testes automatizados.
- **Portabilidade:** monólito e banco local inicializáveis de forma documentada, preferencialmente com Docker Compose.
- **Observabilidade:** cada importação deve possuir estado, quantidade processada, duração, resultado e mensagem de erro.
- **Transparência de qualidade:** competências publicadas com alertas devem expor quantidade, tipo e entidades afetadas, sem misturar alertas com eventos cadastrais.
- **Extensibilidade temporal:** quantidade e sequência de competências devem vir do manifesto; a validação fixa de 13 competências pertence somente à janela do MVP.
- **Retenção:** fontes nacionais e workspaces serão temporários; pacotes ativos, manifestos e auditoria serão preservados conforme a política aprovada.

## 10. Sócios pessoa física e privacidade

### 10.1. Decisão

Sócios pessoa física serão incluídos porque enriquecem significativamente o histórico societário. Entretanto, o sistema continuará sendo uma ferramenta de análise de empresas, e não de pesquisa ou perfilamento de indivíduos.

### 10.2. Dados disponíveis

Nos dados abertos da Receita Federal, o nome do sócio PF é publicado e o CPF é descaracterizado pela ocultação dos três primeiros dígitos e dos dois dígitos verificadores.

Mesmo mascarado, o CPF combinado com nome, empresa e qualificação deve ser tratado como dado pessoal pseudonimizado, e não como dado anônimo.

### 10.3. Tratamento proposto

Durante a preparação da janela histórica:

1. O sistema lê nome, tipo, CPF mascarado, qualificação e data de entrada no workspace temporário.
2. Normaliza os campos necessários à comparação.
3. Gera por HMAC uma identidade societária PF determinística e restrita à empresa, usando segredo mantido fora do código.
4. Descarta o CPF mascarado antes de gerar qualquer pacote Parquet.
5. Mantém nos pacotes e tabelas funcionais somente nome, tipo, qualificação, data de entrada e identidade societária.

### 10.4. Restrições obrigatórias

- o CPF mascarado não será exibido;
- o CPF mascarado não será pesquisável;
- o CPF mascarado não aparecerá em logs ou eventos;
- o CPF mascarado não aparecerá nos pacotes de competência, manifestos ou relatórios de QA;
- não haverá busca de empresas pelo nome de uma pessoa;
- não será construída uma rede global de relações de uma pessoa;
- o sócio será acessível somente dentro do contexto da empresa correspondente;
- eventos societários mostrarão apenas nome e qualificação;
- não haverá score, perfil ou decisão automatizada sobre pessoas físicas;
- a interface informará a origem pública e a competência dos dados.

## 11. Modelo de domínio inicial

### `Company`

Representa a entidade jurídica identificada pelo CNPJ básico. Possui presença regional quando ao menos um de seus estabelecimentos tiver uma ocorrência regional na janela histórica.

### `Establishment`

Representa uma matriz ou filial identificada pelo CNPJ completo. É considerado um estabelecimento com presença regional quando estiver localizado no recorte geográfico em ao menos uma competência da janela histórica.

### `CompanySnapshot`

Representa os atributos corporativos normalizados de uma empresa em determinada competência publicada.

### `EstablishmentSnapshot`

Representa situação, endereço, atividade e presença regional normalizados de um estabelecimento em determinada competência publicada.

### `PartnerSnapshot`

Representa a participação societária normalizada em determinada empresa e competência publicada. Para PF, utiliza identidade societária pseudônima restrita à empresa e não armazena CPF completo ou mascarado.

### `ChangeEvent`

Representa uma diferença relevante derivada de duas fotografias consecutivas e identifica se a entidade afetada é uma empresa ou um estabelecimento. Pode ser recalculado sem alterar as fotografias de origem.

### `Watchlist`

Relaciona um usuário às empresas que ele deseja acompanhar.

### `ImportBatch`

Registra origem, competência, revisão, hash, estado, progresso, duração e resultado de uma importação. O fluxo distingue recebimento, validação, staging, publicação, publicação com alertas, substituição e falha.

### `RegionalMonthlyMetric`

Armazena indicadores agregados por competência, município, CNAE, situação cadastral e tipo de entidade, sem misturar empresas com estabelecimentos.

### `DataQualityIssue`

Representa uma inconsistência ou incerteza auditável da fonte ou do processamento. Não é um evento cadastral e não autoriza inferências sobre encerramento ou saída regional.

### `Municipality`

Representa um município pela identidade canônica IBGE e mantém seu código TOM da fonte CNPJ, nome, UF e pertencimento ao recorte geográfico.

### `HistoricalWindow`

Representa uma sequência contínua de competências, sua coorte, recorte, contrato e estado. Inicialmente somente uma janela publicada poderá estar ativa.

## 12. Estratégia de armazenamento

O PostgreSQL manterá fotografias normalizadas completas das entidades em cada competência publicada da janela ativa. No MVP serão 13. Isso não representa cópias da base nacional: somente a coorte regional e os campos aprovados serão persistidos.

Estratégia recomendada:

```text
fontes mensais da janela — 13 no MVP
       ↓
descoberta da coorte regional
       ↓
histórico completo dos CNPJs selecionados
       ↓
validação e staging por competência
       ↓
comparação entre competências consecutivas
       ├── persiste fotografias normalizadas
       ├── gera eventos
       ├── gera métricas apenas das ocorrências regionais
       └── arquiva extrato compactado
```

No PostgreSQL permanecerão:

- fotografias de empresas por competência;
- fotografias de estabelecimentos por competência;
- fotografias das participações societárias por competência;
- eventos detectados;
- métricas agregadas;
- histórico das importações.

O estado atual será consultado a partir da competência publicada mais recente. Não haverá uma segunda tabela independente de estado atual que possa divergir das fotografias. Eventos e métricas serão derivados e poderão ser recalculados.

O manifesto e os pacotes regionais ativos serão mantidos fora do banco para auditoria e reprocessamento. Pacotes substituídos completos permanecerão pelo menos até a entrega acadêmica oficial, exceto quando contiverem dado pessoal proibido: nesse caso, o conteúdo será expurgado depois da publicação e validação da substituta, preservando metadados, hashes, lotes e ocorrências.

Fontes nacionais e arquivos extraídos serão temporários e removidos manualmente somente após a preparação e a validação bem-sucedidas. URL, competência, tamanho e hash permanecerão registrados. Workspaces com CPF mascarado não serão versionados ou enviados a backup. Não haverá limpeza ou expurgo automático no MVP.

Parquet será o formato canônico das tabelas intermediárias. Relatórios CSV ou JSON poderão auxiliar inspeção e testes, mas não serão usados como fonte oficial de importação.

## 13. Volume estimado e medido

### Amostra técnica com quatro cidades e sócios PF

- aproximadamente 550 mil a 650 mil estabelecimentos por competência, considerando todas as situações cadastrais;
- 6 competências: aproximadamente 4 a 8 GB;
- 13 competências: aproximadamente 9 a 18 GB;
- espaço livre recomendado: 25 a 30 GB.

### Recorte oficial com 35 municípios

- aproximadamente 800 mil a 1,2 milhão de estabelecimentos por competência;
- 6 competências: aproximadamente 7 a 15 GB;
- 13 competências: aproximadamente 16 a 33 GB;
- espaço livre recomendado: pelo menos 40 GB.

### Janela oficial preparada e importada

- coorte regional: 707.670 empresas;
- fotografias de empresa nas 13 competências: 8.509.822;
- fotografias de estabelecimento nas 13 competências: 8.804.270;
- fotografias societárias nas 13 competências: 4.018.362;
- total das três tabelas Parquet: 21.332.454 linhas;
- eventos derivados: 278.301;
- métricas derivadas: 15.751.

As contagens de fotografias são somas mensais, não entidades únicas. As estimativas iniciais de gigabytes continuam úteis apenas para preflight; o dimensionamento operacional deve usar os arquivos e o volume PostgreSQL efetivamente presentes no Mac.

### Memória RAM

- meta de uso máximo do importador: 3 a 4 GB;
- processamento em lotes de 10 mil a 50 mil registros;
- um worker de importação por vez;
- o Mac com 16 GB de RAM é suficiente para o recorte regional.

## 14. Arquitetura técnica proposta

- **Aplicação monolítica:** um único projeto Django 5.2 LTS, organizado em módulos internos;
- **Backend:** views, formulários, serviços de domínio e ORM do Django;
- **Frontend:** Django Templates, HTML, CSS e JavaScript simples;
- **Banco de dados:** PostgreSQL;
- **Ambiente local:** Docker Compose;
- **Arquivos históricos:** extratos regionais compactados;
- **Testes:** testes unitários, de integração, funcionais e de aceitação documentados.

O navegador, as regras de negócio, a importação e o acesso ao banco pertencem ao mesmo monólito. Não haverá separação entre uma API de backend e uma SPA de frontend no MVP.

Componentes:

```text
Fontes nacionais oficiais
          ↓
management command de preparação ──→ pacotes regionais
                                             ↓
management command de importação ──→ serviços de domínio ──→ ORM ──→ PostgreSQL
                                                                    ↑
Navegador ──→ URLs/Views ──→ Templates, HTML, CSS e JavaScript ─────┘
```

O frontend será renderizado no servidor. JavaScript será usado apenas onde trouxer interação real, como filtros, confirmações e gráficos. AngularJS não será adotado porque está fora de suporte oficial desde janeiro de 2022 e acrescentaria uma camada desnecessária ao monólito acadêmico.

Celery e RabbitMQ ficam fora do MVP. Eles poderão ser estudados após a entrega interna, desde que a aplicação principal esteja estável e o professor considere essa infraestrutura compatível com o requisito de monólito.

## 15. Organização da preparação e do importador

As regras deverão existir em serviços internos reutilizáveis do mesmo monólito:

```text
PrepareHistoricalWindowService     ImportSnapshotService
              ↑                             ↑
management command de preparação   management command de importação
```

Benefícios:

- arquitetura integralmente monolítica;
- execução e depuração direta pelo terminal;
- testes mais simples;
- separação entre regra de negócio e infraestrutura;
- possibilidade de adicionar uma fila futuramente sem reescrever a regra central.

O disparo manual não autoriza edição manual de linhas. Dadas as mesmas fontes, configuração e versão das regras, a preparação deverá produzir o mesmo resultado lógico.

Requisitos de confiabilidade:

- chave idempotente formada por região, competência e hash dos arquivos;
- correção explícita e atômica para hash diferente da mesma competência;
- preservação da revisão anterior como substituída;
- recálculo das métricas da competência e dos eventos dos intervalos adjacentes;
- validação de que janela, coorte, recorte e versão são compatíveis entre os 13 pacotes;
- concorrência de importação igual a um;
- processamento em lotes com consumo limitado de memória;
- transações e falha controlada;
- publicação atômica somente após validação integral;
- proibição de comparar ou publicar através de lacunas;
- falha do pacote em erros estruturais ou sistêmicos;
- publicação com alertas quando ocorrências localizadas puderem ser isoladas e auditadas;
- bloqueio desde a primeira ocorrência para hash inválido, arquivo ou coluna obrigatória ausente, competência incompatível, identidade nula ou duplicada e mapeamento regional impossível;
- escalada de cada regra de alerta quando `affected_rows` superar seu limite versionado: `max(10, ceil(eligible_rows × 0,001))` na regra geral e `max(10, ceil(eligible_rows × 0,005))` para `LATE_FIRST_SEEN`;
- registro periódico da quantidade processada;
- publicação dos eventos somente após uma importação válida.

Abaixo ou no limite de escalada, a competência poderá assumir `PUBLISHED_WITH_WARNINGS`, e somente as entidades afetadas terão a comparação suspensa. Acima do limite, assumirá `FAILED_QUALITY_GATE` até investigação e nova revisão. A medição das 13 competências calibrou `LATE_FIRST_SEEN` em 0,50%; as demais regras mantêm 0,10%. Qualquer ajuste futuro deverá ser documentado, versionado e aplicado a toda a janela, nunca a uma competência isolada.

## 16. Escopo do MVP

### Incluído

- 13 competências, de agosto de 2025 a agosto de 2026;
- recorte regional;
- empresas em todas as situações cadastrais;
- sócios PF e PJ com minimização de dados;
- preparação automatizada da janela histórica;
- importação manual por management command;
- dashboard regional;
- pesquisa e detalhes da empresa;
- linha do tempo de alterações;
- lista de monitoramento;
- autenticação;
- testes das regras críticas;
- execução local.

### Fora do MVP

- ingestão nacional completa;
- atualização em tempo real;
- cron, Celery, RabbitMQ e Celery Beat;
- frontend separado em SPA e API;
- AngularJS;
- envio de e-mail, SMS ou WhatsApp;
- aplicação móvel nativa;
- API pública;
- cobrança e assinaturas;
- score de crédito ou de risco;
- inteligência artificial;
- consulta de CPF;
- busca por nome de pessoa física;
- dados judiciais, financeiros ou de bureaus de crédito;
- integração com sistemas corporativos externos;
- deploy em produção.

## 17. Diferenciais acadêmicos

O projeto permitirá demonstrar:

- uso de dados públicos reais;
- ETL e processamento em lotes;
- modelagem temporal;
- algoritmos de comparação;
- geração de eventos;
- arquitetura monolítica organizada em camadas;
- idempotência;
- rastreabilidade e proveniência dos dados;
- privacidade por design;
- visualização de dados regionais;
- testes automatizados e evidências de testes manuais;
- rastreabilidade entre backlog, critérios de aceite, testes e entregas;
- arquitetura preparada para evolução futura.

## 18. Riscos e mitigação

### Volume maior que o estimado

**Mitigação:** medir a primeira competência, reduzir campos, limitar municípios e manter arquivos compactados.

### Falta de alterações interessantes na demonstração

**Mitigação:** utilizar as 13 competências aprovadas, validar previamente a quantidade de eventos e preparar empresas reais com histórico representativo.

### Primeira competência interpretada como abertura em massa

**Mitigação:** tratar `2025-08` como baseline sem eventos e exigir data de início compatível nas competências seguintes.

### Ausência interpretada como alteração cadastral

**Mitigação:** manter ocorrências de qualidade separadas dos eventos de negócio e exigir evidência explícita de baixa ou nova localização.

### Falsos eventos societários

**Mitigação:** normalização consistente, identificador interno, comparação por empresa e registro das limitações do CPF mascarado.

### Exposição indevida de dados pessoais

**Mitigação:** minimização, ausência de busca por pessoa, descarte do CPF mascarado, controle de acesso e revisão dos logs.

### Complexidade do Celery e RabbitMQ

Celery e RabbitMQ foram retirados do MVP. Uma eventual adoção futura dependerá de valor demonstrável e alinhamento com o requisito acadêmico de aplicação monolítica.

### Prazo agressivo para o MVP interno

**Mitigação:** sprints semanais, priorização rigorosa do escopo P0, demonstração integrada desde cedo e transferência de itens P1 para o período de refinamento quando necessário.

### Sobrecarga e concentração de conhecimento

**Mitigação:** definir responsáveis principais sem criar exclusividade, revisar código em dupla, documentar decisões e garantir que pelo menos duas pessoas conheçam cada fluxo crítico.

### Dependência de ativos profissionais

**Mitigação:** usar somente dados públicos e código desenvolvido especificamente para o projeto, salvo autorização expressa.

## 19. Critérios de sucesso da entrega oficial

O critério específico do MVP interno de 30 de setembro está na seção 22. Para a entrega acadêmica oficial, o produto será considerado funcional quando:

1. Importar as 13 competências reais de agosto de 2025 a agosto de 2026.
2. Rejeitar arquivos inválidos ou importações duplicadas.
3. Impedir publicação parcial e comparações através de competências ausentes.
4. Pesquisar empresas reais do recorte regional.
5. Exibir os dados atuais e a competência da fonte.
6. Gerar corretamente os eventos entre meses.
7. Registrar ausências como ocorrências de qualidade sem produzir encerramentos ou saídas regionais falsas.
8. Não gerar eventos no baseline e somente classificar abertura com evidência temporal.
9. Exibir uma linha do tempo com antes e depois.
10. Permitir acompanhar empresas em uma watchlist.
11. Apresentar indicadores regionais ao longo do período.
12. Processar uma competência pelo management command, registrar o resultado e impedir duplicações.
13. Não expor CPF completo ou mascarado na interface, APIs ou logs.

## 20. Equipe, papéis e responsabilidades

Os papéis indicam responsabilidade principal, mas não criam exclusividade. A equipe continuará colaborando, revisando entregas e compartilhando conhecimento.

### Tiago — Product Owner, Tech Lead e desenvolvedor full stack

Como **Product Owner**:

- manter e priorizar o Product Backlog;
- esclarecer as necessidades do usuário e o valor de cada funcionalidade;
- definir critérios de aceite;
- aceitar ou solicitar ajustes nas entregas;
- proteger o escopo P0 e decidir o que será adiado.

Como **Tech Lead e desenvolvedor**:

- definir arquitetura, padrões técnicos e modelo de dados;
- liderar importação, comparação temporal e geração de eventos;
- desenvolver prioritariamente backend e integrações;
- apoiar o frontend e revisar pull requests;
- remover bloqueios técnicos e garantir a integração do monólito.

### Gabriel — QA Lead e responsável por pesquisa e validação

Como **responsável por pesquisa**:

- pesquisar fontes públicas, soluções semelhantes e necessidades dos usuários;
- avaliar disponibilidade, qualidade, periodicidade e limitações dos dados;
- apoiar a análise de viabilidade das melhorias propostas;
- documentar referências, achados, riscos e hipóteses que precisem de validação.

Como **QA Lead**:

- elaborar o plano e os casos de teste;
- manter a matriz de rastreabilidade entre requisito, critério de aceite e teste;
- executar testes funcionais, de integração, regressão e aceitação;
- registrar evidências, defeitos encontrados e resultados;
- validar a versão candidata a cada entrega.

Gabriel não será o único responsável pela qualidade: cada desenvolvedor testará o próprio trabalho, e Tiago revisará os fluxos críticos para reduzir o conflito entre desenvolver e homologar.

### Emili — Scrum Master e coordenadora de documentação

Como **Scrum Master**:

- organizar as cerimônias e registrar atas e decisões;
- manter o quadro do Miro organizado e atualizado;
- acompanhar impedimentos, responsáveis e prazos;
- cobrar a atualização das tarefas e facilitar a comunicação;
- conduzir retrospectivas e acompanhar ações de melhoria.

Como **coordenadora de documentação**:

- organizar a documentação acadêmica e as evidências produzidas pela equipe;
- consolidar atas, decisões, requisitos e entregáveis do projeto;
- manter os documentos coerentes com o quadro do Miro e o estado das tarefas;
- apoiar o QA no registro dos testes e na validação visual.

### Novo integrante — Designer de Produto (UI/UX) e Product Discovery

Como **responsável por UI/UX e descoberta de produto**:

- conversar com potenciais usuários e aproveitar sua experiência diária com clientes para levantar
  dores, vocabulário, expectativas e oportunidades;
- transformar os achados em personas, jornadas, fluxos e hipóteses de melhoria;
- criar wireframes, protótipos e especificações de comportamento das telas;
- definir com o grupo identidade visual, logo, paleta, tipografia e componentes reutilizáveis;
- avaliar usabilidade, clareza, consistência, responsividade e acessibilidade;
- validar protótipos antes do desenvolvimento e registrar os resultados;
- propor melhorias ao Product Backlog, mantendo a priorização e o aceite sob responsabilidade do
  Product Owner.

### Responsabilidades compartilhadas

- estimar e atualizar as tarefas sob sua responsabilidade;
- participar de planejamento, revisão e retrospectiva;
- documentar decisões relevantes;
- revisar os critérios de aceite antes do desenvolvimento;
- apresentar o projeto e conhecer seu fluxo principal.

A distribuição deverá ser validada pelos quatro integrantes e poderá ser ajustada conforme disponibilidade, aprendizado e carga de trabalho. O objetivo é dar autonomia e entregas concretas a todos, sem concentrar o projeto inteiro em uma única pessoa.

## 21. Processo de trabalho: Scrum adaptado e Miro

Será utilizado um Scrum adaptado ao calendário acadêmico e ao tamanho da equipe. O Miro concentrará o quadro de trabalho, os artefatos de UX, as decisões e os links para documentos e evidências.

### Estrutura do quadro

- Product Backlog;
- Sprint Backlog;
- A Fazer;
- Em Desenvolvimento;
- Em Revisão;
- Em Teste;
- Concluído;
- Bloqueado.

Cada cartão deverá conter:

- identificador e história de usuário ou tarefa;
- prioridade P0, P1 ou P2;
- responsável;
- estimativa;
- critérios de aceite;
- dependências;
- link para documento, código, teste ou evidência.

### Cerimônias

- **Sprint Planning:** semanal, com 30 a 45 minutos;
- **Daily:** atualização assíncrona no Miro ou reunião de até 10 minutos;
- **Sprint Review:** semanal, com demonstração do incremento;
- **Retrospectiva:** semanal, após a review, com uma ação de melhoria para a sprint seguinte.

### Artefatos acadêmicos

- visão e escopo do produto;
- Product Backlog e Sprint Backlogs;
- atas de reunião e registro de decisões;
- personas e fluxos de usuário;
- wireframes, identidade visual e protótipo navegável;
- requisitos e critérios de aceite;
- plano, casos, evidências e relatório de testes;
- manual de execução e documentação técnica;
- apresentação final.

### Definition of Done

Uma tarefa somente poderá ser movida para **Concluído** quando:

- os critérios de aceite forem atendidos;
- o código estiver integrado e revisado;
- os testes aplicáveis tiverem sido executados;
- não houver defeito crítico conhecido;
- a evidência e a documentação relacionadas estiverem atualizadas;
- a funcionalidade puder ser demonstrada no ambiente local.

## 22. Priorização do MVP

### P0 — obrigatório para o MVP interno

- 13 competências preparadas, validadas e importadas;
- pesquisa por CNPJ, razão social e nome fantasia;
- página de empresa com seus estabelecimentos e quadro societário;
- comparação entre competências e geração dos eventos;
- dez eventos P0 de estabelecimento, empresa e sociedade;
- linha do tempo de alterações;
- dashboard regional com filtros por competência, município e CNAE;
- tela administrativa de lotes, revisões e alertas;
- preparação e importação reproduzíveis por management commands;
- testes unitários das regras críticas, integração do importador e roteiro manual de aceitação documentado;
- execução local completa por Docker Compose;
- ausência de erro fatal conhecido e alertas limitados pela regra de qualidade aprovada.

### P1 — outubro e entrega oficial de novembro

- cinco eventos P1 cadastrais e societários;
- autenticação;
- watchlist;
- filtros avançados;
- gráficos e indicadores adicionais;
- refinamentos visuais, de responsividade e acessibilidade;
- ampliação dos testes;
- correções encontradas na homologação;
- documentação e apresentação acadêmica finais.

Os cinco eventos P1 cadastrais e societários são obrigatórios para a entrega oficial de novembro, mas não bloqueiam o MVP interno de setembro. Autenticação e watchlist permanecem no escopo funcional oficial, porém também não bloqueiam essa meta interna executada em localhost.

O MVP interno somente será declarado concluído quando todos os itens P0 estiverem demonstráveis. Se qualquer um faltar em 30 de setembro, a entrega será registrada como versão parcial. Itens P1 poderão ser antecipados, mas não compensarão a ausência de um P0.

## 23. Cronograma e marcos

### Sprint 0 — 22 a 28 de agosto

- aprovar proposta, papéis e processo de trabalho;
- criar e organizar o Miro;
- fechar o escopo P0 e validar a correspondência dos códigos municipais;
- definir o contrato dos extratos regionais;
- obter e medir uma competência real;
- criar wireframes de baixa fidelidade;
- iniciar o projeto Django e o ambiente local.

### Sprint 1 — 29 de agosto a 4 de setembro

- implementar autenticação e estrutura visual básica;
- criar o modelo inicial de dados e as migrações;
- implementar o primeiro fluxo de importação;
- importar uma competência real;
- iniciar plano e casos de teste.

### Sprint 2 — 5 a 11 de setembro

- consolidar a importação das 13 competências;
- implementar comparação e geração dos eventos prioritários;
- criar testes unitários e de integração do importador;
- finalizar o protótipo navegável e a identidade visual inicial.

### Sprint 3 — 12 a 18 de setembro

- implementar pesquisa e filtros básicos;
- implementar detalhe da empresa e quadro societário;
- implementar linha do tempo com antes e depois;
- executar testes funcionais dos fluxos entregues.

### Sprint 4 — 19 a 25 de setembro

- implementar dashboard regional básico;
- implementar watchlist se o P0 estiver estável;
- integrar e revisar os fluxos de ponta a ponta;
- corrigir problemas de UX, desempenho e acessibilidade.

### Sprint 5 — 26 a 30 de setembro

- congelar novas funcionalidades;
- executar regressão e corrigir defeitos críticos;
- revisar privacidade e logs;
- preparar dados de demonstração;
- publicar a versão do **MVP interno em 30 de setembro de 2026**.

### Outubro — refinamento e validação

- coletar feedback sobre o MVP interno;
- corrigir defeitos e débitos técnicos;
- concluir itens P1 de maior valor;
- melhorar interface, desempenho e cobertura de testes;
- carregar ou revisar as 13 competências;
- consolidar documentação técnica, acadêmica e evidências.

### Novembro — entrega acadêmica oficial

- estabilizar a versão final;
- executar testes de aceitação e regressão final;
- revisar todos os artefatos exigidos pelo professor;
- preparar apresentação, roteiro e demonstração;
- realizar ensaios e entregar na data oficial definida pela instituição.

## 24. Decisões ainda pendentes

- nome do produto;
- identidade visual, logo e paleta de cores;
- personas prioritárias para validação;
- indicadores finais do dashboard;
- data exata da entrega acadêmica em novembro.

## 25. Próximos passos

1. Fechar a matriz de aceite, preservando como pendentes os cenários ainda não exercitados.
2. Obter a revisão de pesquisa e QA de Gabriel, a revisão documental de Emili, a revisão de UI/UX do novo integrante e a validação acadêmica do professor.
3. Criar no Miro os cards remanescentes, com responsáveis, evidências e critérios de aceite.
4. Desenvolver a identidade visual do Rastro PJ, logo, paleta, personas e protótipo definitivo.
5. Executar a limpeza manual aprovada das fontes nacionais temporárias depois de confirmar retenção e redownload.
6. Corrigir os defeitos encontrados na homologação sem alterar silenciosamente domínio, privacidade ou janela.
7. Congelar a candidata acadêmica, consolidar evidências e ensaiar a demonstração de novembro.

## 26. Referências iniciais

- [Receita Federal — Layout dos dados abertos do CNPJ](https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf)
- [Receita Federal — Cadastros e dados abertos](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/cadastros)
- [Estatísticas CNPJ — Redesim](https://estatistica.redesim.gov.br/situacao-cnpj)
- [Lei Geral de Proteção de Dados Pessoais](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm)
- [ANPD — Perguntas frequentes](https://www.gov.br/anpd/pt-br/acesso-a-informacao/perguntas-frequentes/perguntas-frequentes)
- [Django — Templates](https://docs.djangoproject.com/en/5.2/topics/templates/)
- [Django — Arquivos estáticos](https://docs.djangoproject.com/en/5.2/howto/static-files/)
- [Django — Custom management commands](https://docs.djangoproject.com/en/5.2/howto/custom-management-commands/)
- [AngularJS — encerramento do suporte oficial](https://github.com/angular/angular.js#angularjs)
- [Scrum Guide — guia oficial](https://scrumguides.org/scrum-guide.html)
- [Miro — Scrum Board](https://miro.com/agile/scrum-board/)
