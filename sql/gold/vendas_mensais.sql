-- Como o faturamento evolui? 1 linha = 1 mês.
SELECT CAST(date_trunc('month', data) AS DATE) AS mes,
       count(DISTINCT id_pedido)              AS pedidos,
       CAST(sum(quantidade) AS INTEGER)       AS pizzas_vendidas,
       sum(valor_item)                        AS faturamento,
       CAST(sum(valor_item) / count(DISTINCT id_pedido) AS DECIMAL(10,2)) AS ticket_medio
FROM itens_pedido
GROUP BY 1
ORDER BY 1
