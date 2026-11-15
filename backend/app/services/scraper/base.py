"""
Clase base abstracta para todos los scrapers de noticias financieras.
Define la interfaz estándar y utilidades comunes como cabeceras HTTP y gestión de pausas.
"""

from abc import ABC, abstractmethod
import logging
from typing import Optional

from app.schemas.article import ArticleCreate

logger = logging.getLogger("marketpulse.scraper")


class BaseScraper(ABC):
    """Interfaz base para extractores de información financiera."""

    def __init__(self, source_name: str, base_url: str):
        self.source_name = source_name
        self.base_url = base_url

    def get_default_headers(self) -> dict[str, str]:
        """Cabeceras HTTP estándar simulando un navegador real para evitar bloqueos 403."""
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    @abstractmethod
    async def fetch_articles(self, limit: int = 20) -> list[ArticleCreate]:
        """
        Método obligatorio a implementar por cada scraper específico.
        Tendría que devolver una lista de instancias validadas de ArticleCreate.
        """
        pass
