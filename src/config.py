"""Caminhos e parâmetros do pipeline."""

from pathlib import Path

RAIZ: Path = Path(__file__).resolve().parent.parent
PASTA_DADOS: Path = RAIZ / "data"
PASTA_FONTE: Path = PASTA_DADOS / "fonte"
PASTA_RAW: Path = PASTA_DADOS / "raw"
PASTA_REFINED: Path = PASTA_DADOS / "refined"
PASTA_GOLD: Path = PASTA_DADOS / "gold"
PASTA_SQL_GOLD: Path = RAIZ / "sql" / "gold"

# KPIs da gold, na ordem em que são gerados; cada um tem sql/gold/<nome>.sql
TABELAS_GOLD: list[str] = [
    "resumo_geral", "vendas_mensais", "vendas_por_categoria", "ranking_pizzas",
    "vendas_por_tamanho", "pedidos_por_hora", "pedidos_por_dia_semana",
]

# tabela -> (encoding do CSV, colunas esperadas na ordem da fonte)
TABELAS_FONTE: dict[str, tuple[str, list[str]]] = {
    "orders": ("utf-8", ["order_id", "date", "time"]),
    "order_details": ("utf-8", ["order_details_id", "order_id", "pizza_id", "quantity"]),
    "pizzas": ("utf-8", ["pizza_id", "pizza_type_id", "size", "price"]),
    # tem um 0x91 (aspa ‘ do Windows) em "‘Nduja": não é utf-8
    "pizza_types": ("cp1252", ["pizza_type_id", "name", "category", "ingredients"]),
}
