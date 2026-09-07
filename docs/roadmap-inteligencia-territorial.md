# Roadmap de inteligência territorial

**Produto:** Rastro PJ  
**Status:** documento evolutivo; primeiro experimento implementado e validado internamente  
**Última revisão:** 7 de setembro de 2026

## Objetivo

Evoluir o mapa de uma visualização de concentração cadastral para uma ferramenta de leitura da transformação empresarial do Triângulo Mineiro. Cada incremento deve produzir um insight explicável, usar fonte pública e gratuita, preservar a rastreabilidade temporal e evitar conclusões econômicas que os dados não sustentam.

Este roadmap registra possibilidades, não compromissos de entrega. Cada nova camada exige uma pequena prova de dados antes de entrar no produto.

## Ordem recomendada

| Ordem | Incremento | Insight principal | Fonte | Esforço | Estado |
|---:|---|---|---|---|---|
| 1 | Dinâmica territorial | Onde o estoque ativo cresceu ou diminuiu entre competências? | Dados já importados da Receita e eventos derivados | Médio | Experimento atual |
| 2 | Especialização por atividade | Quais municípios concentram proporcionalmente cada CNAE? | Dados já importados | Baixo | Próximo candidato |
| 3 | Densidade e indicadores relativos | A concentração permanece alta após considerar população ou área? | IBGE Cidades e Estados/SIDRA | Baixo–médio | Planejado |
| 4 | Maturidade e renovação empresarial | O território é composto por negócios novos, maduros ou longevos? | Data de início da atividade | Baixo | Planejado |
| 5 | Contratações públicas | Quais empresas e setores aparecem como fornecedores públicos? | PNCP | Médio–alto | Investigação |
| 6 | Integridade cadastral | Há ocorrência da empresa em cadastros públicos restritivos? | CEIS, CNEP, CEPIM e Lista Suja | Médio | Roadmap geral |
| 7 | Ecossistemas de saúde e educação | Como empresas se distribuem ao redor de equipamentos setoriais? | CNES e Censo Escolar | Alto | Exploração futura |

## Experimento 1 — dinâmica territorial

### Pergunta

Como o estoque filtrado de estabelecimentos ativos mudou em cada município e CNAE entre duas competências consecutivas?

### Recorte e regras

- a competência selecionada é comparada somente à competência publicada imediatamente anterior;
- a primeira competência da janela é baseline e não possui comparação;
- município, CNAE, matriz/filial, porte, perfil tributário e precisão espacial são aplicados separadamente às duas fotografias;
- o filtro “abertura do estabelecimento” é incompatível com este modo, pois reduziria cada fotografia por uma janela móvel diferente;
- a visualização é municipal: pontos individuais continuam pertencendo ao modo de concentração atual;
- vermelho representa retração do estoque, tom neutro representa estabilidade e verde representa crescimento;
- a escala de cores é simétrica em torno de zero e recalculada para o recorte;
- rankings ordenam municípios e CNAEs pelo maior movimento absoluto, preservando o sinal da variação.

### Métricas

Para o mesmo recorte filtrado:

```text
variação do estoque = estoque atual − estoque anterior
taxa de variação = variação do estoque ÷ estoque anterior
saldo de ciclo de vida = aberturas confirmadas − baixas confirmadas
outros efeitos cadastrais = variação do estoque − saldo de ciclo de vida
```

“Outros efeitos cadastrais” é um resíduo explicativo, não uma causa. Pode refletir entrada ou saída regional, mudança de situação diferente de abertura/baixa, mudança de CNAE ou porte, aparição tardia na fonte e efeito dos filtros. Uma decomposição causal completa fica fora deste experimento.

### Critérios de aceite

- alternar o modo não altera a consulta de concentração existente;
- os totais anterior e atual conferem com consultas independentes das duas competências;
- crescimento e retração usam sinais, cores e textos coerentes;
- aberturas e baixas contam somente eventos confirmados do intervalo correspondente;
- municípios sem observação em uma das competências permanecem comparáveis com estoque zero;
- baseline e combinações incompatíveis produzem erro compreensível;
- tabela acessível expõe os mesmos valores do mapa;
- o experimento mantém o p95 local aquecido de resumo abaixo de 1 segundo.

### Limitações

- a competência mensal informa quando a mudança foi detectada, não o dia exato em que ocorreu;
- variação cadastral não comprova crescimento econômico, faturamento, emprego ou demanda;
- o CNEFE influencia somente cobertura e precisão espacial, não a elegibilidade cadastral;
- comparações muito pequenas devem ser lidas com o valor absoluto e não apenas com a taxa percentual;
- não há previsão, projeção de tendência, animação temporal ou comparação arbitrária neste estágio.

## Próximos incrementos sem nova fonte

### Especialização territorial por CNAE

Calcular um quociente locacional cadastral: participação do CNAE no município dividida pela participação do mesmo CNAE na região. O resultado mostraria especialização relativa, não produtividade ou vantagem econômica. Deve sempre exibir também as contagens absolutas e exigir um denominador mínimo para evitar destaque de amostras irrelevantes.

### Idade e renovação do tecido empresarial

Adicionar faixas de idade do estabelecimento e indicadores de abertura por coorte: até 1 ano, 1–3, 3–5, 5–10 e mais de 10 anos. Isso permitiria comparar municípios dominados por negócios recentes ou longevos sem buscar outra base.

### Persistência da mudança

Classificar uma expansão ou retração municipal como pontual ou persistente depois de duas ou três comparações consecutivas. O recurso deve usar linguagem descritiva e não chamar persistência histórica de tendência futura.

## Enriquecimentos com fontes públicas

### IBGE — população, área e PIB municipal

Permite indicadores por mil habitantes, por quilômetro quadrado e contextualização econômica municipal. A competência anual e a defasagem de cada indicador devem aparecer na interface; valores de anos diferentes não podem ser apresentados como se fossem simultâneos.

Fonte oficial: [IBGE — Cidades e Estados](https://www.ibge.gov.br/cidades-e-estados.html) e [PIB dos Municípios](https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9088-produto-interno-bruto-dos-municipios.html).

### PNCP — contratações públicas

Permite mostrar presença de fornecedores, quantidade e valor homologado de contratos, distribuição por órgão e setor. O primeiro teste deve usar a API aberta sem login em uma amostra temporal curta, medir cobertura de CNPJ e decidir se a atualização será por download ou consulta incremental.

Fonte oficial: [PNCP — Dados Abertos](https://www.gov.br/pncp/pt-br/acesso-a-informacao/dados-abertos) e [manuais](https://www.gov.br/pncp/pt-br/pncp/manuais).

### CEIS, CNEP e CEPIM — integridade pública

Permitem sinalizar ocorrência em cadastros de sanções ou impedimentos. O produto deve mostrar cadastro, órgão, período e situação, sem converter ocorrência em nota opaca de risco. Para carga em massa, devem ser preferidos os arquivos completos aos limites da API.

Fonte oficial: [Portal da Transparência — downloads de dados](https://portaldatransparencia.gov.br/download-de-dados/).

### Lista Suja do Trabalho Escravo

Permite sinalizar coincidências com o Cadastro de Empregadores do Ministério do Trabalho e Emprego. Pessoas físicas continuam fora do escopo; somente entradas com identidade PJ suficientemente confiável podem ser relacionadas automaticamente.

Fonte oficial: [MTE — Combate ao Trabalho Escravo](https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/inspecao-do-trabalho/areas-de-atuacao/combate-ao-trabalho-escravo-e-analogo-ao-de-escravo).

### CNES e Censo Escolar

Podem sustentar análises setoriais de saúde e educação, como concentração de fornecedores e serviços perto de equipamentos públicos e privados. São camadas contextuais, não cadastros substitutos da Receita, e exigem avaliação prévia de chaves, coordenadas, licenciamento e granularidade.

Fontes oficiais: [CNES no Portal de Dados Abertos](https://dados.gov.br/dados/conjuntos-dados/cnes-cadastro-nacional-de-estabelecimentos-de-saude) e [Inep — microdados do Censo Escolar](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar).

## Gate para qualquer nova fonte

Antes da implementação definitiva, registrar:

1. pergunta de negócio e métrica pretendida;
2. URL oficial, licença, periodicidade e formato;
3. chave de relacionamento e taxa de cobertura no recorte;
4. riscos de falso positivo, duplicidade, defasagem e mudança de schema;
5. custo de armazenamento, preparação e atualização;
6. regras de privacidade e apresentação responsável;
7. critérios de aceite, rollback e rastreabilidade da versão importada.

O experimento só avança quando a resposta agrega valor além do que o Rastro PJ já demonstra e pode ser reproduzida sem serviço pago ou quebra de CAPTCHA.
