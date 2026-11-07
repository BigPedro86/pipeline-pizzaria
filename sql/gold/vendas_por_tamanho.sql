-- Qual tamanho sai mais? 1 linha = 1 tamanho, em ordem S, M, L, XL, XXL (não alfabética).
SELECT tamanho,
       CAST(sum(quantidade) AS INTEGER) AS pizzas_vendidas,
       sum(valor_item) AS faturamento,
       CAST(100 * sum(valor_item) / sum(sum(valor_item)) OVER () AS DECIMAL(5,2)) AS participacao_pct
FROM itens_pedido
GROUP BY 1
ORDER BY list_position(['S', 'M', 'L', 'XL', 'XXL'], tamanho)
