"""Testes da gold (spec 03). Montam uma itens_pedido pequena em pasta temporária."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from src import agregacao
from src.agregacao import agregar_tudo, carregar_consultas
from src.config import PASTA_SQL_GOLD, TABELAS_GOLD

# 3 pedidos: 2 em jan (quinta 01/01 e sexta 02/01), 1 em fev (segunda 02/02)
ITENS = """
    SELECT * FROM (VALUES
        (1, 1, DATE '2015-01-01', TIME '11:30:00', 'Hawaiian', 'Classic', 'M', 1, 13.25),
        (2, 1, DATE '2015-01-01', TIME '11:30:00', 'Greek',    'Classic', 'XL', 2, 25.50),
        (3, 2, DATE '2015-01-02', TIME '18:10:00', 'Veggie',   'Veggie',  'S', 1, 12.00),
        (4, 3, DATE '2015-02-02', TIME '18:45:00', 'Hawaiian', 'Classic', 'M', 3, 13.25)
    ) AS t(id_detalhe, id_pedido, data, hora, nome_pizza, categoria, tamanho, quantidade, preco)
"""


@pytest.fixture
def refined(tmp_path: Path) -> Path:
    """Grava refined/itens_pedido.parquet com os tipos da camada refined."""
    pasta = tmp_path / "refined"
    pasta.mkdir()
    con = duckdb.connect()
    con.execute(f"""
        COPY (SELECT id_detalhe::INTEGER AS id_detalhe, id_pedido::INTEGER AS id_pedido,
                     data, hora, nome_pizza, categoria, tamanho,
                     quantidade::INTEGER AS quantidade,
                     preco::DECIMAL(10,2) AS preco,
                     (quantidade * preco)::DECIMAL(10,2) AS valor_item
              FROM ({ITENS}))
        TO '{(pasta / "itens_pedido.parquet").as_posix()}' (FORMAT parquet)
    """)
    con.close()
    return pasta


def ler(pasta: Path, tabela: str) -> list[tuple]:
    """Lê todas as linhas de um Parquet da gold."""
    con = duckdb.connect()
    linhas = con.execute(f"SELECT * FROM '{(pasta / f'{tabela}.parquet').as_posix()}'").fetchall()
    con.close()
    return linhas


def test_contagens_de_linhas(refined, tmp_path):
    """A4: uma tabela por KPI, com o grão esperado."""
    assert agregar_tudo(refined, tmp_path / "gold") == {
        "resumo_geral": 1, "vendas_mensais": 2, "vendas_por_categoria": 2,
        "ranking_pizzas": 3, "vendas_por_tamanho": 3, "pedidos_por_hora": 2,
        "pedidos_por_dia_semana": 3,
    }


def test_resumo_geral(refined, tmp_path):
    """Faturamento 13,25 + 51,00 + 12,00 + 39,75 = 116,00; 3 pedidos; 7 pizzas."""
    agregar_tudo(refined, tmp_path / "gold")
    assert ler(tmp_path / "gold", "resumo_geral") == [
        (Decimal("116.00"), 3, 7, Decimal("38.67"), Decimal("2.33"))
    ]


def test_vendas_mensais(refined, tmp_path):
    agregar_tudo(refined, tmp_path / "gold")
    assert ler(tmp_path / "gold", "vendas_mensais") == [
        (date(2015, 1, 1), 2, 4, Decimal("76.25"), Decimal("38.13")),
        (date(2015, 2, 1), 1, 3, Decimal("39.75"), Decimal("39.75")),
    ]


def test_categoria_com_participacao(refined, tmp_path):
    agregar_tudo(refined, tmp_path / "gold")
    assert ler(tmp_path / "gold", "vendas_por_categoria") == [
        ("Classic", 6, Decimal("104.00"), Decimal("89.66")),
        ("Veggie", 1, Decimal("12.00"), Decimal("10.34")),
    ]


def test_ranking_pizzas(refined, tmp_path):
    """Hawaiian: 4 un. e 53,00; Greek: 2 un. e 51,00; Veggie: 1 un. e 12,00."""
    agregar_tudo(refined, tmp_path / "gold")
    assert ler(tmp_path / "gold", "ranking_pizzas") == [
        ("Hawaiian", "Classic", 4, Decimal("53.00"), 1, 1),
        ("Greek", "Classic", 2, Decimal("51.00"), 2, 2),
        ("Veggie", "Veggie", 1, Decimal("12.00"), 3, 3),
    ]


def test_pizzas_vendidas_e_inteiro(refined, tmp_path):
    """Soma de quantidade não pode virar 7.0 (DOUBLE/HUGEINT)."""
    agregar_tudo(refined, tmp_path / "gold")
    con = duckdb.connect()
    for tabela in ["resumo_geral", "vendas_mensais", "vendas_por_categoria",
                   "ranking_pizzas", "vendas_por_tamanho"]:
        caminho = (tmp_path / "gold" / f"{tabela}.parquet").as_posix()
        tipo = con.execute(
            f"SELECT column_type FROM (DESCRIBE SELECT * FROM '{caminho}') "
            "WHERE column_name = 'pizzas_vendidas'"
        ).fetchone()[0]
        assert tipo == "INTEGER", tabela
    con.close()


def test_tamanhos_em_ordem_e_nao_alfabetica(refined, tmp_path):
    """A3: S, M, XL (alfabética seria M, S, XL)."""
    agregar_tudo(refined, tmp_path / "gold")
    assert [linha[0] for linha in ler(tmp_path / "gold", "vendas_por_tamanho")] == ["S", "M", "XL"]


def test_hora_e_dia_da_semana(refined, tmp_path):
    agregar_tudo(refined, tmp_path / "gold")
    assert ler(tmp_path / "gold", "pedidos_por_hora") == [
        (11, 1, Decimal("64.25")), (18, 2, Decimal("51.75")),
    ]
    dias = ler(tmp_path / "gold", "pedidos_por_dia_semana")
    assert [(d[0], d[1], d[2]) for d in dias] == [(1, "segunda", 1), (4, "quinta", 1), (5, "sexta", 1)]


def test_cada_kpi_tem_seu_arquivo_sql():
    """Um .sql por KPI em sql/gold/, nem a mais nem a menos."""
    arquivos = sorted(p.stem for p in PASTA_SQL_GOLD.glob("*.sql"))
    assert arquivos == sorted(TABELAS_GOLD)
    assert list(agregacao.CONSULTAS_GOLD) == TABELAS_GOLD


def test_kpi_sem_sql_para_o_pipeline(tmp_path):
    """Se faltar o .sql de um KPI, o erro diz qual arquivo falta."""
    (tmp_path / "resumo_geral.sql").write_text("SELECT 1", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="vendas_mensais.sql"):
        carregar_consultas(tmp_path, ["resumo_geral", "vendas_mensais"])


def test_total_que_nao_fecha_para_o_pipeline(refined, tmp_path, monkeypatch):
    """N1: um KPI que perde linhas não pode ser gravado."""
    consultas = dict(agregacao.CONSULTAS_GOLD)
    consultas["vendas_por_tamanho"] = consultas["vendas_por_tamanho"].replace(
        "FROM itens_pedido", "FROM itens_pedido WHERE tamanho <> 'S'"
    )
    monkeypatch.setattr(agregacao, "CONSULTAS_GOLD", consultas)
    with pytest.raises(ValueError, match="vendas_por_tamanho.faturamento"):
        agregar_tudo(refined, tmp_path / "gold")
    assert not (tmp_path / "gold").exists()
