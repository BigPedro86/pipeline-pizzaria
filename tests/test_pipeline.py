"""Testes da orquestração (spec 04): ponta a ponta com CSVs pequenos."""

import logging
from pathlib import Path

import pytest

from src import pipeline
from src.config import TABELAS_FONTE

CSVS = {
    "orders": "order_id,date,time\r\n1,2015-01-01,11:38:36\r\n2,2015-01-02,18:05:00\r\n",
    "order_details": "order_details_id,order_id,pizza_id,quantity\r\n"
    "1,1,hawaiian_m,1\r\n2,2,hawaiian_m,2\r\n",
    "pizzas": "pizza_id,pizza_type_id,size,price\r\nhawaiian_m,hawaiian,M,13.25\r\n",
    "pizza_types": "pizza_type_id,name,category,ingredients\r\n"
    'hawaiian,The Hawaiian Pizza,Classic,"‘Ham, Pineapple"\r\n',
}


@pytest.fixture
def pastas(tmp_path: Path) -> dict[str, Path]:
    """Cria data/fonte com os CSVs e devolve os caminhos das 4 pastas."""
    fonte = tmp_path / "fonte"
    fonte.mkdir()
    for tabela, texto in CSVS.items():
        (fonte / f"{tabela}.csv").write_bytes(texto.encode(TABELAS_FONTE[tabela][0]))
    return {nome: tmp_path / nome for nome in ["fonte", "raw", "refined", "gold"]}


def test_ponta_a_ponta(pastas):
    """A1, A5: as três etapas rodam e geram as três camadas."""
    resultado = pipeline.executar_pipeline(**pastas)
    assert list(resultado) == ["ingestao", "transformacao", "agregacao"]
    assert resultado["transformacao"]["itens_pedido"] == 2
    assert resultado["agregacao"]["resumo_geral"] == 1
    assert len(list(pastas["gold"].glob("*.parquet"))) == 7


def test_log_de_cada_etapa(pastas, caplog):
    """A2: início, linhas e fim de cada etapa aparecem no log."""
    with caplog.at_level(logging.INFO, logger="pipeline"):
        pipeline.executar_pipeline(**pastas)
    texto = caplog.text
    for etapa in ["ingestão", "transformação", "agregação"]:
        assert f"Início: {etapa}" in texto
        assert f"Fim: {etapa}" in texto
    assert "itens_pedido: 2 linhas" in texto


def test_falha_interrompe_etapas_seguintes(pastas):
    """N1: sem um CSV, a ingestão falha e refined/gold não são criadas."""
    (pastas["fonte"] / "pizzas.csv").unlink()
    with pytest.raises(FileNotFoundError):
        pipeline.executar_pipeline(**pastas)
    assert not pastas["refined"].exists()
    assert not pastas["gold"].exists()


def test_main_retorna_0_em_sucesso(monkeypatch, caplog):
    """A4."""
    monkeypatch.setattr(pipeline, "executar_pipeline", lambda: {})
    with caplog.at_level(logging.INFO, logger="pipeline"):
        assert pipeline.main() == 0
    assert "Pipeline concluído" in caplog.text


def test_main_retorna_1_e_registra_erro(monkeypatch, caplog):
    """N2: o erro vai para o log com traceback e o código de saída é 1."""

    def falhar() -> None:
        raise ValueError("pizzas: colunas esperadas")

    monkeypatch.setattr(pipeline, "executar_pipeline", falhar)
    with caplog.at_level(logging.INFO, logger="pipeline"):
        assert pipeline.main() == 1
    erro = [r for r in caplog.records if r.levelno == logging.ERROR][0]
    assert erro.exc_info is not None
    assert "Pipeline interrompido" in erro.getMessage()
