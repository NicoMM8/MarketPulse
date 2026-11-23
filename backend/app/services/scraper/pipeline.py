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
        default_limit: int = 20
    ):
        # Si no se pasan scrapers a medida, usamos los dos portales configurados
        self.scrapers = scrapers or [
            YahooFinanceScraper(),
            InvestingScraper()
        ]
        self.default_limit = default_limit

