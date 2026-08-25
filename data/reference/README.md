# Referências geográficas

`triangulo_mineiro_35_municipios.csv` é a referência versionada do recorte `triangulo-mineiro-35`, versão 1.

Origem e validação em 24 de agosto de 2026:

- nomes e códigos IBGE: arquivo `triangulo_mineiro_35_municipios_ibge.csv` fornecido por Tiago;
- códigos TOM: `Municipios.zip` da competência `2026-08`, publicado no compartilhamento público da Receita Federal/Serpro;
- URL da fonte TOM: `https://arquivos.receitafederal.gov.br/public.php/dav/files/YggdBLfdninEJX9/2026-08/Municipios.zip`;
- os 35 códigos TOM foram confirmados no catálogo da Receita, preservando os zeros iniciais;
- nomes repetidos entre estados foram desambiguados por UF e código IBGE antes da versão final.

O arquivo é entrada do comando `load_geographic_scope`. Alterar municípios, IBGE ou TOM exige nova versão do recorte; não se deve sobrescrever silenciosamente uma versão já carregada.
