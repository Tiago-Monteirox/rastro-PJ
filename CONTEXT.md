# Rastro PJ

Este contexto descreve a linguagem do produto que transforma competências mensais do CNPJ em histórico empresarial regional e alterações rastreáveis.

## Entidades cadastrais

**CNPJ básico**:
Os oito primeiros caracteres alfanuméricos do CNPJ, usados como identidade estável da empresa e
compartilhados por seus estabelecimentos.
_Evitar_: CNPJ de oito dígitos, CNPJ completo

**CNPJ completo**:
Identidade de um estabelecimento formada por doze caracteres alfanuméricos e dois dígitos
verificadores numéricos.
_Evitar_: CNPJ somente numérico, CNPJ básico

**Empresa**:
Entidade jurídica identificada pelo CNPJ básico, proprietária de dados corporativos e do quadro societário.
_Evitar_: estabelecimento, filial

**Estabelecimento**:
Unidade matriz ou filial identificada pelo CNPJ completo, proprietária de localização, atividade e situação cadastral.
_Evitar_: empresa, CNPJ básico

**Evento de empresa**:
Alteração entre competências em um atributo corporativo ou societário pertencente à empresa.
_Evitar_: abertura de filial, baixa de estabelecimento

**Evento de estabelecimento**:
Alteração entre competências em localização, atividade, situação ou presença regional pertencente a um estabelecimento.
_Evitar_: encerramento da empresa, alteração societária

**Dimensão de alteração**:
Aspecto independente comparado entre duas fotografias, como situação cadastral, localização, atividade, dados corporativos ou sociedade.
_Evitar_: tipo de entidade, competência

**Evento primário**:
Evento mais específico que representa uma alteração dentro da mesma dimensão e intervalo, substituindo eventos genéricos equivalentes.
_Evitar_: evento duplicado, agrupamento de dimensões independentes

**Identidade societária PF**:
Identidade pseudônima de uma participação de pessoa física, limitada ao contexto de uma empresa e incapaz de relacionar globalmente a pessoa entre empresas.
_Evitar_: identidade da pessoa, CPF mascarado, identificador global

**Ausência cadastral**:
Falta de uma empresa ou estabelecimento em uma competência posterior à sua primeira fotografia, sem evidência explícita de baixa ou saída regional.
_Evitar_: encerramento, saída regional

**Ocorrência de qualidade de dados**:
Registro auditável de uma inconsistência ou incerteza da fonte ou do processamento que não representa um evento do negócio.
_Evitar_: evento cadastral, alteração empresarial

## Histórico mensal

**Competência**:
Fotografia mensal publicada da base aberta do CNPJ, identificada no formato `AAAA-MM`.
_Evitar_: mês, versão da empresa

**Intervalo de comparação**:
Par ordenado de competências consecutivas usado para identificar alterações cadastrais entre duas fotografias.
_Evitar_: competência, mês de mudança

**Baseline histórico**:
Primeira competência publicada da janela, usada como estado inicial sem gerar eventos de alteração.
_Evitar_: primeiro mês de eventos, abertura em massa

**Borda final aberta**:
Última competência publicada da janela, que representa o estado mais recente observado sem provar continuidade, encerramento ou qualquer alteração posterior.
_Evitar_: estado futuro, fim da entidade

**Competência cartográfica**:
Competência de referência selecionada no mapa analítico regional. No modo de concentração, define isoladamente o estado exibido; no modo de dinâmica, é comparada de forma explícita somente à competência publicada imediatamente anterior.
_Evitar_: soma de competências, posição atual permanente, intervalo arbitrário

**Data de detecção**:
Instante em que o importador calculou um evento derivado; não representa o dia exato em que a alteração cadastral ocorreu.
_Evitar_: data do evento, data efetiva da Receita

**Abertura de estabelecimento**:
Primeira aparição posterior ao baseline cuja data de início da atividade confirma que o estabelecimento surgiu no intervalo de comparação.
_Evitar_: primeira aparição tardia, entrada regional

**Primeira aparição tardia**:
Primeira fotografia posterior ao baseline cuja data de início é anterior ao intervalo e, portanto, não comprova abertura naquele período.
_Evitar_: abertura de estabelecimento

**Janela histórica**:
Conjunto ordenado de competências consecutivas que compartilham a mesma coorte, o mesmo recorte e o mesmo contrato de dados.
_Evitar_: coleção descontínua, acréscimo informal de competências

**Janela do MVP**:
Janela histórica de 13 competências, de `2025-08` a `2026-08`, que forma 12 intervalos de comparação e representa um ano completo de evolução.
_Evitar_: limite permanente do produto, 12 competências

**Janela ativa**:
Única janela histórica publicada que sustenta consultas, eventos e indicadores apresentados pela aplicação naquele momento.
_Evitar_: janela em preparação, múltiplas janelas combinadas

**MVP interno**:
Incremento integrado e demonstrável cuja meta pessoal é 30 de setembro de 2026, sujeito a critérios objetivos de aceite e distinto da entrega acadêmica oficial de novembro.
_Evitar_: versão parcial, entrega oficial

## Geografia

**Recorte geográfico**:
Conjunto fechado dos 35 municípios do Triângulo Mineiro aprovado para o MVP.
_Evitar_: região ampliada, quatro cidades do piloto

**Amostra técnica**:
Subconjunto formado por Uberlândia, Uberaba, Araguari e Ituiutaba, utilizado somente para acelerar desenvolvimento e testes sem alterar o recorte geográfico do produto.
_Evitar_: escopo reduzido, piloto de produção

**Mapa analítico regional**:
Visualização geográfica voltada à descoberta de concentrações, distribuições e padrões dos estabelecimentos no recorte geográfico. Apresenta dados agregados em escalas regionais e revela estabelecimentos individuais somente após aproximação ou aplicação de filtros.
_Evitar_: localizador cadastral, mapa de todos os endereços sem agregação

**Modo de análise cartográfica**:
Perspectiva que determina se o mapa apresenta o estoque ativo de uma competência ou a comparação entre duas competências consecutivas, mantendo explícita a semântica de cada resultado.
_Evitar_: camada visual, filtro temporal, intervalo livre

**Dinâmica territorial**:
Comparação experimental do estoque de estabelecimentos elegíveis ao mapa entre a competência cartográfica e a competência publicada imediatamente anterior, com os mesmos filtros aplicados separadamente às duas fotografias.
_Evitar_: previsão, tendência comprovada, comparação entre meses arbitrários

**Variação do estoque ativo**:
Diferença entre as quantidades filtradas de estabelecimentos elegíveis na competência atual e na anterior. Pode incluir ciclo de vida, movimentação regional e outros efeitos cadastrais.
_Evitar_: saldo de aberturas e baixas, crescimento econômico, geração de empregos

**Saldo de ciclo de vida**:
Diferença entre aberturas e baixas de estabelecimento confirmadas pelos eventos derivados no intervalo de comparação.
_Evitar_: variação do estoque, empresas criadas, saldo empresarial definitivo

**Outros efeitos cadastrais**:
Parcela residual da variação do estoque ativo após descontar o saldo de ciclo de vida, sem atribuição automática de causa específica.
_Evitar_: erro, migração regional confirmada, alteração cadastral identificada

**Recorte cartográfico da POC**:
Os mesmos 35 municípios do recorte geográfico do Triângulo Mineiro, exibidos integralmente pelo mapa analítico regional desde a POC.
_Evitar_: somente Araguari e Uberlândia, amostra técnica de quatro municípios

**Concentração cadastral de atividade**:
Distribuição geográfica dos estabelecimentos elegíveis ao mapa segundo o CNAE principal na competência cartográfica. Indica presença cadastral observada, não demanda, faturamento, intensidade concorrencial ou oportunidade comercial comprovada.
_Evitar_: tamanho do mercado, potencial de vendas, concorrência comprovada

**Referência demográfica municipal**:
População residente oficial associada ao código IBGE do município e ao ano em que foi medida, usada como denominador contextual sem alterar a competência cadastral analisada.
_Evitar_: população da competência, população atual, projeção de consumidores

**Densidade cadastral populacional**:
Quantidade de estabelecimentos elegíveis ao mapa por mil habitantes da referência demográfica municipal. Compara presença cadastral relativa, não emprego, demanda, faturamento ou atividade econômica por pessoa.
_Evitar_: densidade empresarial, potencial de mercado, empresas per capita

**Estabelecimento elegível ao mapa**:
Ocorrência regional de um estabelecimento com situação cadastral `02 — ATIVA` na competência selecionada. Somente estabelecimentos elegíveis compõem o mapa analítico regional da POC.
_Evitar_: empresa ativa, estabelecimento ativo em qualquer competência, demais situações cadastrais

**Referência geográfica CNEFE**:
Dados públicos do CNEFE 2022 do IBGE usados como fonte primária gratuita de coordenadas e qualidade posicional para localizar endereços da Receita. Não determinam situação cadastral nem substituem a fotografia da competência selecionada.
_Evitar_: cadastro de empresas de 2022, fonte da situação cadastral, geocodificação Mapbox

**Localização geográfica qualificada**:
Resultado espacial de uma fotografia de estabelecimento acompanhado obrigatoriamente do método utilizado: correspondência CNEFE no nível do endereço, aproximação pelo CEP ou não localizado. A aproximação nunca é apresentada como endereço preciso.
_Evitar_: coordenada exata, ponto sem origem, deslocamento aleatório

**Endereço geograficamente ambíguo**:
Correspondência textual no nível do endereço cujos melhores candidatos CNEFE possuem dispersão superior a 100 metros. Não recebe uma localização no nível do endereço e segue a aproximação pelo CEP.
_Evitar_: média das coordenadas, endereço preciso, escolha arbitrária

**Projeção cartográfica derivada**:
Estrutura recalculável que relaciona fotografias da Receita a localizações geográficas qualificadas obtidas da referência CNEFE, sem transformar as coordenadas externas em atributos oficiais das fotografias cadastrais.
_Evitar_: fotografia georreferenciada da Receita, coordenada oficial do CNPJ

**Projeção cartográfica publicada**:
Versão integral da projeção cartográfica derivada que concluiu o quality gate e está disponível para consulta. Uma preparação parcial ou reprovada nunca substitui a última versão publicada.
_Evitar_: staging geográfico, resultado parcial, última tentativa

**Preparação cartográfica**:
Processo manual, idempotente e retomável que resolve endereços distintos contra uma referência geográfica validada, materializa as 13 competências da projeção cartográfica derivada e somente então as publica para consulta.
_Evitar_: geocodificação na requisição, processamento parcial publicado

**Quality gate cartográfico**:
Conjunto de verificações estruturais e limites de cobertura que uma projeção cartográfica deve satisfazer integralmente antes de ser publicada para consulta.
_Evitar_: inspeção apenas visual, publicação parcial, cobertura presumida

**Nível cartográfico**:
Etapa progressiva da exploração do mapa: visão regional por município, visão municipal por clusters e visão local por estabelecimento ou endereço compartilhado.
_Evitar_: carregar todos os pontos na abertura, nível de precisão espacial

**Agregação cartográfica progressiva**:
Resposta completa adequada ao nível de zoom e à área visível, calculada pelo backend antes da renderização. Quando o detalhe ultrapassa o limite seguro, o servidor amplia a agregação em vez de truncar silenciosamente os dados.
_Evitar_: GeoJSON integral, amostra silenciosa, clustering de conjunto incompleto

**Ocorrência regional**:
Fotografia de um estabelecimento cuja localização pertence ao recorte geográfico naquela competência específica.
_Evitar_: empresa regional, sede regional

**Estabelecimento com presença regional**:
Estabelecimento identificado pelo CNPJ completo que possui ao menos uma ocorrência regional dentro da janela histórica, seja matriz ou filial.
_Evitar_: estabelecimento sediado, somente matriz

**Empresa com presença regional**:
Entidade identificada pelo CNPJ básico que possui ao menos um estabelecimento com presença regional dentro da janela histórica.
_Evitar_: empresa sediada na região, matriz regional

**Coorte regional**:
Conjunto de estabelecimentos com presença regional cujas fotografias serão mantidas por toda a janela histórica, inclusive quando a localização estiver fora do recorte geográfico.
_Evitar_: estabelecimentos do mês, filtro mensal isolado

**Entrada regional**:
Transição confirmada de um estabelecimento de fora para dentro do recorte geográfico entre duas competências consecutivas.
_Evitar_: abertura, primeira fotografia da janela

**Saída regional**:
Transição confirmada de um estabelecimento de dentro para fora do recorte geográfico entre duas competências consecutivas.
_Evitar_: baixa, desaparecimento da fonte

**Código IBGE do município**:
Identidade canônica de sete dígitos usada pelo produto para reconhecer um município.
_Evitar_: nome como identidade, código numérico sem zeros

**Código TOM**:
Identificador textual de quatro dígitos usado pela Receita Federal para o município nos dados do CNPJ e relacionado ao código IBGE pela tabela oficial.
_Evitar_: código IBGE, número inteiro

## Fluxo de dados

**Preparação da janela histórica**:
Processo automatizado, iniciado manualmente, que transforma as fontes nacionais oficiais na coorte regional e em pacotes regionais auditáveis.
_Evitar_: filtragem manual, edição de CSV

**Pacote de competência**:
Artefato regional imutável, rastreável e validado que transporta exatamente uma competência da coorte regional para a aplicação.
_Evitar_: dump nacional, pacote de toda a janela

**Manifesto da janela**:
Contrato que relaciona todos os pacotes esperados à mesma janela histórica, coorte regional, recorte geográfico e versões de dados.
_Evitar_: pacote de competência, lista informal de arquivos

**Importação da competência**:
Processo automatizado, iniciado manualmente, que valida um pacote de competência e incorpora sua fotografia ao histórico da aplicação.
_Evitar_: preparação regional, upload para servidor

**Competência publicada**:
Competência integralmente validada e incorporada ao histórico como uma unidade, apta a participar de comparações consecutivas.
_Evitar_: pacote recebido, carga parcial

**Fotografia normalizada**:
Representação persistida do estado conhecido de uma entidade em uma competência publicada, limitada aos atributos do produto.
_Evitar_: arquivo nacional bruto, evento

**Fotografia normalizada de estabelecimento**:
Estado mensal de um estabelecimento contendo identidade, nome fantasia, situação cadastral, atividade principal, endereço, município, presença regional e dados de auditoria definidos pelo produto. Não contém contatos nem CNAEs secundários no MVP.
_Evitar_: linha completa da Receita Federal, cadastro de empresa

**Fotografia normalizada de empresa**:
Estado mensal da entidade identificada pelo CNPJ básico, reunindo razão social, natureza jurídica, capital social, porte, Simples, MEI e dados de auditoria definidos pelo produto.
_Evitar_: fotografia de estabelecimento, linha nacional completa

**Fotografia normalizada de participação societária**:
Estado mensal do vínculo entre uma empresa e um sócio PF, PJ ou estrangeiro, identificado por uma chave estável e contendo somente nome de exibição, tipo, qualificação, data de entrada, país ou CNPJ de PJ quando aplicáveis e dados de auditoria.
_Evitar_: cadastro completo da pessoa, quadro societário sem competência

**Evento derivado**:
Diferença de negócio calculada entre duas fotografias normalizadas consecutivas e passível de recálculo sem alterar as fotografias de origem.
_Evitar_: fonte primária, fotografia cadastral

**Lacuna histórica**:
Competência esperada que ainda não foi publicada e que impede publicar ou comparar as competências posteriores da mesma janela.
_Evitar_: mês sem alterações, competência pulada

**Erro fatal de competência**:
Inconsistência estrutural ou sistêmica que impede considerar o pacote íntegro e, portanto, impede sua publicação.
_Evitar_: alerta localizado, campo opcional ausente

**Alerta de qualidade**:
Ocorrência localizada e isolável que permite publicar a competência com transparência, suspendendo somente o dado ou a entidade afetada.
_Evitar_: erro fatal, correção silenciosa

**Limite de escalada de alertas**:
Quantidade máxima tolerada por regra em uma competência. A regra geral é `max(10, ceil(0,1% das linhas elegíveis))`; `LATE_FIRST_SEEN` usa a calibração longitudinal versionada de 0,50%. Ao ultrapassar o limite aplicável, o alerta deixa de ser localizado e bloqueia a competência.
_Evitar_: tolerância ajustada por mês, meta informal

**Competência publicada com alertas**:
Competência íntegra no contrato geral, mas acompanhada de alertas de qualidade explícitos e auditáveis.
_Evitar_: competência inválida, publicação silenciosa

**Revisão de competência**:
Versão identificável de uma mesma competência, produzida para corrigir seu conteúdo sem apagar a versão anteriormente publicada.
_Evitar_: nova competência, sobrescrita silenciosa

**Revisão substituída**:
Revisão que deixou de ser oficial após a publicação atômica de uma correção, mas permanece registrada para auditoria.
_Evitar_: revisão apagada, revisão ativa
