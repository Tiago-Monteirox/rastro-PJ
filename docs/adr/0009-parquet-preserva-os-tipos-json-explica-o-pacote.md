---
status: accepted
---

# Parquet preserva os tipos; JSON explica o pacote

As tabelas dos pacotes de competência usarão Parquet e seus manifestos usarão JSON UTF-8. CNPJ, IBGE, TOM e demais códigos permanecerão textuais; o manifesto declarará arquivos, tipos, versões, contagens, origem, alertas e hashes SHA-256.

## Considered Options

- Parquet para tabelas e JSON para manifestos;
- CSV compactado com gzip para as tabelas.

## Consequences

Os pacotes ganham compressão, leitura seletiva e tipos explícitos. Em troca, inspeção das tabelas exige ferramenta própria; relatórios auxiliares pequenos poderão ser exportados em JSON ou CSV para QA, sem substituir a fonte canônica.
