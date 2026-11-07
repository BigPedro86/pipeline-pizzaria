-- Qual categoria fatura mais? 1 linha = 1 categoria.
SELECT categoria,
       CAST(sum(quantidade) AS INTEGER) AS pizzas_vendidas,
       sum(valor_item) AS faturamento,
       CAST(100 * sum(valor_item) / sum(sum(valor_item)) OVER () AS DECIMAL(5,2)) AS participacao_pct
FROM itens_pedido
GROUP BY 1
ORDER BY faturamento DESC
