"""Transformação: raw (VARCHAR) -> refined (tipada, nomes em português, com JOIN)."""

from pathlib import Path

import duckdb

from src.config import PASTA_RAW, PASTA_REFINED, TABELAS_FONTE

# tabela refined -> SELECT sobre as views raw_<tabela>; CAST (não TRY_CAST) para falhar alto
CONSULTAS_REFINED: dict[str, str] = {
    "pedidos": """
        SELECT CAST(order_id AS INTEGER) AS id_pedido,
               CAST(date AS DATE)        AS data,
               CAST(time AS TIME)        AS hora
        FROM raw_orders
    """,
    "detalhes_pedido": """
        SELECT CAST(order_details_id AS INTEGER) AS id_detalhe,
               CAST(order_id AS INTEGER)         AS id_pedido,
               pizza_id                          AS id_pizza,
               CAST(quantity AS INTEGER)         AS quantidade
        FROM raw_order_details
    """,
    "pizzas": """
        SELECT pizza_id                     AS id_pizza,
               pizza_type_id                AS id_tipo_pizza,
               size                         AS tamanho,
               CAST(price AS DECIMAL(10,2)) AS preco
        FROM raw_pizzas
    """,
    "tipos_pizza": """
        SELECT pizza_type_id AS id_tipo_pizza,
               name          AS nome,
               category      AS categoria,
               ingredients   AS ingredientes
        FROM raw_pizza_types
    """,
    # JOIN das 4 tabelas: uma linha por item vendido
    "itens_pedido": """
        SELECT d.id_detalhe, d.id_pedido, p.data, p.hora,
               d.id_pizza, z.id_tipo_pizza, t.nome AS nome_pizza, t.categoria,
               z.tamanho, d.quantidade, z.preco,
               CAST(d.quantidade * z.preco AS DECIMAL(10,2)) AS valor_item
        FROM detalhes_pedido d
        JOIN pedidos p     ON p.id_pedido = d.id_pedido
        JOIN pizzas z      ON z.id_pizza = d.id_pizza
        JOIN tipos_pizza t ON t.id_tipo_pizza = z.id_tipo_pizza
    """,
}

CHAVES: dict[str, str] = {
    "pedidos": "id_pedido",
    "detalhes_pedido": "id_detalhe",
    "pizzas": "id_pizza",
    "tipos_pizza": "id_tipo_pizza",
    "itens_pedido": "id_detalhe",
}


def registrar_raw(con: duckdb.DuckDBPyConnection, origem: Path) -> None:
    """Cria uma view raw_<tabela> para cada Parquet da raw."""
    for tabela in TABELAS_FONTE:
        caminho = (origem / f"{tabela}.parquet").as_posix()
        con.execute(f"CREATE VIEW raw_{tabela} AS SELECT * FROM '{caminho}'")


def contar(con: duckdb.DuckDBPyConnection, tabela: str) -> int:
    """Retorna o número de linhas de uma tabela ou view."""
    return con.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]


def validar_sem_nulos(con: duckdb.DuckDBPyConnection, tabela: str) -> None:
    """Para o pipeline se qualquer coluna da tabela tiver nulo."""
    colunas = [c[0] for c in con.execute(f"DESCRIBE {tabela}").fetchall()]
    contagens = ", ".join(f'count(*) FILTER (WHERE "{c}" IS NULL)' for c in colunas)
    nulos = con.execute(f"SELECT {contagens} FROM {tabela}").fetchone()
    com_nulo = {c: n for c, n in zip(colunas, nulos) if n}
    if com_nulo:
        raise ValueError(f"{tabela}: nulos encontrados {com_nulo}")


def validar_chave_unica(con: duckdb.DuckDBPyConnection, tabela: str, chave: str) -> None:
    """Para o pipeline se a chave tiver valor repetido."""
    repetidas = con.execute(
        f"SELECT count(*) FROM (SELECT {chave} FROM {tabela} GROUP BY 1 HAVING count(*) > 1)"
    ).fetchone()[0]
    if repetidas:
        raise ValueError(f"{tabela}: {repetidas} valor(es) repetido(s) em {chave}")


def validar_join_sem_perda(con: duckdb.DuckDBPyConnection) -> None:
    """Para o pipeline se o JOIN de itens_pedido perdeu linhas de detalhes_pedido."""
    esperado, obtido = contar(con, "detalhes_pedido"), contar(con, "itens_pedido")
    if obtido != esperado:
        raise ValueError(
            f"itens_pedido: JOIN perdeu {esperado - obtido} de {esperado} itens"
        )


def criar_tabela(con: duckdb.DuckDBPyConnection, tabela: str) -> None:
    """Cria a tabela refined em memória e roda as validações dela."""
    con.execute(f"CREATE TABLE {tabela} AS {CONSULTAS_REFINED[tabela]}")
    validar_sem_nulos(con, tabela)
    validar_chave_unica(con, tabela, CHAVES[tabela])


def salvar_parquet(con: duckdb.DuckDBPyConnection, tabela: str, destino: Path) -> int:
    """Grava a tabela em destino/<tabela>.parquet (sobrescreve) e retorna as linhas."""
    destino.mkdir(parents=True, exist_ok=True)
    caminho = (destino / f"{tabela}.parquet").as_posix()
    con.execute(f"COPY {tabela} TO '{caminho}' (FORMAT parquet)")
    return contar(con, tabela)


def transformar_tudo(
    origem: Path = PASTA_RAW, destino: Path = PASTA_REFINED
) -> dict[str, int]:
    """Gera todas as tabelas da refined e retorna {tabela: linhas}.

    Só grava os Parquets depois que todas as validações passaram.
    """
    con = duckdb.connect()
    try:
        registrar_raw(con, origem)
        for tabela in CONSULTAS_REFINED:
            criar_tabela(con, tabela)
        validar_join_sem_perda(con)
        return {t: salvar_parquet(con, t, destino) for t in CONSULTAS_REFINED}
    finally:
        con.close()


if __name__ == "__main__":
    for nome, linhas in transformar_tudo().items():
        print(f"{nome}: {linhas} linhas")
