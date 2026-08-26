---
status: accepted
---

# Documento pessoal incidental também termina na preparação

Sequências isoladas com formato de CPF, completas ou mascaradas, serão removidas de campos textuais destinados à exibição e pesquisa durante a preparação. A regra alcança razão social, nome fantasia e nome exibido do sócio. Se a remoção esvaziar o campo obrigatório, o pacote usará `NOME SUPRIMIDO`. CNPJ completo de 14 caracteres e identificadores opacos gerados por HMAC não serão alterados.

## Context

A varredura da janela oficial encontrou sequências de 11 dígitos em razões sociais e, em menor quantidade, em nomes fantasia publicados pela própria fonte. Ainda que a sequência não prove por si só a validade do documento, persisti-la contraria a garantia aprovada de que CPF completo ou mascarado não chega aos pacotes, ao PostgreSQL, aos logs ou aos relatórios.

## Considered Options

- manter o texto da fonte por ser um dado público;
- ocultar somente na interface e preservar o valor nos pacotes e snapshots;
- remover o formato proibido na preparação e rejeitá-lo nas demais fronteiras;
- excluir integralmente as empresas afetadas.

## Consequences

A empresa e seu histórico continuam no recorte, mas o trecho semelhante a documento deixa de ser exibido e pesquisável. Pacotes corrigidos entram como novas revisões auditáveis. A retenção de conteúdo substituído tem exceção obrigatória de privacidade: depois da validação e publicação da revisão sanitizada, snapshots e pacotes antigos que contenham o dado proibido serão expurgados, preservando metadados, hashes, lotes e ocorrências necessários à auditoria. As fontes nacionais permanecem somente no workspace temporário previsto pela política de retenção.
