"""Módulo de scrapers y pipeline de ingestión de noticias financieras."""

from app.services.scraper.base import BaseScraper
from app.services.scraper.investing import InvestingScraper
from app.services.scraper.pipeline import IngestionStats, NewsIngestionPipeline
from app.services.scraper.yahoo import YahooFinanceScraper

__all__ = [
    "BaseScraper",
    "YahooFinanceScraper",
    "InvestingScraper",
    "NewsIngestionPipeline",
    "IngestionStats"
]
