"""Testes da ingestão (spec 01). Usam CSVs pequenos em pasta temporária."""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from src.config import TABELAS_FONTE
from src.ingestao import ingerir_tabela, ingerir_tudo, ler_csv, validar_colunas

CSVS = {
    "orders": "order_id,date,time\r\n1,2015-01-01,11:38:36\r\n2,2015-01-01,11:57:40\r\n",
    "order_details": "order_details_id,order_id,pizza_id,quantity\r\n1,1,hawaiian_m,1\r\n2,2,NA,\r\n",
    "pizzas": "pizza_id,pizza_type_id,size,price\r\nhawaiian_m,hawaiian,M,013.25\r\n",
    "pizza_types": 'pizza_type_id,name,category,ingredients\r\n'
    'calabrese,The Calabrese Pizza,Supreme,"‘Nduja Salami, Garlic"\r\n',
}


@pytest.fixture
def origem(tmp_path: Path) -> Path:
    """Cria os 4 CSVs de teste com o mesmo encoding da fonte real."""
    pasta = tmp_path / "fonte"
    pasta.mkdir()
    for tabela, texto in CSVS.items():
        encoding = TABELAS_FONTE[tabela][0]
        (pasta / f"{tabela}.csv").write_bytes(texto.encode(encoding))
    return pasta


def ler_parquet(caminho: Path) -> tuple[list[tuple[str, str]], list[tuple]]:
    """Lê um Parquet e devolve [(coluna, tipo)] e as linhas."""
    con = duckdb.connect()
    linhas = con.execute(f"SELECT * FROM '{caminho.as_posix()}'").fetchall()
    tipos = con.execute(f"DESCRIBE SELECT * FROM '{caminho.as_posix()}'").fetchall()
    con.close()
    return [(t[0], t[1]) for t in tipos], linhas


def test_raw_tem_mesmas_linhas_colunas_e_tudo_varchar(origem, tmp_path):
    """A1, A2, A3, A7."""
    contagens = ingerir_tudo(origem, tmp_path / "raw")
    assert contagens == {"orders": 2, "order_details": 2, "pizzas": 1, "pizza_types": 1}
    for tabela, (_, colunas) in TABELAS_FONTE.items():
        tipos, _ = ler_parquet(tmp_path / "raw" / f"{tabela}.parquet")
        assert [c for c, _ in tipos] == colunas
        assert {t for _, t in tipos} == {"VARCHAR"}


def test_valores_ficam_como_texto_da_fonte(origem, tmp_path):
    """A4: "NA", vazio e zero à esquerda não são convertidos."""
    ingerir_tudo(origem, tmp_path / "raw")
    _, itens = ler_parquet(tmp_path / "raw" / "order_details.parquet")
    assert itens[1] == ("2", "2", "NA", "")
    _, pizzas = ler_parquet(tmp_path / "raw" / "pizzas.parquet")
    assert pizzas[0][3] == "013.25"


def test_pizza_types_decodifica_cp1252(origem, tmp_path):
    """A5: o 0x91 vira ‘ e não um caractere quebrado."""
    ingerir_tabela("pizza_types", origem, tmp_path / "raw")
    _, linhas = ler_parquet(tmp_path / "raw" / "pizza_types.parquet")
    assert linhas[0][3].startswith("‘Nduja")


def test_rodar_duas_vezes_nao_acumula(origem, tmp_path):
    """A6."""
    ingerir_tabela("orders", origem, tmp_path / "raw")
    ingerir_tabela("orders", origem, tmp_path / "raw")
    _, linhas = ler_parquet(tmp_path / "raw" / "orders.parquet")
    assert len(linhas) == 2


def test_nao_altera_arquivos_da_fonte(origem, tmp_path):
    """N2."""
    antes = {p.name: p.read_bytes() for p in origem.iterdir()}
    ingerir_tudo(origem, tmp_path / "raw")
    assert {p.name: p.read_bytes() for p in origem.iterdir()} == antes


def test_csv_ausente_para_o_pipeline(origem, tmp_path):
    """N3: falta de arquivo."""
    (origem / "pizzas.csv").unlink()
    with pytest.raises(FileNotFoundError):
        ingerir_tudo(origem, tmp_path / "raw")


def test_coluna_diferente_para_o_pipeline():
    """N3: coluna faltando ou trocada."""
    df = pd.DataFrame(columns=["order_id", "date"])
    with pytest.raises(ValueError, match="orders"):
        validar_colunas(df, ["order_id", "date", "time"], "orders")


def test_encoding_errado_para_o_pipeline(origem):
    """N4: ler o cp1252 como utf-8 tem que falhar."""
    with pytest.raises(UnicodeDecodeError):
        ler_csv(origem / "pizza_types.csv", "utf-8")
