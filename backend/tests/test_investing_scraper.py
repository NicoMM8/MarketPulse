"""
Pruebas unitarias para InvestingScraper con Playwright (Issue #10).
Verifica el parseo de HTML dinámico, extracción de tickers españoles (IBEX 35)
y mocks de navegación sin levantar navegador real en CI/tests automáticos.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from app.services.scraper.investing import InvestingScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def investing_html() -> str:
    # Usamos el HTML de muestra guardado para no llamar a internet en los tests
    ruta = FIXTURES_DIR / "investing_muestra.html"
    return ruta.read_text(encoding="utf-8")


def test_parse_investing_html_fixture(investing_html: str):
    """Verifica que el parseo de HTML de Investing extrae noticias válidas y sus tickers."""
    scraper = InvestingScraper()
    articles = scraper.parse_articles_from_html(investing_html, limit=10)

    # El fixture tiene 3 noticias validas y 1 enlace a /crypto/ que debe descartarse
    assert len(articles) == 3

    # Noticia 1: Santander (detección por palabra clave en IBEX_TICKER_MAP)
    first = articles[0]
    assert "Banco Santander" in first.title
    assert first.source == "investing"
    assert "SAN.MC" in first.tickers
    assert len(first.content_hash) == 64

    # Noticia 2: BBVA (detección por (BME:BBVA) y por nombre)
    second = articles[1]
    assert "BBVA.MC" in second.tickers

    # Noticia 3: Telefónica ($TEF)
    third = articles[2]
    assert any(t in third.tickers for t in ["TEF", "TEF.MC"])


def test_parse_investing_respects_limit(investing_html: str):
    """Comprueba que el límite de noticias devueltas se respeta."""
    scraper = InvestingScraper()
    articles = scraper.parse_articles_from_html(investing_html, limit=1)
    assert len(articles) == 1


@pytest.mark.asyncio
async def test_fetch_articles_with_mocked_playwright(investing_html: str):
    """Simula la navegación de Playwright devolviendo el HTML del fixture."""
    scraper = InvestingScraper()

    with patch.object(scraper, "fetch_page_html", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = investing_html

        articles = await scraper.fetch_articles(limit=5)

        assert len(articles) == 3
        mock_fetch.assert_awaited_once_with(scraper.news_url)


@pytest.mark.asyncio
async def test_fetch_articles_handles_browser_error():
    """Si Playwright falla por timeout o caída del navegador, retorna lista vacía sin romper."""
    scraper = InvestingScraper()

    with patch.object(scraper, "fetch_page_html", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = None

        articles = await scraper.fetch_articles(limit=5)

        assert articles == []
        mock_fetch.assert_awaited_once_with(scraper.news_url)
