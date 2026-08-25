---
status: accepted
---

# Auditoria suficiente, retenção mínima

Fontes nacionais e arquivos extraídos serão temporários e removidos manualmente somente após validação da janela. Manifesto e pacotes ativos permanecerão; pacotes substituídos completos serão preservados pelo menos até a entrega oficial, junto da auditoria permanente de hashes e lotes, salvo quando contiverem dado pessoal proibido pela política de privacidade.

## Considered Options

- retenção mínima de fontes reproduzíveis e preservação dos artefatos regionais;
- retenção indefinida de todos os arquivos nacionais e intermediários.

## Consequences

Reprocessar poderá exigir novo download público. Workspaces com CPF mascarado não serão versionados ou copiados e serão limpos após sucesso. Se uma revisão substituída contiver dado pessoal proibido, seu conteúdo será expurgado depois da validação da substituta; metadados, hashes, lotes e ocorrências permanecerão como trilha de auditoria. Fora dessa exceção, nenhuma exclusão será automática no MVP.
