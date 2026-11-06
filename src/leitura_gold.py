"""Leitura da camada gold e formatação de valores para o painel."""

from pathlib import Path

import duckdb
import pandas as pd

from src.agregacao import CONSULTAS_GOLD
from src.config import PASTA_GOLD


def gold_disponivel(pasta: Path = PASTA_GOLD) -> bool:
    """Indica se todas as tabelas da gold já foram geradas."""
    return all((pasta / f"{t}.parquet").exists() for t in CONSULTAS_GOLD)


def ler_gold(tabela: str, pasta: Path = PASTA_GOLD) -> pd.DataFrame:
    """Lê uma tabela da gold como DataFrame (DECIMAL vira float)."""
    if tabela not in CONSULTAS_GOLD:
        raise ValueError(f"tabela desconhecida na gold: {tabela}")
    caminho = (pasta / f"{tabela}.parquet").as_posix()
    con = duckdb.connect()
    try:
        return con.execute(f"SELECT * FROM '{caminho}'").df()
    finally:
        con.close()


def formatar_numero(valor: float, casas: int = 0) -> str:
    """Formata no padrão brasileiro: 21350 -> '21.350'; 38.31 -> '38,31'."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_moeda(valor: float) -> str:
    """Formata dinheiro em dólar (moeda do dataset): 817860.05 -> '$ 817.860,05'."""
    return f"$ {formatar_numero(valor, 2)}"
