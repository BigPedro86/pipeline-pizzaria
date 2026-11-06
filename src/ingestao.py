"""Ingestão: CSVs de data/fonte -> Parquet em data/raw (espelho fiel, tudo VARCHAR)."""

from pathlib import Path

import duckdb
import pandas as pd

from src.config import PASTA_FONTE, PASTA_RAW, TABELAS_FONTE


def ler_csv(caminho: Path, encoding: str) -> pd.DataFrame:
    """Lê um CSV inteiro como texto, sem converter "NA" ou "" em nulo.

    Levanta FileNotFoundError se o arquivo não existir e
    UnicodeDecodeError se o encoding estiver errado.
    """
    return pd.read_csv(caminho, encoding=encoding, dtype=str, keep_default_na=False)


def validar_colunas(df: pd.DataFrame, esperadas: list[str], tabela: str) -> None:
    """Para o pipeline se as colunas do CSV não forem exatamente as esperadas."""
    encontradas = list(df.columns)
    if encontradas != esperadas:
        raise ValueError(
            f"{tabela}: colunas esperadas {esperadas}, encontradas {encontradas}"
        )


def salvar_parquet(df: pd.DataFrame, destino: Path) -> None:
    """Grava o DataFrame em Parquet com todas as colunas VARCHAR (sobrescreve)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.register("df", df)
        colunas = ", ".join(f'CAST("{c}" AS VARCHAR) AS "{c}"' for c in df.columns)
        con.execute(
            f"COPY (SELECT {colunas} FROM df) TO '{destino.as_posix()}' (FORMAT parquet)"
        )
    finally:
        con.close()


def ingerir_tabela(
    tabela: str,
    origem: Path = PASTA_FONTE,
    destino: Path = PASTA_RAW,
) -> int:
    """Ingere uma tabela de origem/<tabela>.csv para destino/<tabela>.parquet.

    Retorna o número de linhas gravadas.
    """
    encoding, colunas = TABELAS_FONTE[tabela]
    df = ler_csv(origem / f"{tabela}.csv", encoding)
    validar_colunas(df, colunas, tabela)
    salvar_parquet(df, destino / f"{tabela}.parquet")
    return len(df)


def ingerir_tudo(origem: Path = PASTA_FONTE, destino: Path = PASTA_RAW) -> dict[str, int]:
    """Ingere todas as tabelas de TABELAS_FONTE e retorna {tabela: linhas}."""
    return {t: ingerir_tabela(t, origem, destino) for t in TABELAS_FONTE}


if __name__ == "__main__":
    for nome, linhas in ingerir_tudo().items():
        print(f"{nome}: {linhas} linhas")
