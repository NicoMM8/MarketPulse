"""
Pruebas unitarias con mocks y fixtures para el extractor de Yahoo Finance (Issue #9).
Utiliza capturas reales en español guardadas en tests/fixtures/ para no depender
de la conexión a Internet durante la ejecución automática de pytest.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from app.services.scraper.yahoo import YahooFinanceScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def yahoo_rss_xml() -> str:
    return (FIXTURES_DIR / "yahoo_rss_sample.xml").read_text(encoding="utf-8")


@pytest.fixture
def yahoo_html_content() -> str:
    return (FIXTURES_DIR / "yahoo_html_sample.html").read_text(encoding="utf-8")


def test_parse_yahoo_rss_spanish_fixture(yahoo_rss_xml: str):
    """Comprueba el parseo correcto de noticias reales en español desde el feed RSS."""
    scraper = YahooFinanceScraper()
    articles = scraper.parse_articles_from_html(yahoo_rss_xml, limit=10)

    # El XML tiene 4 items, pero el cuarto no tiene <link> y debe ser ignorado
    assert len(articles) == 3

    # Comprobamos la primera noticia (Nvidia)
    first = articles[0]
    assert first.title == "Nvidia supera expectativas: ¿Y ahora qué?"
    assert first.source == "yahoo_finance"
    assert "NVDA" in first.tickers
    assert len(first.content_hash) == 64

    # Comprobamos la segunda noticia (formato NASDAQ:NVDA sin espacio)
    second = articles[1]
    assert "NVDA" in second.tickers

    # Comprobamos la tercera noticia (Apple con $AAPL)
    third = articles[2]
    assert "AAPL" in third.tickers
    assert third.published_at.year == 2026


def test_parse_yahoo_html_spanish_fixture(yahoo_html_content: str):
    """Comprueba el parseo HTML en español y que ignora enlaces que no son noticias."""
    scraper = YahooFinanceScraper()
    articles = scraper.parse_articles_from_html(yahoo_html_content, limit=10)

    # El HTML tiene 2 noticias validas (/noticias/...) y 1 enlace a /quote/ que debe descartarse
    assert len(articles) == 2

    assert str(articles[0].url).startswith("https://es.finance.yahoo.com/noticias/")
    assert "AAPL" in articles[0].tickers
    assert "NVDA" in articles[1].tickers


def test_parse_respects_limit(yahoo_rss_xml: str):
    """Verifica que el parámetro limit acota correctamente el número de artículos devueltos."""
    scraper = YahooFinanceScraper()
    articles = scraper.parse_articles_from_html(yahoo_rss_xml, limit=2)
    assert len(articles) == 2


@pytest.mark.asyncio
async def test_fetch_articles_uses_rss_first(yahoo_rss_xml: str):
    """Simula respuesta exitosa de red en RSS y verifica que no hace llamadas innecesarias."""
    scraper = YahooFinanceScraper()

    with patch.object(scraper, "fetch_html", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = yahoo_rss_xml

        articles = await scraper.fetch_articles(limit=5)

        assert len(articles) == 3
        # Solo debe haber llamado 1 vez (al RSS) porque tuvo exito
        mock_fetch.assert_awaited_once_with(scraper.rss_url)


@pytest.mark.asyncio
async def test_fetch_articles_fallback_to_html_when_rss_fails(yahoo_html_content: str):
    """Si falla el RSS (devuelve None), debe hacer fallback automático a la portada HTML."""
    scraper = YahooFinanceScraper()

    with patch.object(scraper, "fetch_html", new_callable=AsyncMock) as mock_fetch:
        # 1a llamada (RSS) falla -> None; 2a llamada (HTML) -> contenido valido
        mock_fetch.side_effect = [None, yahoo_html_content]

        articles = await scraper.fetch_articles(limit=5)

        assert len(articles) == 2
        assert mock_fetch.await_count == 2


@pytest.mark.asyncio
async def test_fetch_articles_handles_total_network_failure():
    """Si fallan ambas fuentes (timeout o servidor caido), devuelve lista vacia sin romper."""
    scraper = YahooFinanceScraper()

    with patch.object(scraper, "fetch_html", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = None

        articles = await scraper.fetch_articles(limit=5)

        assert articles == []
        assert mock_fetch.await_count == 2

