-- Qual dia vende mais? 1 linha = 1 dia da semana (segunda = 1).
-- média = pedidos / nº de datas com venda daquele dia da semana
SELECT isodow(data) AS num_dia,
       ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo'][isodow(data)] AS dia_semana,
       count(DISTINCT id_pedido) AS pedidos,
       sum(valor_item)           AS faturamento,
       CAST(count(DISTINCT id_pedido) / count(DISTINCT data) AS DECIMAL(10,2)) AS media_pedidos_por_dia
FROM itens_pedido
GROUP BY 1, 2
ORDER BY 1
