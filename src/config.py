"""Caminhos e parâmetros do pipeline."""

from pathlib import Path

RAIZ: Path = Path(__file__).resolve().parent.parent
PASTA_DADOS: Path = RAIZ / "data"
PASTA_FONTE: Path = PASTA_DADOS / "fonte"
PASTA_RAW: Path = PASTA_DADOS / "raw"
PASTA_REFINED: Path = PASTA_DADOS / "refined"
PASTA_GOLD: Path = PASTA_DADOS / "gold"

# tabela -> (encoding do CSV, colunas esperadas na ordem da fonte)
TABELAS_FONTE: dict[str, tuple[str, list[str]]] = {
    "orders": ("utf-8", ["order_id", "date", "time"]),
    "order_details": ("utf-8", ["order_details_id", "order_id", "pizza_id", "quantity"]),
    "pizzas": ("utf-8", ["pizza_id", "pizza_type_id", "size", "price"]),
    # tem um 0x91 (aspa ‘ do Windows) em "‘Nduja": não é utf-8
    "pizza_types": ("cp1252", ["pizza_type_id", "name", "category", "ingredients"]),
}
