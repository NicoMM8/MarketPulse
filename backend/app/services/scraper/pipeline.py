"""
Pipeline de ingestión de noticias financieras.
Orquesta la extracción desde múltiples fuentes (Yahoo Finance, Investing.com)
y su almacenamiento idempotente en la base de datos a través de ArticleRepository.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import ArticleRepository
from app.schemas.article import ArticleCreate
from app.services.scraper.base import BaseScraper
from app.services.scraper.investing import InvestingScraper
from app.services.scraper.yahoo import YahooFinanceScraper

logger = logging.getLogger("marketpulse.pipeline")


@dataclass
class IngestionStats:
    """Estructura de métricas para auditar los resultados de una ejecución del pipeline."""
    total_scraped: int = 0
    new_inserted: int = 0
    duplicates_skipped: int = 0
    duration_seconds: float = 0.0
    by_source: dict[str, int] = field(default_factory=dict)
    tickers_detected: set[str] = field(default_factory=set)


class NewsIngestionPipeline:
    """
    Coordina los scrapers activos, normaliza el flujo de noticias
    y gestiona la inserción en base de datos sin duplicar registros.
    """

    def __init__(
        self,
        scrapers: Optional[list[BaseScraper]] = None,
        default_limit: int = 20,
    ):
        # Si no se pasan scrapers a medida, usamos los dos portales configurados
        self.scrapers = scrapers or [
            YahooFinanceScraper(),
            InvestingScraper()
        ]
        self.default_limit = default_limit

    async def _process_article(
        self,
        repo: ArticleRepository,
        article_in: ArticleCreate,
        stats: IngestionStats
    ) -> bool:
        """Intenta guardar una noticia en la base de datos y actualiza los contadores."""
        try:
            _, created = await repo.create_if_not_exists(article_in)

            if created:
                stats.new_inserted += 1
            else:
                stats.duplicates_skipped += 1

            # Contabilizamos por portal de procedencia
            stats.by_source[article_in.source] = stats.by_source.get(article_in.source, 0) + 1

            # Registramos los tickers que han aparecido
            for t in article_in.tickers:
                stats.tickers_detected.add(t)

            return created

        except Exception as err:
            logger.error(f"Error al guardar noticia '{article_in.title[:40]}': {err}")
            return False

    async def run(
        self,
        session: AsyncSession,
        limit_per_source: Optional[int] = None
    ) -> IngestionStats:
        """
        Ejecuta todos los extractores, persiste las noticias en la base de datos
        y devuelve el resumen con las estadísticas de la sesión.
        """
        start_time = time.time()
        stats = IngestionStats()
        repo = ArticleRepository(session)
        limit = limit_per_source or self.default_limit

        logger.info(f"Iniciando pipeline de ingestión con {len(self.scrapers)} extractores...")

        for scraper in self.scrapers:
            logger.info(f"Lanzando extractor: {scraper.source_name} (límite: {limit})")
            try:
                articles = await scraper.fetch_articles(limit=limit)
                stats.total_scraped += len(articles)

                # Guardamos cada noticia en la base de datos
                for article in articles:
                    await self._process_article(repo, article, stats)

            except Exception as err:
                # Si un scraper falla por red o captcha, no rompemos el resto del pipeline
                logger.error(f"Error crítico en extractor {scraper.source_name}: {err}")
                continue

        stats.duration_seconds = round(time.time() - start_time, 2)
        logger.info(
            f"Pipeline finalizado en {stats.duration_seconds}s. "
            f"Nuevas: {stats.new_inserted}, Duplicadas: {stats.duplicates_skipped}"
        )

        return stats

    async def run_single(
        self,
        session: AsyncSession,
        source_name: str,
        limit: Optional[int] = None
    ) -> IngestionStats:
        """Permite ejecutar únicamente un scraper concreto por su nombre (ej: 'yahoo_finance')."""
        target_scrapers = [s for s in self.scrapers if s.source_name == source_name]

        if not target_scrapers:
            raise ValueError(f"No hay ningún extractor registrado con el nombre '{source_name}'")

        pipeline_individual = NewsIngestionPipeline(
            scrapers=target_scrapers,
            default_limit=limit or self.default_limit
        )

        return await pipeline_individual.run(session, limit_per_source=limit)

