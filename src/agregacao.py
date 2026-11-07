"""Agregação: refined/itens_pedido -> gold (uma tabela de KPI por pergunta)."""

from decimal import Decimal
from pathlib import Path

import duckdb

from src.config import PASTA_GOLD, PASTA_REFINED, PASTA_SQL_GOLD, TABELAS_GOLD


def carregar_consultas(
    pasta: Path = PASTA_SQL_GOLD, tabelas: list[str] = TABELAS_GOLD
) -> dict[str, str]:
    """Lê sql/gold/<tabela>.sql de cada KPI e retorna {tabela: SELECT}.

    Para o pipeline se faltar o .sql de algum KPI.
    """
    consultas = {}
    for tabela in tabelas:
        arquivo = pasta / f"{tabela}.sql"
        if not arquivo.exists():
            raise FileNotFoundError(f"KPI sem arquivo SQL: {arquivo}")
        consultas[tabela] = arquivo.read_text(encoding="utf-8")
    return consultas


# tabela gold -> SELECT sobre a view itens_pedido (lido de sql/gold/)
CONSULTAS_GOLD: dict[str, str] = carregar_consultas()

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
