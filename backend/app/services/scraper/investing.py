"""
Extractor dinámico de noticias financieras para Investing.com utilizando Playwright.
Ejecuta Chromium en modo headless, optimiza la carga bloqueando elementos pesados,
gestiona modales de consentimiento de cookies y extrae titulares, contenido y tickers.
"""

import asyncio
from datetime import datetime, timezone
import logging
import re
from typing import Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from playwright.async_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from app.schemas.article import ArticleCreate
from app.services.scraper.base import BaseScraper, logger


# Mapeo manual para los valores mas conocidos del IBEX 35
IBEX_TICKER_MAP = {
    "SANTANDER": "SAN.MC",
    "BBVA": "BBVA.MC",
    "TELEFONICA": "TEF.MC",
    "TELEFÓNICA": "TEF.MC",
    "INDITEX": "ITX.MC",
    "IBERDROLA": "IBE.MC",
    "REPSOL": "REP.MC",
    "CAIXABANK": "CABK.MC",
    "AMADEUS": "AMS.MC",
}


class InvestingScraper(BaseScraper):
    """
    Extractor dinámico para Investing.com en español basado en Playwright (Chromium headless).
    Capaz de renderizar contenido generado por JavaScript, gestionar banners de consentimiento
    y extraer noticias financieras en tiempo real.
    """

    def __init__(
        self,
        base_url: str = "https://es.investing.com",
        news_path: str = "/news/stock-market-news",
        headless: bool = True,
    ):
        super().__init__(source_name="investing", base_url=base_url)
        self.news_url = urljoin(self.base_url, news_path)
        self.headless = headless
        self.timeout = 25000  # 25 segundos máximo por página


    async def _create_optimized_context(self, browser: Browser) -> BrowserContext:
        """
        Crea un contexto de navegación con cabeceras realistas y bloquea
        recursos pesados (imágenes, medios y fuentes) para acelerar drásticamente la carga.
        """
        context = await browser.new_context(
            user_agent=self.get_default_headers()["User-Agent"],
            viewport={"width": 1280, "height": 800},
            locale="es-ES",
            timezone_id="Europe/Madrid"
        )

        # Bloquear imagenes, videos y tipografias pesadas
        async def route_interceptor(route):
            if route.request.resource_type in ["image", "media", "font"]:
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", route_interceptor)
        return context

    async def _handle_cookie_consent(self, page: Page) -> None:
        """
        Detecta y acepta los modales de cookies (OneTrust o avisos GDPR habituales de Investing.com)
        para que no tapen los titulares ni bloqueen la interacción.
        """
        cookie_selectors = [
            "#onetrust-accept-btn-handler",
            "button[id*='onetrust-accept']",
            "button:has-text('Aceptar todas')",
            "button:has-text('Aceptar y continuar')",
            "button:has-text('Acepto')"
        ]

        for selector in cookie_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=2500):
                    logger.info(f"Modal de cookies detectado. Pulsando: {selector}")
                    await btn.click()
                    await asyncio.sleep(0.5)
                    return
            except Exception:
                continue

        logger.debug("No se detectó modal de cookies activo o ya fue aceptado")

    async def fetch_page_html(self, url: str) -> Optional[str]:
        """
        Navega a la URL con Chromium headless, acepta cookies, espera a que cargue
        el contenido dinámico y devuelve el HTML completo renderizado.
        """
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )
                context = await self._create_optimized_context(browser)
                page = await context.new_page()

                logger.info(f"Navegando con Playwright a {url}...")
                await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)

                # Gestionar aviso de cookies si aparece
                await self._handle_cookie_consent(page)

                # Esperamos a que aparezcan los articulos en la pagina
                try:
                    await page.wait_for_selector(
                        "article, [data-test='article-item'], div[class*='articleItem']",
                        timeout=5000
                    )
                except PlaywrightTimeoutError:
                    logger.warning("Timeout esperando selectores de articulos, intentamos con el HTML actual")

                # Hacemos un poco de scroll para que carguen mas noticias si hay carga perezosa
                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(1.0)  # margen para que termine el render

                html_content = await page.content()
                return html_content

            except Exception as err:
                logger.error(f"Error durante la navegación con Playwright en {url}: {err}")
                return None

            finally:
                # Nos aseguramos de cerrar siempre el navegador
                if browser:
                    await browser.close()


    def _extract_tickers(self, text: str) -> list[str]:
        """
        Extrae tickers bursátiles de Investing.com (ej: (BME:SAN), $AAPL o menciones a empresas del IBEX).
        """
        found = set()

        # 1. Tickers con prefijo de mercado o parentesis: (BME:SAN), (NASDAQ:AAPL)
        market_tickers = re.findall(r"\((?:[A-Z]{2,6}:)?([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\)", text)
        found.update(market_tickers)

        # 2. Tickers con signo de dolar ($TSLA)
        dollar_tickers = re.findall(r"\$([A-Z]{1,5})\b", text)
        found.update(dollar_tickers)

        # 3. Deteccion de valores del IBEX 35 por nombre comun
        text_upper = text.upper()
        for name, ticker in IBEX_TICKER_MAP.items():
            if re.search(rf"\b{re.escape(name)}\b", text_upper):
                found.add(ticker)

        return sorted(list(found))

    def parse_articles_from_html(self, html_content: str, limit: int = 20) -> list[ArticleCreate]:
        """
        Parsea el HTML renderizado de Investing.com extrayendo noticias, enlaces, fechas y tickers.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        articles: list[ArticleCreate] = []

        # Investing suele estructurar las noticias en articulos o tarjetas con data-test="article-item"
        news_items = soup.find_all(
            ["article", "div", "li"],
            attrs={"data-test": lambda v: v and "article" in v}
        )

        if not news_items:
            # Fallback a clases comunes de articulos de Investing
            news_items = soup.find_all(
                ["article", "div", "li"],
                class_=lambda c: c and any(k in str(c) for k in ["articleItem", "news-item", "story-card"])
            )

        if not news_items:
            # Si cambian las clases CSS de la web, buscamos directamente enlaces que apunten a /news/
            links = soup.find_all("a", href=lambda h: h and "/news/" in h)
            seen_urls = set()
            for a in links:
                if len(articles) >= limit:
                    break
                href = a.get("href")
                if not href or href in seen_urls:
                    continue
                title = a.get_text(strip=True)
                if len(title) < 15:
                    continue
                seen_urls.add(href)
                full_url = urljoin(self.base_url, href)

                article = ArticleCreate(
                    title=title,
                    content=f"{title}. Noticia financiera capturada en Investing.com.",
                    url=full_url,
                    source=self.source_name,
                    published_at=datetime.now(timezone.utc),
                    tickers=self._extract_tickers(title)
                )
                articles.append(article)
            return articles

        for item in news_items:
            if len(articles) >= limit:
                break

            try:
                # Titulo y enlace
                link_elem = item.find("a", href=lambda h: h and "/news/" in h)
                if not link_elem:
                    continue

                title = link_elem.get_text(strip=True)
                if not title or len(title) < 12:
                    continue

                full_url = urljoin(self.base_url, link_elem["href"])

                # Descripcion o resumen
                desc_elem = item.find(["p", "span"], class_=lambda c: c and any(k in str(c) for k in ["summary", "description", "body"]))
                content = desc_elem.get_text(strip=True) if desc_elem else title

                if len(content) < 20:
                    content = f"{title}. Noticia de mercado financiero publicada en Investing.com."

                # Fecha
                time_elem = item.find("time")
                published_at = datetime.now(timezone.utc)
                if time_elem and time_elem.get("datetime"):
                    try:
                        parsed_date = date_parser.parse(time_elem["datetime"])
                        if parsed_date.tzinfo is None:
                            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                        published_at = parsed_date
                    except Exception:
                        pass

                # Tickers
                tickers = self._extract_tickers(f"{title} {content}")

                article = ArticleCreate(
                    title=title,
                    content=content,
                    url=full_url,
                    source=self.source_name,
                    published_at=published_at,
                    tickers=tickers
                )
                articles.append(article)

            except Exception as err:
                logger.debug(f"Saltando elemento de Investing por error de parseo: {err}")
                continue

        return articles

    async def fetch_articles(self, limit: int = 20) -> list[ArticleCreate]:
        """
        Navega con Playwright a Investing.com, obtiene el HTML renderizado y extrae las noticias.
        """
        html = await self.fetch_page_html(self.news_url)
        if not html:
            logger.warning("No se pudo obtener el contenido HTML de Investing.com")
            return []

        articles = self.parse_articles_from_html(html, limit=limit)
        logger.info(f"Extraídas {len(articles)} noticias de Investing.com con Playwright")
        return articles
