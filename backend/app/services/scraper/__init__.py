"""Módulo de scrapers y extractores de noticias financieras."""

from app.services.scraper.base import BaseScraper
from app.services.scraper.yahoo import YahooFinanceScraper

__all__ = ["BaseScraper", "YahooFinanceScraper"]
