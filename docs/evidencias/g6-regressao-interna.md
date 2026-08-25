# Evidência G6 — regressão interna

**Estado:** candidata técnica interna aprovada; homologação da equipe e acadêmica pendente  
**Data:** 25/08/2026  
**Ambiente:** Mac local, Docker Compose e PostgreSQL

## Resultado

O monólito, a janela oficial, os derivados e os fluxos do portal passaram pela regressão técnica final sem erro fatal conhecido.

| Verificação | Resultado |
|---|---|
| suíte Django em PostgreSQL | 67/67 testes em 3,193 s |
| Ruff lint | aprovado |
| Ruff format | 104 arquivos conformes |
| Django system check | nenhum issue |
| migrações | `No changes detected` |
| Docker Compose | configuração válida, exit code 0 |
| pacote oficial idempotente | `COMPLETED/no_op` em 2,61 s |
| privacidade dos pacotes | zero ocorrência proibida |
| privacidade global do PostgreSQL | `blocking_total=0` |
| desempenho | todos os caminhos medidos abaixo de 2 s |

## Testes temporais fechados

Três testes adicionais tornaram explícitas as fronteiras que antes estavam apenas cobertas indiretamente:

- primeira competência usada como baseline, sem comparação anterior;
- recálculo limitado a pares adjacentes e ordenados;
- abertura usando `(competência anterior, competência atual]`;
- data na borda anterior classificada como `LATE_FIRST_SEEN`, sem falsa abertura;
- data na competência atual classificada como `ESTABLISHMENT_OPENED`.

Os testes temporais direcionados passaram junto com os 67 testes da regressão.

## Idempotência oficial

O batch `842ce935-854b-4d8c-81c0-be67a0a0bf3d` concluiu como `COMPLETED`, fase `no_op`, com:

- `no_op = true`;
- 13 competências preservadas;
- 278.301 eventos preservados;
- 21.169 alertas preservados;
- manifesto inalterado;
- duração aproximada de 2,61 s.

Nenhuma fotografia, evento ou métrica foi duplicada.

## Matriz de aceite

Dos 34 cenários documentados:

- 18 estão aprovados por teste automatizado;
- 8 estão aprovados também no volume oficial;
- 7 possuem cobertura parcial explicitamente descrita;
- 1 permanece pendente: expansão ponta a ponta para competências anteriores em nova janela/coorte.

As pendências parciais não são ocultadas. Elas abrangem fixtures dedicadas de matriz externa/filial regional, ausência de empresa, lacuna de publicação, ambiguidade societária localizada, tentativa de busca por PF e limpeza final de fontes temporárias.

## Desempenho

| Caminho | Tempo observado |
|---|---:|
| dashboard padrão | 95 ms |
| dashboard filtrado | 204 ms |
| busca sem termo | 6 ms |
| busca com termo | 12 ms |
| detalhe | 26 ms |
| eventos padrão | 363 ms |
| eventos por CNPJ | 55 ms |

O filtro por CNPJ foi corrigido antes da medição final. Os números são observações locais, não percentis de produção.

## Limite do aceite

O frontend provisório foi inspecionado informalmente pelo Product Owner e considerado suficiente para esta etapa; a validação visual formal foi dispensada porque não é a interface definitiva. Isso não substitui UX, protótipo, identidade visual ou acessibilidade da entrega acadêmica.

Não foi registrada aprovação em nome de Gabriel, Emili ou do professor. Portanto, G6 está tecnicamente apto para demonstração interna, mas seu aceite coletivo e acadêmico continua pendente.
