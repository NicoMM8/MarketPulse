"""
Extractor de noticias financieras para Yahoo Finance.
Utiliza peticiones HTTP asíncronas con httpx, reintentos con backoff exponencial
y parseo de estructura HTML/RSS mediante BeautifulSoup.
"""

import asyncio
from datetime import datetime, timezone
import logging
import re
from typing import Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import httpx

from app.schemas.article import ArticleCreate
from app.services.scraper.base import BaseScraper, logger


class YahooFinanceScraper(BaseScraper):
    """Extractor asíncrono de noticias financieras desde Yahoo Finance."""

    def __init__(self, base_url: str = "https://finance.yahoo.com"):
        super().__init__(source_name="yahoo_finance", base_url=base_url)
        self.news_url = f"{self.base_url}/news/"
        self.rss_url = "https://finance.yahoo.com/news/rssindex"
        self.timeout = 10.0
        self.max_retries = 3

    async def fetch_html(self, url: str) -> Optional[str]:
        """
        Descarga el contenido HTML o RSS de una URL con reintentos automáticos
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

    def _extract_tickers(self, text: str) -> list[str]:
        """
        Busca patrones de tickers bursatiles en el texto (ej: $AAPL, (TSLA), o palabras clave conocidas).
        """
        found = set()

        # 1. Tickers con signo de dolar (ej: $NVDA)
        dollar_tickers = re.findall(r"\$([A-Z]{1,5})\b", text)
        found.update(dollar_tickers)

        # 2. Tickers entre parentesis habituales (ej: (NASDAQ: AAPL) o (AAPL))
        parenthesis_tickers = re.findall(r"\((?:[A-Z]+:\s*)?([A-Z]{1,5})\)", text)
        found.update(parenthesis_tickers)

        return sorted(list(found))

    def parse_articles_from_html(self, content: str, limit: int = 20) -> list[ArticleCreate]:
        """
        Parsea el contenido descargado. Soporta tanto feed RSS/XML
        como tarjetas HTML de la sección de noticias.
        """
        articles: list[ArticleCreate] = []

        # Si el contenido es un feed RSS/XML
        if "<rss" in content or "<feed" in content or "<channel>" in content:
            soup = BeautifulSoup(content, "xml" if "xml" in BeautifulSoup.__doc__ else "html.parser")
            items = soup.find_all("item")

            for item in items:
                if len(articles) >= limit:
                    break

                try:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_date_elem = item.find("pubDate")
                    desc_elem = item.find("description")

                    if not title_elem or not link_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    url = link_elem.get_text(strip=True)
                    raw_desc = desc_elem.get_text(strip=True) if desc_elem else title

                    # Limpiamos etiquetas HTML residuales en la descripcion
                    clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(strip=True)

                    if len(clean_desc) < 20:
                        clean_desc = f"{title}. {clean_desc}".strip()

                    # Fecha de publicacion
                    published_at = datetime.now(timezone.utc)
                    if pub_date_elem:
                        try:
                            parsed_date = date_parser.parse(pub_date_elem.get_text(strip=True))
                            if parsed_date.tzinfo is None:
                                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                            published_at = parsed_date
                        except Exception:
                            pass

                    # Detectamos posibles tickers
                    tickers = self._extract_tickers(f"{title} {clean_desc}")

                    article = ArticleCreate(
                        title=title,
                        content=clean_desc,
                        url=url,
                        source=self.source_name,
                        published_at=published_at,
                        tickers=tickers
                    )
                    articles.append(article)

                except Exception as err:
                    logger.debug(f"Saltando elemento RSS malformado: {err}")
                    continue

            return articles

        # Si es pagina HTML normal de Yahoo Finance
        soup = BeautifulSoup(content, "html.parser")

        # Buscamos enlaces a noticias dentro de etiquetas h2, h3 o articulos
        news_cards = soup.find_all(["li", "div", "article"], class_=lambda c: c and any(k in str(c) for k in ["stream-item", "story-item", "news-item", "card"]))




        if not news_cards:
            # Fallback generico: buscar titulares h3 con enlace
            news_cards = soup.find_all("h3")

        for card in news_cards:
            if len(articles) >= limit:
                break

            try:
                link = card.find("a", href=True)
                if not link:
                    continue

                href = link["href"]
                # Solo enlaces a noticias
                if "/news/" not in href and "/m/" not in href:
                    continue

                full_url = urljoin(self.base_url, href)
                title = link.get_text(strip=True)
                if not title or len(title) < 10:
                    continue

                # Buscamos un resumen o parrafo descriptivo dentro de la card
                p_elem = card.find("p")
                content_text = p_elem.get_text(strip=True) if p_elem else title

                if len(content_text) < 20:
                    content_text = f"{title}. Noticia financiera destacada en el portal Yahoo Finance."

                tickers = self._extract_tickers(f"{title} {content_text}")

                article = ArticleCreate(
                    title=title,
                    content=content_text,
                    url=full_url,
                    source=self.source_name,
                    published_at=datetime.now(timezone.utc),
                    tickers=tickers
                )
                articles.append(article)

            except Exception as err:
                logger.debug(f"Saltando tarjeta HTML por error de parseo: {err}")
                continue

        return articles

    async def fetch_articles(self, limit: int = 20) -> list[ArticleCreate]:
        """
        Descarga y parsea noticias financieras de Yahoo Finance.
        Prueba primero el feed RSS (mas rapido y limpio) y usa HTML como alternativa.
        """
        # 1. Intentamos primero con RSS
        rss_content = await self.fetch_html(self.rss_url)
        if rss_content:
            articles = self.parse_articles_from_html(rss_content, limit=limit)
            if articles:
                logger.info(f"Extraidas {len(articles)} noticias de Yahoo Finance via RSS")
                return articles

        # 2. Si el RSS falla, probamos con la portada web de noticias
        html_content = await self.fetch_html(self.news_url)
        if html_content:
            articles = self.parse_articles_from_html(html_content, limit=limit)
            logger.info(f"Extraidas {len(articles)} noticias de Yahoo Finance via HTML")
            return articles

        logger.warning("No se pudieron obtener noticias de Yahoo Finance")
        return []

