"""
Extractor dinámico de noticias financieras para Investing.com utilizando Playwright.
Ejecuta Chromium en modo headless, optimiza la carga bloqueando elementos pesados,
gestiona el consentimiento de cookies y espera la carga de los selectores.
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


class InvestingScraper(BaseScraper):
    """
    Extractor dinámico para Investing.com en español basado en Playwright.
    Capaz de renderizar contenido generado por JavaScript, gestionar banners de consentimiento
    y extraer noticias financieras en tiempo real.
    """

    def __init__(
        self,
        base_url: str = "https://es.investing.com",
        news_path: str = "/news/stock-market-news",
        headless: bool = True
    ):
        super().__init__(source_name="investing", base_url=base_url)
        self.news_url = urljoin(self.base_url, news_path)
        self.headless = headless
        self.timeout = 25000  # 25 segundos, tiempo maximo de espera

    async def _create_optimized_context(self, browser: Browser) -> BrowserContext:
        """
        Crea un contexto de navegación con cabeceras realistas y bloquea
        recursos pesados (imágenes, fuentes, css secundarios) para acelerar el scraping.
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
        Detecta y acepta los modelos de cookies (OneTrust o avisos GDPR habituales de Investing.com)
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
                # Comprobamos si el boton existe con un timeout corto de 2.5s
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

                # Esperamos brevemente a que se hidraten los artículos en el DOM
                try:
                    await page.wait_for_selector(
                        "article, [data-test='article-item'], div[class*='articleItem']",
                        timeout=5000
                    )
                except PlaywrightTimeoutError:
                    logger.warning("Timeout esperando selectores específicos de artículos, extrayendo HTML actual")

                # Scroll ligero para disparar lazy loading de noticias adicionales
                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(1.0)

                html_content = await page.content()
                return html_content

            except Exception as err:
                logger.error(f"Error durante la navegación con Playwright en {url}: {err}")
                return None

            finally:
                if browser:
                    await browser.close()

    async def fetch_articles(self, limit: int = 20) -> list[ArticleCreate]:
        """Metodo que completaremos mas adelante    """
        pass
