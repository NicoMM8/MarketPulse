"""
Script ejecutable de consola para lanzar el pipeline de extracción de noticias financieras.
Permite configurar el límite de artículos por fuente y seleccionar portales específicos.
Uso:
    python run_scraper.py --source all --limit 10
    python run_scraper.py --source yahoo --limit 5
    python run_scraper.py --init-db
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Añadimos la raíz del backend al path para poder importar app.*
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import async_session_factory, init_db
from app.services.scraper.investing import InvestingScraper
from app.services.scraper.pipeline import IngestionStats, NewsIngestionPipeline
from app.services.scraper.yahoo import YahooFinanceScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("marketpulse.cli")


def parse_args() -> argparse.Namespace:
    """Configura y parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="MarketPulse CLI — Extracción automatizada de noticias financieras."
    )

    parser.add_argument(
        "--source",
        choices=["all", "yahoo", "investing"],
        default="all",
        help="Portal financiero a consultar (por defecto: all)."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Límite de noticias a extraer por cada portal (por defecto: 15)."
    )

    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Inicializa las tablas de la base de datos antes de ejecutar."
    )

    return parser.parse_args()


def print_summary(stats: IngestionStats) -> None:
    """Imprime un resumen formateado y limpio con los resultados de la ejecución."""
    tickers_str = ", ".join(sorted(list(stats.tickers_detected))) if stats.tickers_detected else "Ninguno detectado"

    print("\n" + "=" * 60)
    print("           RESUMEN DE INGESTIÓN — MARKETPULSE")
    print("=" * 60)
    print(f"  • Total noticias procesadas:  {stats.total_scraped}")
    print(f"  • Nuevas guardadas en BD:     {stats.new_inserted}")
    print(f"  • Duplicadas (descartadas):   {stats.duplicates_skipped}")
    print(f"  • Tiempo de ejecución:        {stats.duration_seconds} segundos")
    print("-" * 60)
    print("  Desglose por portal:")
    for source, count in stats.by_source.items():
        print(f"    - {source}: {count} artículos")
    print("-" * 60)
    print(f"  Tickers detectados ({len(stats.tickers_detected)}):")
    print(f"    {tickers_str}")
    print("=" * 60 + "\n")


async def main():
    args = parse_args()

    # Si se pide inicializar tablas en SQLite
    if args.init_db:
        logger.info("Inicializando tablas en la base de datos...")
        await init_db()
        logger.info("Base de datos lista.")

    # Selección de scrapers según el argumento --source
    scrapers = []
    if args.source in ["all", "yahoo"]:
        scrapers.append(YahooFinanceScraper())
    if args.source in ["all", "investing"]:
        scrapers.append(InvestingScraper())

    pipeline = NewsIngestionPipeline(scrapers=scrapers, default_limit=args.limit)

    async with async_session_factory() as session:
        stats = await pipeline.run(session=session, limit_per_source=args.limit)
        print_summary(stats)


if __name__ == "__main__":
    asyncio.run(main())
