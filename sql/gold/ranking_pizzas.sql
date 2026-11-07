-- Quais pizzas vendem mais e menos? 1 linha = 1 sabor (todos os tamanhos somados).
SELECT nome_pizza, categoria,
       CAST(sum(quantidade) AS INTEGER) AS pizzas_vendidas,
       sum(valor_item) AS faturamento,
       rank() OVER (ORDER BY sum(quantidade) DESC) AS posicao_quantidade,
       rank() OVER (ORDER BY sum(valor_item) DESC) AS posicao_faturamento
FROM itens_pedido
GROUP BY 1, 2
ORDER BY posicao_faturamento, nome_pizza
