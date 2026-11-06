"""Orquestra o pipeline completo: fonte -> raw -> refined -> gold.

Uso: python -m src.pipeline
"""

import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path

from src.agregacao import agregar_tudo
from src.config import PASTA_FONTE, PASTA_GOLD, PASTA_RAW, PASTA_REFINED
from src.ingestao import ingerir_tudo
from src.transformacao import transformar_tudo

log = logging.getLogger("pipeline")


def configurar_logging(nivel: int = logging.INFO) -> None:
    """Configura o log no terminal no formato 'data hora | NIVEL | mensagem'."""
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def executar_etapa(
    nome: str, funcao: Callable[[Path, Path], dict[str, int]], origem: Path, destino: Path
) -> dict[str, int]:
    """Roda uma etapa, registra as linhas de cada tabela e o tempo gasto."""
    log.info("Início: %s (%s -> %s)", nome, origem.name, destino.name)
    inicio = time.perf_counter()
    contagens = funcao(origem, destino)
    for tabela, linhas in contagens.items():
        log.info("  %s: %s linhas", tabela, f"{linhas:,}".replace(",", "."))
    log.info("Fim: %s em %.2f s", nome, time.perf_counter() - inicio)
    return contagens


def executar_pipeline(
    fonte: Path = PASTA_FONTE,
    raw: Path = PASTA_RAW,
    refined: Path = PASTA_REFINED,
    gold: Path = PASTA_GOLD,
) -> dict[str, dict[str, int]]:
    """Executa as três etapas em ordem; uma falha interrompe as seguintes."""
    return {
        "ingestao": executar_etapa("ingestão", ingerir_tudo, fonte, raw),
        "transformacao": executar_etapa("transformação", transformar_tudo, raw, refined),
        "agregacao": executar_etapa("agregação", agregar_tudo, refined, gold),
    }


def main() -> int:
    """Ponto de entrada do comando: retorna 0 em sucesso e 1 em falha."""
    configurar_logging()
    inicio = time.perf_counter()
    try:
        executar_pipeline()
    except Exception:
        log.exception("Pipeline interrompido por erro")
        return 1
    log.info("Pipeline concluído em %.2f s", time.perf_counter() - inicio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
