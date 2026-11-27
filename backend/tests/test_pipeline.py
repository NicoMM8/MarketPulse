"""
Pruebas de integración para el pipeline de ingestión de noticias (Issue #12).
Verifica la orquestación completa: Scrapers -> Pydantic -> Repository -> SQLite en memoria.
Comprueba inserciones idempotentes, estadísticas de ejecución y aislamiento de fallos.
"""

from datetime import datetime, timezone
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.repository import ArticleRepository
from app.schemas.article import ArticleCreate
from app.services.scraper.base import BaseScraper
from app.services.scraper.pipeline import NewsIngestionPipeline


class MockScraper(BaseScraper):
    """Scraper simulado para pruebas de integración que devuelve artículos controlados en memoria."""

    def __init__(self, source_name: str, articles: list[ArticleCreate], should_fail: bool = False):
        super().__init__(source_name=source_name, base_url=f"https://{source_name}.test")
        self.sample_articles = articles
        self.should_fail = should_fail

    async def fetch_articles(self, limit: int = 20) -> list[ArticleCreate]:
        if self.should_fail:
            raise ConnectionError(f"Simulación de caída de red en {self.source_name}")
        return self.sample_articles[:limit]


@pytest_asyncio.fixture
async def test_session():
    """Crea una base de datos SQLite en memoria limpia para cada test."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.fixture
def mock_articles_yahoo() -> list[ArticleCreate]:
    return [
        ArticleCreate(
            title="Santander anuncia recompra de acciones en el mercado continuo",
            content="La entidad financiera española destinará fondos para mejorar la retribución al accionista.",
            url="https://es.finance.yahoo.com/noticias/santander-recompra-2026.html",
            source="yahoo_finance",
            published_at=datetime.now(timezone.utc),
            tickers=["SAN.MC"]
        ),
        ArticleCreate(
            title="Nvidia amplía su ventaja en chips de inteligencia artificial",
            content="Los centros de datos de última generación aumentan sus pedidos de aceleradores gráficos.",
            url="https://es.finance.yahoo.com/noticias/nvidia-chips-ia-2026.html",
            source="yahoo_finance",
            published_at=datetime.now(timezone.utc),
            tickers=["NVDA"]
        )
    ]


@pytest.fixture
def mock_articles_investing() -> list[ArticleCreate]:
    return [
        ArticleCreate(
            title="Telefónica aprueba su plan de inversión en redes europeas",
            content="El operador de telecomunicaciones presentó su estrategia de despliegue de infraestructuras.",
            url="https://es.investing.com/news/telefonica-inversion-2026",
            source="investing",
            published_at=datetime.now(timezone.utc),
            tickers=["TEF.MC"]
        )
    ]


@pytest.mark.asyncio
async def test_pipeline_full_run_success(test_session: AsyncSession, mock_articles_yahoo, mock_articles_investing):
    """Comprueba que el pipeline procesa todas las fuentes y las guarda en base de datos."""
    scrapers = [
        MockScraper("yahoo_finance", mock_articles_yahoo),
        MockScraper("investing", mock_articles_investing)
    ]

    pipeline = NewsIngestionPipeline(scrapers=scrapers)
    stats = await pipeline.run(session=test_session)

    # Debe haber procesado 3 noticias en total
    assert stats.total_scraped == 3
    assert stats.new_inserted == 3
    assert stats.duplicates_skipped == 0
    assert stats.by_source["yahoo_finance"] == 2
    assert stats.by_source["investing"] == 1
    assert "SAN.MC" in stats.tickers_detected
    assert "NVDA" in stats.tickers_detected

    # Comprobamos en la base de datos real
    repo = ArticleRepository(test_session)
    total_in_db = await repo.count_articles()
    assert total_in_db == 3


@pytest.mark.asyncio
async def test_pipeline_deduplication_on_second_run(test_session: AsyncSession, mock_articles_yahoo):
    """Verifica que una segunda ejecución del pipeline con las mismas noticias no duplica registros."""
    scraper = MockScraper("yahoo_finance", mock_articles_yahoo)
    pipeline = NewsIngestionPipeline(scrapers=[scraper])

    # 1. Primera ejecución: guarda 2
    stats1 = await pipeline.run(session=test_session)
    assert stats1.new_inserted == 2
    assert stats1.duplicates_skipped == 0

    # 2. Segunda ejecución: las 2 deben ser descartadas por duplicadas
    stats2 = await pipeline.run(session=test_session)
    assert stats2.new_inserted == 0
    assert stats2.duplicates_skipped == 2

    # El total en base de datos debe seguir siendo 2
    repo = ArticleRepository(test_session)
    assert await repo.count_articles() == 2


@pytest.mark.asyncio
async def test_pipeline_error_isolation(test_session: AsyncSession, mock_articles_yahoo):
    """Si un scraper falla por error de conexión, el pipeline debe continuar con los demás."""
    scrapers = [
        MockScraper("broken_source", [], should_fail=True),
        MockScraper("yahoo_finance", mock_articles_yahoo)
    ]

    pipeline = NewsIngestionPipeline(scrapers=scrapers)
    stats = await pipeline.run(session=test_session)

    # La fuente rota no guardó nada, pero Yahoo sí
    assert stats.new_inserted == 2
    assert stats.by_source.get("yahoo_finance") == 2
    assert "broken_source" not in stats.by_source


@pytest.mark.asyncio
async def test_pipeline_run_single_source(test_session: AsyncSession, mock_articles_yahoo, mock_articles_investing):
    """Comprueba que run_single ejecuta únicamente el portal solicitado."""
    scrapers = [
        MockScraper("yahoo_finance", mock_articles_yahoo),
        MockScraper("investing", mock_articles_investing)
    ]

    pipeline = NewsIngestionPipeline(scrapers=scrapers)

    # Ejecutamos solo Investing
    stats = await pipeline.run_single(session=test_session, source_name="investing")

    assert stats.total_scraped == 1
    assert stats.new_inserted == 1
    assert "investing" in stats.by_source
    assert "yahoo_finance" not in stats.by_source
