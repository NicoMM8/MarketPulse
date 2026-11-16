"""
Extractor de noticias financieras para Yahoo Finance.
Utiliza peticiones HTTP asíncronas con httpx y gestión de reintentos con backoff exponencial.
"""

import asyncio
import logging
from typing import Optional
import httpx

from app.services.scraper.base import BaseScraper, logger


class YahooFinanceScraper(BaseScraper):
    """Extractor asíncrono de noticias financieras desde Yahoo Finance."""

    def __init__(self, base_url: str = "https://finance.yahoo.com"):
        super().__init__(source_name="yahoo_finance", base_url=base_url)
        self.news_url = f"{self.base_url}/news/"
        self.timeout = 10.0
        self.max_retries = 3

    async def fetch_html(self, url: str) -> Optional[str]:
        """
        Descarga el contenido HTML de una URL con reintentos automáticos
        y control de pausas para no saturar al servidor.
        """
        headers = self.get_default_headers()

        # Usamos cliente asincrono con soporte para redirecciones
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info(f"Intentando descargar {url} (intento {attempt}/{self.max_retries})")
                    response = await client.get(url, headers=headers)

                    if response.status_code == 200:
                        return response.text

                    # Si nos devuelven un 429 (rate limit) o 5xx, esperamos un poco antes de reintentar
                    logger.warning(
                        f"Respuesta no exitosa de Yahoo Finance: {response.status_code} en intento {attempt}"
                    )

                except (httpx.RequestError, httpx.TimeoutException) as exc:
                    logger.warning(f"Error de conexion con {url}: {exc} (intento {attempt})")

                # Pausa exponencial: 1s, 2s, 4s...
                if attempt < self.max_retries:
                    sleep_time = 2 ** (attempt - 1)
                    await asyncio.sleep(sleep_time)

        logger.error(f"Fallo definitivo al descargar {url} tras {self.max_retries} intentos")
        return None

    async def fetch_articles(self, limit: int = 20):
        
        pass

