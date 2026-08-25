# Backend CNPJ Regional — registro de decisões

**Estado:** refinamento concluído e validado pelo Product Owner  
**Responsável pela validação de produto:** Tiago, Product Owner  
**Revisores:** Gabriel, Emili e professor orientador  
**Última atualização:** 24 de agosto de 2026
**Consolidação:** [`backend-cnpj-regional-validacao-arquitetural.md`](backend-cnpj-regional-validacao-arquitetural.md)

## Evidências verificadas

- O CSV localizado em `/Users/tiagomonteiro/Downloads/triangulo_mineiro_35_municipios_ibge.csv` contém 35 municípios, 35 códigos distintos e nenhuma duplicidade de nome ou código.
- Os 35 códigos e nomes do CSV foram encontrados sem divergência na relação oficial de municípios de Minas Gerais do IBGE em 24 de agosto de 2026.
- A tabela oficial TOM da Receita Federal forneceu correspondência única para os 35 códigos IBGE. O layout do CNPJ representa o município do estabelecimento pelo código TOM de quatro dígitos; Delta usa `0602` e União de Minas usa `0742`, confirmando que zeros iniciais são significativos.
- Em 23 de agosto de 2026, o repositório público consultado continha competências de `2025-08` a `2026-08`.
- A competência pública `2026-08` possui 37 arquivos e aproximadamente 7,16 GiB compactados. O pipeline profissional de referência exige por padrão 200 GiB livres para processar uma competência nacional, evidenciando que a aquisição bruta não deve ser tratada como uma operação comum da aplicação local.
- O pipeline de referência processa empresas, estabelecimentos, Simples, sócios e tabelas de domínio, mas pertence a outro contexto e não autoriza reutilização de código, credenciais ou dados internos.

## Decisões confirmadas

### 1. Um ano completo exige 13 fotografias mensais

- **Evidência:** o intervalo inclusivo de agosto de 2025 a agosto de 2026 contém 13 competências.
- **Resultado escolhido:** importar as 13 competências de `2025-08` a `2026-08` e comparar cada par consecutivo.
- **Consequência de negócio:** o produto mostrará 12 meses completos de evolução, inclusive a comparação entre agosto de 2025 e agosto de 2026.
- **Consequência técnica:** o backend deverá representar 13 fotografias e produzir 12 intervalos de comparação.
- **Risco evitado:** anunciar um ano de evolução utilizando somente 11 comparações mensais.
- **Alternativa considerada:** importar exatamente 12 competências, de `2025-09` a `2026-08`.
- **Motivo da rejeição:** essa alternativa produziria somente 11 intervalos e excluiria agosto de 2025.
- **Trade-off:** aproximadamente 8% a mais de carga histórica em relação a 12 competências.
- **Responsável:** Tiago, Product Owner.
- **Estado:** aprovado em 23 de agosto de 2026.

### 2. O MVP representa os 35 municípios do Triângulo Mineiro

- **Evidência:** o arquivo recebido contém 35 municípios distintos; trocar quatro por 35 altera principalmente o volume, não a regra funcional de filtragem regional.
- **Resultado escolhido:** adotar os 35 municípios como recorte oficial e usar Uberlândia, Uberaba, Araguari e Ituiutaba somente como amostra técnica durante desenvolvimento e testes rápidos.
- **Consequência de negócio:** indicadores e consultas do MVP representarão o recorte regional completo aprovado, e não apenas seus quatro maiores centros.
- **Consequência técnica:** o recorte deverá ser configurável a partir de uma referência validada; a lista não poderá ficar replicada nas regras do backend.
- **Risco evitado:** apresentar uma amostra de quatro cidades como se representasse todo o Triângulo Mineiro.
- **Alternativa considerada:** limitar o produto às quatro cidades inicialmente propostas.
- **Motivo da rejeição:** a redução enfraqueceria a proposta regional sem reduzir de forma equivalente a complexidade do software.
- **Trade-off:** mais registros, maior duração de importação e necessidade de medir o consumo real antes da carga integral.
- **Responsável:** Tiago, Product Owner.
- **Estado:** aprovado em 23 de agosto de 2026.

### 3. A presença regional nasce em qualquer estabelecimento, não apenas na matriz

- **Evidência:** município, endereço, situação cadastral e CNAE pertencem ao registro de estabelecimento; o registro de empresa identificado pelo CNPJ básico não determina sozinho onde há atuação regional.
- **Resultado escolhido:** considerar uma empresa presente na região quando qualquer matriz ou filial possuir endereço em um dos 35 municípios em ao menos uma das 13 competências.
- **Consequência de negócio:** filiais de empresas com matriz externa participarão da consulta e dos indicadores regionais.
- **Consequência técnica:** a seleção começará pelos estabelecimentos e seus CNPJs completos; os CNPJs básicos resultantes determinarão as empresas e os quadros societários necessários. Outras filiais externas não entrarão automaticamente.
- **Risco evitado:** excluir atividade econômica local de bancos, redes comerciais, fornecedores e outras organizações sediadas fora da região.
- **Alternativa considerada:** incluir somente empresas cuja matriz esteja em um dos 35 municípios.
- **Motivo da rejeição:** sede jurídica e presença econômica regional representam conceitos diferentes.
- **Trade-off:** a interface e os indicadores precisarão distinguir contagens de empresas e de estabelecimentos.
- **Responsável:** Tiago, Product Owner.
- **Estado:** aprovado em 24 de agosto de 2026.

### 4. O histórico acompanha o estabelecimento através da fronteira regional

- **Evidência:** filtrar cada competência isoladamente faria um estabelecimento que mudou de Uberlândia para Goiânia desaparecer do extrato sem explicar a causa.
- **Resultado escolhido:** formar a coorte com todos os CNPJs completos que possuam ao menos uma ocorrência regional e preservar suas fotografias nas 13 competências, inclusive quando estiverem fora do recorte.
- **Consequência de negócio:** o produto distinguirá entrada regional, saída regional e alteração de endereço de uma baixa ou ausência de dados.
- **Consequência técnica:** a extração terá duas etapas: descobrir a união dos CNPJs completos regionais e recuperar o histórico desses CNPJs em todas as competências. Métricas regionais usarão apenas ocorrências localizadas nos 35 municípios.
- **Risco evitado:** emitir conclusões cadastrais falsas a partir do simples desaparecimento de uma linha filtrada.
- **Alternativa considerada:** aplicar o filtro municipal independentemente em cada competência.
- **Motivo da rejeição:** a alternativa perde a continuidade histórica justamente nas movimentações de entrada e saída da região.
- **Trade-off:** duas passagens sobre as fontes e armazenamento de algumas fotografias externas adicionais.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 5. O município conserva a identidade IBGE e traduz o código da Receita

- **Evidência:** o arquivo recebido e a lista oficial do IBGE usam códigos de sete dígitos; os estabelecimentos do CNPJ usam códigos TOM de quatro dígitos. A Receita publica uma correspondência oficial entre ambos.
- **Resultado escolhido:** adotar o código IBGE textual como identidade canônica do município e manter o código TOM textual como identificador da fonte da Receita.
- **Consequência de negócio:** filtros, documentação e futuras integrações reconhecerão o município por um código público amplamente compreendido.
- **Consequência técnica:** a referência versionada deverá conter código IBGE, código TOM, nome e UF; ambos os códigos serão texto, e o importador rejeitará ausências, duplicidades ou UF diferente de MG.
- **Risco evitado:** perder zeros iniciais, relacionar por nomes ambíguos ou acoplar a identidade do domínio a um código específico da fonte CNPJ.
- **Alternativa considerada:** usar o código TOM como identidade principal do município.
- **Motivo da rejeição:** simplificaria o filtro de origem, mas reduziria interoperabilidade e clareza fora dos sistemas da Receita.
- **Trade-off:** manutenção explícita de uma tabela de correspondência versionada.
- **Responsável:** Tiago, Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 6. A preparação nacional e a importação regional são estágios do mesmo monólito

- **Evidência:** uma competência nacional possui aproximadamente 7,16 GiB compactados e o pipeline profissional de referência reserva 200 GiB livres; tratar 13 bases nacionais como operação comum da aplicação local ameaçaria prazo e recursos.
- **Resultado escolhido:** separar o ETL em preparação da janela histórica e importação das competências, ambos automatizados, iniciados manualmente e mantidos no mesmo projeto monolítico.
- **Consequência de negócio:** o usuário da aplicação trabalhará com dados regionais reais sem precisar operar a base nacional.
- **Consequência técnica:** um comando preparará a coorte e os pacotes regionais; outro validará e carregará cada pacote no PostgreSQL, gerando histórico, eventos e métricas.
- **Risco evitado:** bloquear a entrega do produto com download e tratamento nacional acoplados à interface web ou depender de infraestrutura profissional.
- **Alternativa considerada:** fazer a aplicação restaurar ou processar diretamente cada base nacional durante a importação funcional.
- **Motivo da rejeição:** mistura aquisição pesada com o ciclo operacional do produto e torna falhas, testes e reprocessamentos mais caros.
- **Trade-off:** existência de uma fronteira de arquivos intermediários e dois comandos operacionais documentados.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 7. Cada competência viaja em um pacote imutável da mesma janela

- **Evidência:** as competências são importadas e comparadas individualmente; um artefato único tornaria qualquer correção dependente da regeneração e revalidação de toda a janela.
- **Resultado escolhido:** gerar 13 pacotes imutáveis, um por competência, ligados por um manifesto da janela histórica.
- **Consequência de negócio:** uma competência poderá ser auditada, corrigida e reapresentada sem ocultar a identidade das demais.
- **Consequência técnica:** o manifesto declarará período, competências, coorte, recorte, versões e hashes; cada pacote declarará competência, arquivos, contagens, hashes e origem.
- **Risco evitado:** reprocessar silenciosamente toda a janela para corrigir um único mês ou misturar pacotes produzidos com coortes diferentes.
- **Alternativa considerada:** gerar um único pacote contendo as 13 competências.
- **Motivo da rejeição:** simplifica o transporte, mas aumenta impacto de falhas e custo de validação, repetição e auditoria.
- **Trade-off:** mais manifestos e validações de consistência entre artefatos.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 8. Empresa e estabelecimento possuem ciclos de vida distintos

- **Evidência:** situação cadastral, abertura, baixa, endereço e CNAE pertencem ao CNPJ completo do estabelecimento; razão social, natureza jurídica, capital, porte e sócios pertencem ao CNPJ básico da empresa.
- **Resultado escolhido:** separar proprietários, eventos e indicadores de empresa dos de estabelecimento e retirar `COMPANY_CREATED` e `COMPANY_CLOSED` do MVP.
- **Consequência de negócio:** a baixa de uma filial será apresentada como encerramento de um estabelecimento, sem afirmar que toda a empresa deixou de existir.
- **Consequência técnica:** eventos carregarão o tipo e a identidade da entidade afetada; métricas de abertura, baixa e situação contarão estabelecimentos, enquanto totais corporativos contarão CNPJs básicos distintos.
- **Risco evitado:** produzir indicadores inflados ou alegações cadastrais incorretas ao tratar matriz, filial e empresa como a mesma entidade.
- **Alternativa considerada:** simplificar todos os eventos e indicadores sob o conceito genérico de empresa.
- **Motivo da rejeição:** a simplificação contraria a estrutura e a semântica da fonte oficial.
- **Trade-off:** mais clareza de nomes, filtros e relacionamentos no domínio, ao custo de uma interface ligeiramente mais detalhada.
- **Responsável:** Tiago, Product Owner.
- **Estado:** aprovado em 24 de agosto de 2026.

### 9. Uma competência oficial precisa ser íntegra e consecutiva

- **Evidência:** comparar dezembro diretamente com fevereiro após falha de janeiro atribuiria mudanças de dois intervalos a uma única competência e quebraria a janela aprovada.
- **Resultado escolhido:** validar e publicar cada competência atomicamente e proibir comparações ou publicações que atravessem uma lacuna histórica.
- **Consequência de negócio:** cada evento continuará relacionado a um intervalo mensal conhecido, sem ocultar meses ausentes ou cargas parciais.
- **Consequência técnica:** pacotes passarão por recebimento, validação e staging antes da publicação; uma competência posterior poderá aguardar preparada, mas não se tornará oficial antes das anteriores.
- **Risco evitado:** snapshots parciais, métricas inconsistentes e eventos atribuídos ao mês errado.
- **Alternativa considerada:** aceitar cargas parciais ou comparar a última competência válida diretamente com a próxima disponível.
- **Motivo da rejeição:** a flexibilidade operacional comprometeria a principal promessa temporal do produto.
- **Trade-off:** um pacote inválido bloqueia a publicação das competências posteriores até ser corrigido.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 10. Ausência cadastral não prova encerramento ou saída regional

- **Evidência:** um CNPJ ausente pode resultar de falha de fonte, extração, coorte ou correção cadastral; a ausência não informa situação nem nova localização.
- **Resultado escolhido:** tratar ausência de empresa ou estabelecimento como ocorrência de qualidade de dados, sem gerar evento cadastral.
- **Consequência de negócio:** o produto somente afirmará encerramento ou saída regional quando houver evidência explícita na fotografia posterior.
- **Consequência técnica:** `ESTABLISHMENT_CLOSED` exigirá transição para situação baixada; `LEFT_REGION` exigirá localização posterior fora do recorte; comparações individuais serão suspensas durante ausência.
- **Risco evitado:** alegar falsamente que uma empresa encerrou, uma filial foi baixada ou um estabelecimento deixou a região.
- **Alternativa considerada:** inferir baixa ou saída quando o registro desaparecer entre competências.
- **Motivo da rejeição:** transforma incerteza da fonte em afirmação de negócio sem evidência.
- **Trade-off:** algumas linhas do tempo terão lacunas explícitas e menos eventos, privilegiando precisão sobre completude aparente.
- **Responsável:** Tiago, Product Owner.
- **Estado:** aprovado em 24 de agosto de 2026.

### 11. Falhas sistêmicas bloqueiam; ocorrências isoladas permanecem visíveis

- **Evidência:** bloquear 13 competências por causa de um único registro problemático é operacionalmente frágil, enquanto publicar arquivos, hashes ou identidades estruturalmente inválidos compromete toda a fotografia.
- **Resultado escolhido:** classificar inconsistências como erro fatal de competência ou alerta de qualidade localizado.
- **Consequência de negócio:** dados não afetados continuarão disponíveis, mas a interface e a auditoria indicarão explicitamente competências e entidades com alertas.
- **Consequência técnica:** erros estruturais produzirão `FAILED`; alertas isolados permitirão `PUBLISHED_WITH_WARNINGS`, criarão `DataQualityIssue` e suspenderão somente comparações afetadas.
- **Risco evitado:** tanto a paralisação desnecessária da janela quanto a publicação silenciosa de corrupção sistêmica.
- **Alternativa considerada:** bloquear a competência diante de qualquer inconsistência, independentemente de alcance.
- **Motivo da rejeição:** confunde anomalia localizada com perda de integridade do pacote inteiro.
- **Trade-off:** classificação explícita de severidade e necessidade de calibrar, com dados reais, o limite que transforma muitos alertas em falha sistêmica.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 12. As tabelas preservam tipos em Parquet e os manifestos permanecem legíveis em JSON

- **Evidência:** CNPJ, IBGE e TOM precisam preservar zeros; o volume histórico favorece compressão e leitura seletiva; CSV introduz ambiguidades de encoding, delimitadores e tipos.
- **Resultado escolhido:** usar Parquet como formato canônico das tabelas e JSON UTF-8 como formato dos manifestos.
- **Consequência de negócio:** os pacotes serão menores e mais consistentes, enquanto origem, contagens, hashes e alertas permanecerão facilmente auditáveis no manifesto.
- **Consequência técnica:** o contrato fixará tipos explícitos e hashes SHA-256; códigos permanecerão texto e relatórios pequenos poderão ser exportados para QA sem se tornarem fonte canônica.
- **Risco evitado:** perda de zeros, datas ambíguas, erros de separador e cargas com inferência de tipos diferente entre competências.
- **Alternativa considerada:** tabelas em CSV compactado com gzip.
- **Motivo da rejeição:** é mais familiar, mas transfere complexidade e risco para cada leitura e validação do pacote.
- **Trade-off:** Parquet exige leitor próprio e não é inspecionável diretamente em editor de texto.
- **Responsável:** Tiago, Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 13. O CPF mascarado termina na preparação e não atravessa o pacote

- **Evidência:** o CPF mascarado continua sendo dado pessoal pseudonimizado; levá-lo aos pacotes multiplicaria cópias acessíveis a desenvolvimento, QA e apresentação sem necessidade funcional.
- **Resultado escolhido:** gerar durante a preparação uma identidade societária PF por HMAC restrita à empresa e eliminar o CPF mascarado antes da geração do Parquet.
- **Consequência de negócio:** o produto continuará detectando mudanças no quadro societário dentro da empresa sem oferecer pesquisa, grafo ou correlação global de pessoas.
- **Consequência técnica:** a chave usará segredo externo, CNPJ básico, tipo PF, CPF mascarado e nome normalizado; qualificação e data de entrada permanecerão atributos comparáveis, não componentes da identidade.
- **Risco evitado:** exposição do CPF mascarado em pacotes, logs, testes, relatórios ou cópias de trabalho e criação acidental de identidade global.
- **Alternativa considerada:** transportar o CPF mascarado nos pacotes e pseudonimizá-lo apenas na importação.
- **Motivo da rejeição:** aumenta a superfície de dados pessoais sem gerar valor para o backend funcional.
- **Trade-off:** mudança de segredo ou regra exige regeneração dos pacotes; correção de nome pode aparecer como remoção e inclusão; não há correlação automática entre empresas.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 14. O baseline não fabrica eventos e abertura exige evidência temporal

- **Evidência:** todos os estabelecimentos existentes aparecem pela primeira vez para o produto em `2025-08`, embora muitos tenham iniciado atividades anos antes.
- **Resultado escolhido:** usar a primeira competência como baseline sem eventos e gerar `ESTABLISHMENT_OPENED` posteriormente somente quando ausência anterior, primeira aparição e data de início forem coerentes com o intervalo consecutivo.
- **Consequência de negócio:** o dashboard não apresentará empresas antigas como aberturas recentes e distinguirá abertura de entrada na região.
- **Consequência técnica:** primeira aparição com data antiga ou incompatível produzirá alerta `LATE_FIRST_SEEN`; existência externa anterior seguida de ocorrência regional produzirá `ENTERED_REGION`.
- **Risco evitado:** inflação artificial de eventos na primeira competência e afirmações falsas de abertura.
- **Alternativa considerada:** interpretar qualquer primeira aparição na janela como abertura.
- **Motivo da rejeição:** confunde início da observação com início da atividade.
- **Trade-off:** o baseline não terá timeline de alterações e algumas aparições posteriores serão alertas, não eventos.
- **Responsável:** Tiago, Product Owner.
- **Estado:** aprovado em 24 de agosto de 2026.

### 15. O evento mais específico representa cada dimensão alterada

- **Evidência:** uma transição de ativa para baixada satisfaz simultaneamente uma mudança genérica de situação e um encerramento específico; publicar ambos duplicaria um único fato.
- **Resultado escolhido:** emitir somente o evento primário mais específico por entidade, dimensão e intervalo, mantendo eventos separados para dimensões independentes.
- **Consequência de negócio:** timeline e indicadores representarão cada fato uma vez, sem esconder mudanças independentes ocorridas na mesma competência.
- **Consequência técnica:** `ESTABLISHMENT_CLOSED` substitui mudança genérica para baixada; entrada ou saída regional substitui mudança de endereço na mesma transição; abertura confirmada não gera diferenças contra uma fotografia inexistente.
- **Risco evitado:** duplicação de eventos, contagens infladas e timeline repetitiva.
- **Alternativa considerada:** emitir todo evento técnico cujas condições sejam satisfeitas.
- **Motivo da rejeição:** transforma classificações sobrepostas do mesmo fato em mudanças distintas para o usuário.
- **Trade-off:** o comparador precisa de regras explícitas de precedência por dimensão.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 16. Fotografias completas sustentam eventos recalculáveis

- **Evidência:** auditoria, lacunas individuais e correção das regras de comparação exigem conhecer os estados anterior e posterior sem depender do evento já produzido.
- **Resultado escolhido:** persistir no PostgreSQL fotografias normalizadas completas por entidade e competência publicada e tratar eventos como dados derivados e recalculáveis.
- **Consequência de negócio:** a timeline poderá ser explicada pelo antes e depois e corrigida sem perder a evidência cadastral que a originou.
- **Consequência técnica:** haverá fotografias separadas de empresa, estabelecimento e participação societária; o estado atual será consultado na competência publicada mais recente, sem tabela duplicada independente.
- **Risco evitado:** tornar eventos a única prova histórica ou permitir divergência entre uma tabela de estado atual e os snapshots.
- **Alternativa considerada:** guardar apenas estado atual e eventos, ou compactar mudanças em intervalos SCD Type 2.
- **Motivo da rejeição:** a primeira perde evidência para recálculo; a segunda adiciona complexidade desproporcional à janela fixa de 13 competências.
- **Trade-off:** repetição de atributos inalterados e maior consumo de PostgreSQL.
- **Responsável:** Tiago, Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 17. Correções criam revisões e nunca sobrescrevem silenciosamente

- **Evidência:** reimportar a mesma competência após corrigir dados ou preparação pode alterar fotografias, métricas e os dois intervalos de eventos adjacentes.
- **Resultado escolhido:** tratar o mesmo hash como operação idempotente e exigir uma revisão explícita, versionada e atômica quando o hash da mesma competência mudar.
- **Consequência de negócio:** correções serão rastreáveis e não interromperão a versão válida durante preparação ou falha da substituição.
- **Consequência técnica:** a nova revisão será validada em staging, substituirá a ativa atomicamente, marcará a anterior como substituída e recalculará métricas e eventos adjacentes.
- **Risco evitado:** perda de auditoria, publicação parcial de correção e eventos derivados de fotografias diferentes da revisão oficial.
- **Alternativa considerada:** apagar a competência anterior e importar novamente no mesmo lugar.
- **Motivo da rejeição:** elimina a evidência histórica e expõe o sistema a estado intermediário inconsistente.
- **Trade-off:** retenção de metadados e possivelmente artefatos substituídos, além de fluxo operacional explícito para correções.
- **Responsável:** Tiago, Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 18. A janela do MVP é fixa; o motor histórico é parametrizável

- **Evidência:** em 24 de agosto de 2026, a fonte pública oferecia 40 competências de `2023-05` a `2026-08`; ampliar o período pode revelar estabelecimentos regionais que não pertencem à coorte do MVP.
- **Resultado escolhido:** validar o MVP com 13 competências, mas permitir janelas contínuas de outros tamanhos; uma expansão histórica completa cria nova janela e recalcula a coorte sobre todo o período.
- **Consequência de negócio:** o produto poderá incorporar história anterior sem apresentar um backfill parcial como representação completa da região.
- **Consequência técnica:** quantidade e sequência virão do manifesto, sem `13` fixo na regra geral; inicialmente haverá uma janela ativa, substituída atomicamente somente após a nova janela ser validada.
- **Risco evitado:** omitir empresas que deixaram a região antes de `2025-08` e misturar pacotes de coortes incompatíveis.
- **Alternativa considerada:** apenas anexar competências antigas à coorte já formada para o MVP.
- **Motivo da rejeição:** o acréscimo recuperaria somente o passado das entidades atuais e não o histórico regional completo.
- **Trade-off:** expandir o período exige reprocessar a coorte e regenerar inclusive os pacotes sobrepostos.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 19. Fontes nacionais são temporárias; pacotes ativos permanecem

- **Evidência:** 13 competências nacionais compactadas podem superar 90 GiB e os workspaces temporários contêm CPF mascarado antes da pseudonimização.
- **Resultado escolhido:** reter fontes nacionais apenas durante preparação, manter permanentemente manifesto e pacotes ativos e preservar pacotes substituídos completos pelo menos até a entrega oficial.
- **Consequência de negócio:** o projeto continua reproduzível pela origem pública e auditável sem acumular indefinidamente arquivos nacionais ou dados pessoais temporários.
- **Consequência técnica:** limpeza será manual e somente após validação dos pacotes; URL, hash, tamanho e competência da fonte permanecerão; PostgreSQL e auditoria não terão expurgo automático no MVP.
- **Risco evitado:** esgotamento de disco, retenção desnecessária de CPF mascarado e remoção prematura de evidência necessária à apresentação.
- **Alternativa considerada:** manter fontes nacionais, arquivos extraídos e todas as revisões completas indefinidamente.
- **Motivo da rejeição:** são artefatos volumosos e reproduzíveis que ampliam custo e superfície de privacidade.
- **Trade-off:** reprocessamento futuro pode exigir novo download; depois da entrega, remover pacote substituído exigirá decisão manual preservando manifesto, hash e lote.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 20. Setembro entrega dez eventos de maior valor; novembro completa os demais

- **Evidência:** implementar e testar 15 tipos até a meta interna aumenta o risco de atrasar o fluxo integrado por alterações de menor impacto demonstrativo.
- **Resultado escolhido:** tornar dez eventos P0 para setembro e cinco eventos P1 obrigatórios para a entrega oficial de novembro.
- **Consequência de negócio:** o MVP interno demonstrará abertura, baixa, movimentação regional, endereço, atividade, capital e mudanças de sócios; outubro ampliará a cobertura cadastral.
- **Consequência técnica:** P0 inclui os sete eventos de estabelecimento e capital, inclusão e remoção de sócios; os campos dos eventos P1 já estarão nos pacotes e snapshots para permitir recálculo sem nova preparação nacional.
- **Risco evitado:** deixar a entrega de ponta a ponta incompleta por tentar finalizar simultaneamente todos os eventos possíveis.
- **Alternativa considerada:** exigir os 15 eventos até 30 de setembro.
- **Motivo da rejeição:** aumenta casos-limite e esforço de QA sem crescimento equivalente no valor da primeira demonstração.
- **Trade-off:** natureza jurídica, porte, Simples, MEI e alteração de qualificação societária entram somente no período de refinamento.
- **Responsável:** Tiago, Product Owner.
- **Estado:** aprovado em 24 de agosto de 2026.

### 21. A fotografia de estabelecimento contém somente os campos necessários ao produto

- **Evidência:** os eventos P0 dependem de identidade, situação cadastral, atividade principal, endereço e localização; contatos e CNAEs secundários não sustentam funcionalidades aprovadas.
- **Resultado escolhido:** incluir no contrato de estabelecimento CNPJ completo, CNPJ básico, indicador matriz/filial, nome fantasia, situação cadastral com data e motivo, data de início, CNAE principal, endereço normalizado, TOM, IBGE, presença regional, competência e hash do registro.
- **Consequência de negócio:** a aplicação poderá pesquisar estabelecimentos e explicar seus eventos sem transportar atributos públicos que não tenham finalidade no MVP.
- **Consequência técnica:** o catálogo TOM–IBGE deverá cobrir também os municípios externos encontrados na coorte; somente os 35 municípios aprovados terão presença regional verdadeira.
- **Risco evitado:** perda de zeros em identificadores, comparações instáveis, exposição desnecessária de contatos e crescimento injustificado dos pacotes e snapshots.
- **Alternativa considerada:** copiar integralmente todas as colunas da tabela nacional de estabelecimentos.
- **Motivo da rejeição:** mistura disponibilidade da fonte com necessidade do produto e amplia volume, privacidade e superfície de testes.
- **Trade-off:** incluir futuramente telefone, e-mail, CNAEs secundários ou situação especial exigirá nova versão do contrato e regeneração dos pacotes afetados.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 22. A fotografia de empresa incorpora os atributos de Simples e MEI

- **Evidência:** dados corporativos, Simples e MEI compartilham o CNPJ básico e sustentam eventos pertencentes à empresa, não ao estabelecimento.
- **Resultado escolhido:** incluir no contrato de empresa CNPJ básico, razão social, natureza jurídica, capital social decimal, porte, indicadores e datas do Simples e do MEI, competência e hash do registro.
- **Consequência de negócio:** a consulta apresentará uma fotografia corporativa coesa e permitirá recalcular todos os eventos empresariais P0 e P1 aprovados.
- **Consequência técnica:** a preparação combinará as fontes por CNPJ básico antes de gerar `companies.parquet`, preservando no manifesto a linhagem e a validação de cada fonte.
- **Risco evitado:** duplicar identidades corporativas, atribuir regimes a filiais ou precisar baixar novamente as fontes para implementar os eventos P1.
- **Alternativa considerada:** transportar Empresas e Simples em tabelas e snapshots independentes ou copiar todas as colunas nacionais.
- **Motivo da rejeição:** aumenta junções e estados sem criar uma entidade de domínio distinta; campos sem finalidade ampliam o contrato desnecessariamente.
- **Trade-off:** uma inconsistência localizada na fonte do Simples deverá ser alertada sem invalidar automaticamente os demais atributos corporativos da empresa.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 23. A participação societária possui identidade estável conforme o tipo do sócio

- **Evidência:** eventos de inclusão, remoção e alteração de qualificação exigem reconhecer a mesma participação entre competências sem usar qualificação ou data de entrada como identidade.
- **Resultado escolhido:** transportar empresa, chave da participação, tipo, nome de exibição, raiz CNPJ de oito dígitos apenas para sócio PJ nacional, país quando aplicável, qualificação, data de entrada, competência e hash do registro. Fontes antigas com 14 dígitos e fontes novas com oito são normalizadas para a mesma raiz antes da construção da identidade.
- **Consequência de negócio:** o histórico societário mostrará nomes e qualificações e distinguirá inclusão, remoção e mudança de função sem expor CPF mascarado.
- **Consequência técnica:** PF usará HMAC restrito à empresa; PJ usará CNPJ; estrangeiro sem documento usará chave derivada de empresa, tipo, nome normalizado e país. Ambiguidade suspenderá apenas a comparação afetada.
- **Risco evitado:** correlacionar PF globalmente, fabricar remoção e inclusão por mudança de qualificação ou transportar atributos pessoais sem finalidade.
- **Alternativa considerada:** usar a linha completa da Receita ou nome, qualificação e data de entrada como uma chave composta única para todos os tipos.
- **Motivo da rejeição:** a primeira amplia a exposição de dados; a segunda transforma alterações comuns em identidades novas e não lida adequadamente com PJ.
- **Trade-off:** correção do nome de PF pode alterar sua chave pseudônima, e sócio estrangeiro sem documento pode permanecer ambíguo; ambos exigirão alerta em vez de inferência automática.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 24. A timeline começa em um baseline e termina em uma borda aberta

- **Evidência:** fotografias mensais comprovam somente os estados observados nas competências e não revelam, em regra, o dia exato da transição nem fatos posteriores à última fotografia.
- **Resultado escolhido:** manter a primeira competência sem eventos, tratar a última como borda aberta e atribuir cada mudança ao intervalo entre fotografias consecutivas.
- **Consequência de negócio:** a timeline distinguirá claramente observação, ocorrência cadastral explícita e momento de processamento, sem sugerir fatos fora da janela.
- **Consequência técnica:** datas explícitas da Receita serão evidências; `detected_at` será o instante do cálculo. Nova competência somente formará evento com a anterior dentro de uma janela validada que contenha ambas.
- **Risco evitado:** inventar alterações antes do baseline, inferir baixa, saída ou remoção depois da janela e apresentar o horário da importação como data real do fato.
- **Alternativa considerada:** atribuir toda alteração ao primeiro dia da nova competência e considerar o último snapshot como estado válido indefinidamente.
- **Motivo da rejeição:** cria uma precisão inexistente e estende conclusões além da evidência disponível.
- **Trade-off:** a maioria dos eventos terá precisão mensal, mesmo quando a interface desejaria uma data diária.
- **Responsável:** Tiago, Product Owner e Tech Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 25. Alertas numerosos deixam de ser localizados e bloqueiam a competência

- **Evidência:** permitir quantidade ilimitada de alertas transforma falha sistêmica em publicação aparentemente válida; um limite apenas absoluto ou apenas percentual distorce tabelas de tamanhos diferentes.
- **Resultado escolhido:** bloquear erros estruturais desde a primeira ocorrência e escalar cada regra localizada quando `affected_rows > max(10, ceil(eligible_rows × 0,001))`.
- **Consequência de negócio:** competências com poucas exceções transparentes poderão ser usadas, mas volumes anormais não contaminarão indicadores e timelines.
- **Consequência técnica:** até o limite haverá `PUBLISHED_WITH_WARNINGS` e suspensão das entidades afetadas; acima dele haverá `FAILED_QUALITY_GATE`. As 13 competências serão medidas antes de congelar a versão do contrato.
- **Risco evitado:** calibrar tolerâncias por mês para forçar publicação, esconder problemas generalizados e bloquear uma tabela grande por poucas exceções isoladas.
- **Alternativa considerada:** julgamento manual sem limite, percentual puro ou quantidade absoluta única.
- **Motivo da rejeição:** nenhuma dessas alternativas é simultaneamente reproduzível e proporcional aos diferentes tamanhos de tabela.
- **Trade-off:** o limite inicial de 0,1% é uma hipótese operacional e poderá exigir revisão após a medição, mas qualquer mudança será documentada, versionada e aplicada a toda a janela.
- **Calibração posterior:** a série oficial manteve 0,1% como regra geral e versionou `LATE_FIRST_SEEN` em 0,50%, uniformemente nas 13 competências, conforme o ADR 0018.
- **Responsável:** Tiago, Tech Lead, com validação de Gabriel, QA Lead.
- **Estado:** aprovado em 24 de agosto de 2026.

### 26. O MVP interno exige o fluxo histórico completo, não apenas uma demonstração parcial

- **Evidência:** a meta de 30 de setembro deve criar margem real para homologação até novembro; chamá-la de concluída sem dados, eventos, consultas e testes integrados esconderia o risco restante.
- **Resultado escolhido:** exigir as 13 competências, pesquisa e detalhe, dez eventos P0, timeline, dashboard básico, acompanhamento administrativo, comandos reproduzíveis, testes críticos documentados e execução completa por Docker Compose.
- **Consequência de negócio:** outubro começará com um produto demonstrável sobre dados reais e poderá ser dedicado a cinco eventos P1, qualidade visual, homologação e documentação acadêmica.
- **Consequência técnica:** nenhuma competência poderá ter erro fatal conhecido; alertas obedecerão ao limite aprovado. Testes unitários, integração do importador e aceitação manual serão evidências obrigatórias.
- **Risco evitado:** declarar sucesso com quatro cidades, poucas competências, dados fictícios ou telas desconectadas do pipeline real.
- **Alternativa considerada:** considerar concluído qualquer protótipo navegável ou subconjunto funcional entregue até a data.
- **Motivo da rejeição:** não reduziria de forma confiável o risco técnico antes da entrega oficial.
- **Trade-off:** autenticação, watchlist, cinco eventos P1 e refinamentos completos não bloquearão a meta interna, embora permaneçam no escopo da entrega oficial.
- **Responsável:** Tiago, Product Owner, com aceite de Gabriel e Emili sobre seus artefatos.
- **Estado:** aprovado em 24 de agosto de 2026.

## Dependências e decisões ainda abertas

Nenhuma decisão material aberta para validar o backend do MVP.
