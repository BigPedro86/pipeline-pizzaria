-- Quanto vendemos no ano? 1 linha = o ano inteiro.
SELECT sum(valor_item)                    AS faturamento,
       count(DISTINCT id_pedido)          AS pedidos,
       CAST(sum(quantidade) AS INTEGER)   AS pizzas_vendidas,
       CAST(sum(valor_item) / count(DISTINCT id_pedido) AS DECIMAL(10,2)) AS ticket_medio,
       CAST(sum(quantidade) / count(DISTINCT id_pedido) AS DECIMAL(10,2)) AS pizzas_por_pedido
FROM itens_pedido
