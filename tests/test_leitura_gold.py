"""Testes da leitura da gold usada pelo painel."""

import pytest

from src.agregacao import agregar_tudo
from src.leitura_gold import formatar_moeda, formatar_numero, gold_disponivel, ler_gold
from tests.test_agregacao import refined  # noqa: F401  (fixture reaproveitada)


def test_gold_ausente(tmp_path):
    assert gold_disponivel(tmp_path) is False


def test_ler_gold_depois_do_pipeline(refined, tmp_path):  # noqa: F811
    agregar_tudo(refined, tmp_path / "gold")
    assert gold_disponivel(tmp_path / "gold") is True
    resumo = ler_gold("resumo_geral", tmp_path / "gold")
    assert resumo.faturamento.iloc[0] == pytest.approx(116.00)
    assert list(ler_gold("vendas_por_tamanho", tmp_path / "gold").tamanho) == ["S", "M", "XL"]


def test_tabela_desconhecida(tmp_path):
    with pytest.raises(ValueError, match="desconhecida"):
        ler_gold("nao_existe", tmp_path)


def test_formatos_brasileiros():
    assert formatar_numero(21350) == "21.350"
    assert formatar_numero(2.3248, 2) == "2,32"
    assert formatar_moeda(817860.05) == "$ 817.860,05"
