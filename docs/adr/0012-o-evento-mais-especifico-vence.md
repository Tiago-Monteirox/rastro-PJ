---
status: accepted
---

# O evento mais específico vence

Para a mesma entidade, dimensão e intervalo, somente o evento mais específico será publicado. Eventos genéricos sobrepostos serão suprimidos, enquanto alterações em dimensões independentes continuarão gerando eventos separados.

## Considered Options

- aplicar precedência e publicar um evento primário por dimensão;
- publicar todas as classificações técnicas detectadas.

## Consequences

O comparador manterá precedências explícitas: encerramento substitui mudança genérica para baixada; entrada ou saída regional substitui mudança de endereço correspondente; abertura não compara contra fotografia inexistente. Indicadores deixam de contar o mesmo fato duas vezes.
