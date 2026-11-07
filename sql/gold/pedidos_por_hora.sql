-- Qual é o horário de pico? 1 linha = 1 hora do dia em que houve pedido.
SELECT hour(hora)                AS hora,
       count(DISTINCT id_pedido) AS pedidos,
       sum(valor_item)           AS faturamento
FROM itens_pedido
GROUP BY 1
ORDER BY 1
