"""Agregação: refined/itens_pedido -> gold (uma tabela de KPI por pergunta)."""

from decimal import Decimal
from pathlib import Path

import duckdb

from src.config import PASTA_GOLD, PASTA_REFINED

# tabela gold -> SELECT sobre a view itens_pedido
CONSULTAS_GOLD: dict[str, str] = {
    "resumo_geral": """
        SELECT sum(valor_item)                    AS faturamento,
               count(DISTINCT id_pedido)          AS pedidos,
               CAST(sum(quantidade) AS INTEGER)   AS pizzas_vendidas,
               CAST(sum(valor_item) / count(DISTINCT id_pedido) AS DECIMAL(10,2)) AS ticket_medio,
               CAST(sum(quantidade) / count(DISTINCT id_pedido) AS DECIMAL(10,2)) AS pizzas_por_pedido
        FROM itens_pedido
    """,
    "vendas_mensais": """
        SELECT CAST(date_trunc('month', data) AS DATE) AS mes,
               count(DISTINCT id_pedido)              AS pedidos,
               CAST(sum(quantidade) AS INTEGER)       AS pizzas_vendidas,
               sum(valor_item)                        AS faturamento,
               CAST(sum(valor_item) / count(DISTINCT id_pedido) AS DECIMAL(10,2)) AS ticket_medio
        FROM itens_pedido
        GROUP BY 1
        ORDER BY 1
    """,
    "vendas_por_categoria": """
        SELECT categoria,
               CAST(sum(quantidade) AS INTEGER) AS pizzas_vendidas,
               sum(valor_item) AS faturamento,
               CAST(100 * sum(valor_item) / sum(sum(valor_item)) OVER () AS DECIMAL(5,2)) AS participacao_pct
        FROM itens_pedido
        GROUP BY 1
        ORDER BY faturamento DESC
    """,
    "ranking_pizzas": """
        SELECT nome_pizza, categoria,
               CAST(sum(quantidade) AS INTEGER) AS pizzas_vendidas,
               sum(valor_item) AS faturamento,
               rank() OVER (ORDER BY sum(quantidade) DESC) AS posicao_quantidade,
               rank() OVER (ORDER BY sum(valor_item) DESC) AS posicao_faturamento
        FROM itens_pedido
        GROUP BY 1, 2
        ORDER BY posicao_faturamento, nome_pizza
    """,
    "vendas_por_tamanho": """
        SELECT tamanho,
               CAST(sum(quantidade) AS INTEGER) AS pizzas_vendidas,
               sum(valor_item) AS faturamento,
               CAST(100 * sum(valor_item) / sum(sum(valor_item)) OVER () AS DECIMAL(5,2)) AS participacao_pct
        FROM itens_pedido
        GROUP BY 1
        ORDER BY list_position(['S', 'M', 'L', 'XL', 'XXL'], tamanho)
    """,
    "pedidos_por_hora": """
        SELECT hour(hora)                AS hora,
               count(DISTINCT id_pedido) AS pedidos,
               sum(valor_item)           AS faturamento
        FROM itens_pedido
        GROUP BY 1
        ORDER BY 1
    """,
    # média = pedidos / nº de datas com venda daquele dia da semana
    "pedidos_por_dia_semana": """
        SELECT isodow(data) AS num_dia,
               ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo'][isodow(data)] AS dia_semana,
               count(DISTINCT id_pedido) AS pedidos,
               sum(valor_item)           AS faturamento,
               CAST(count(DISTINCT id_pedido) / count(DISTINCT data) AS DECIMAL(10,2)) AS media_pedidos_por_dia
        FROM itens_pedido
        GROUP BY 1, 2
        ORDER BY 1
    """,
}

# tabelas cuja soma de faturamento / pedidos deve bater com o resumo_geral
TABELAS_COM_FATURAMENTO: list[str] = [
    "vendas_mensais", "vendas_por_categoria", "ranking_pizzas",
    "vendas_por_tamanho", "pedidos_por_hora", "pedidos_por_dia_semana",
]
TABELAS_COM_PEDIDOS: list[str] = ["vendas_mensais", "pedidos_por_hora", "pedidos_por_dia_semana"]


def registrar_refined(con: duckdb.DuckDBPyConnection, origem: Path) -> None:
    """Cria a view itens_pedido a partir da refined."""
    caminho = (origem / "itens_pedido.parquet").as_posix()
    con.execute(f"CREATE VIEW itens_pedido AS SELECT * FROM '{caminho}'")


def somar(con: duckdb.DuckDBPyConnection, tabela: str, coluna: str) -> Decimal | int | None:
    """Retorna a soma de uma coluna de uma tabela."""
    return con.execute(f"SELECT sum({coluna}) FROM {tabela}").fetchone()[0]


def validar_totais(con: duckdb.DuckDBPyConnection) -> None:
    """Para o pipeline se algum KPI não fechar com o resumo_geral e a refined."""
    faturamento = somar(con, "itens_pedido", "valor_item")
    pedidos = con.execute("SELECT count(DISTINCT id_pedido) FROM itens_pedido").fetchone()[0]
    esperados = {("resumo_geral", "faturamento"): faturamento, ("resumo_geral", "pedidos"): pedidos}
    esperados |= {(t, "faturamento"): faturamento for t in TABELAS_COM_FATURAMENTO}
    esperados |= {(t, "pedidos"): pedidos for t in TABELAS_COM_PEDIDOS}
    for (tabela, coluna), esperado in esperados.items():
        obtido = somar(con, tabela, coluna)
        if obtido != esperado:
            raise ValueError(f"{tabela}.{coluna}: soma {obtido}, esperado {esperado}")


def salvar_parquet(con: duckdb.DuckDBPyConnection, tabela: str, destino: Path) -> int:
    """Grava a tabela em destino/<tabela>.parquet (sobrescreve) e retorna as linhas."""
    destino.mkdir(parents=True, exist_ok=True)
    caminho = (destino / f"{tabela}.parquet").as_posix()
    con.execute(f"COPY {tabela} TO '{caminho}' (FORMAT parquet)")
    return con.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]


def agregar_tudo(
    origem: Path = PASTA_REFINED, destino: Path = PASTA_GOLD
) -> dict[str, int]:
    """Gera todas as tabelas da gold e retorna {tabela: linhas}.

    Só grava os Parquets depois que os totais fecharem.
    """
    con = duckdb.connect()
    try:
        registrar_refined(con, origem)
        for tabela, sql in CONSULTAS_GOLD.items():
            con.execute(f"CREATE TABLE {tabela} AS {sql}")
        validar_totais(con)
        return {t: salvar_parquet(con, t, destino) for t in CONSULTAS_GOLD}
    finally:
        con.close()


if __name__ == "__main__":
    for nome, linhas in agregar_tudo().items():
        print(f"{nome}: {linhas} linhas")
