"""Testes da transformação (spec 02). Montam uma raw pequena em pasta temporária."""

from decimal import Decimal
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from src.config import TABELAS_FONTE
from src.ingestao import salvar_parquet
from src.transformacao import transformar_tudo

RAW_BASE: dict[str, list[list[str]]] = {
    "orders": [["1", "2015-01-01", "11:38:36"], ["2", "2015-01-02", "18:05:00"]],
    "order_details": [["1", "1", "hawaiian_m", "1"], ["2", "2", "hawaiian_m", "2"],
                      ["3", "2", "the_greek_xl", "1"]],
    "pizzas": [["hawaiian_m", "hawaiian", "M", "13.25"], ["the_greek_xl", "the_greek", "XL", "25.5"]],
    "pizza_types": [["hawaiian", "The Hawaiian Pizza", "Classic", "Pineapple"],
                    ["the_greek", "The Greek Pizza", "Classic", "Feta"]],
}


def montar_raw(pasta: Path, alteracoes: dict[str, list[list[str]]] | None = None) -> Path:
    """Grava a raw de teste (tudo texto), trocando as tabelas indicadas em alteracoes."""
    dados = {**RAW_BASE, **(alteracoes or {})}
    for tabela, linhas in dados.items():
        df = pd.DataFrame(linhas, columns=TABELAS_FONTE[tabela][1], dtype=str)
        salvar_parquet(df, pasta / f"{tabela}.parquet")
    return pasta


def consultar(caminho: Path, sql: str = "SELECT * FROM t") -> list[tuple]:
    """Roda uma consulta num Parquet exposto como t."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW t AS SELECT * FROM '{caminho.as_posix()}'")
    resultado = con.execute(sql).fetchall()
    con.close()
    return resultado


def test_contagens_e_join_sem_perda(tmp_path):
    """A2, A3, A6."""
    contagens = transformar_tudo(montar_raw(tmp_path / "raw"), tmp_path / "refined")
    assert contagens == {"pedidos": 2, "detalhes_pedido": 3, "pizzas": 2,
                         "tipos_pizza": 2, "itens_pedido": 3}


def test_tipos_e_nomes_em_portugues(tmp_path):
    """A1 e D4A."""
    transformar_tudo(montar_raw(tmp_path / "raw"), tmp_path / "refined")
    tipos = dict(consultar(tmp_path / "refined" / "itens_pedido.parquet",
                           "SELECT column_name, column_type FROM (DESCRIBE t)"))
    assert tipos == {
        "id_detalhe": "INTEGER", "id_pedido": "INTEGER", "data": "DATE", "hora": "TIME",
        "id_pizza": "VARCHAR", "id_tipo_pizza": "VARCHAR", "nome_pizza": "VARCHAR",
        "categoria": "VARCHAR", "tamanho": "VARCHAR", "quantidade": "INTEGER",
        "preco": "DECIMAL(10,2)", "valor_item": "DECIMAL(10,2)",
    }


def test_valor_item_e_quantidade_vezes_preco(tmp_path):
    """A4: 1×13,25 + 2×13,25 + 1×25,50 = 65,25."""
    transformar_tudo(montar_raw(tmp_path / "raw"), tmp_path / "refined")
    total = consultar(tmp_path / "refined" / "itens_pedido.parquet",
                      "SELECT sum(valor_item) FROM t")[0][0]
    assert total == Decimal("65.25")


def test_rodar_duas_vezes_da_o_mesmo_resultado(tmp_path):
    """A5."""
    raw = montar_raw(tmp_path / "raw")
    primeira = transformar_tudo(raw, tmp_path / "refined")
    assert transformar_tudo(raw, tmp_path / "refined") == primeira


def test_valor_invalido_para_o_pipeline(tmp_path):
    """N1: CAST falha em data inválida (com TRY_CAST viraria nulo em silêncio)."""
    raw = montar_raw(tmp_path / "raw", {"orders": [["1", "2015-13-01", "11:38:36"],
                                                   ["2", "2015-01-02", "18:05:00"]]})
    with pytest.raises(duckdb.ConversionException):
        transformar_tudo(raw, tmp_path / "refined")


def test_nulo_para_o_pipeline(tmp_path):
    """N2: campo vazio vira NULL no CAST e deve parar."""
    raw = montar_raw(tmp_path / "raw", {"pizza_types": [
        ["hawaiian", "The Hawaiian Pizza", "Classic", "Pineapple"],
        ["the_greek", "The Greek Pizza", None, "Feta"]]})
    with pytest.raises(ValueError, match="nulos"):
        transformar_tudo(raw, tmp_path / "refined")


def test_chave_duplicada_para_o_pipeline(tmp_path):
    """N3."""
    raw = montar_raw(tmp_path / "raw", {"orders": [["1", "2015-01-01", "11:38:36"],
                                                   ["1", "2015-01-02", "18:05:00"],
                                                   ["2", "2015-01-02", "18:05:00"]]})
    with pytest.raises(ValueError, match="repetido"):
        transformar_tudo(raw, tmp_path / "refined")


def test_item_sem_pizza_para_o_pipeline(tmp_path):
    """N4: item aponta para pizza que não existe -> JOIN perderia a linha."""
    raw = montar_raw(tmp_path / "raw", {"order_details": [
        ["1", "1", "hawaiian_m", "1"], ["2", "2", "pizza_fantasma", "1"]]})
    with pytest.raises(ValueError, match="JOIN perdeu 1"):
        transformar_tudo(raw, tmp_path / "refined")


def test_falha_nao_grava_refined(tmp_path):
    """Se uma validação falha, nenhum Parquet da refined é gravado."""
    raw = montar_raw(tmp_path / "raw", {"order_details": [
        ["1", "1", "pizza_fantasma", "1"]]})
    with pytest.raises(ValueError):
        transformar_tudo(raw, tmp_path / "refined")
    assert not (tmp_path / "refined").exists()
