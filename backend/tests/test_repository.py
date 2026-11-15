"""
Pruebas automatizadas de persistencia para ArticleRepository (Issue #6).
Verifica la inserción idempotente (sin duplicados), búsquedas por hash/URL y listados.
Utiliza una base de datos SQLite en memoria para aislamiento completo de cada test.
"""

from datetime import datetime, timezone
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.repository import ArticleRepository
from app.schemas.article import ArticleCreate


@pytest_asyncio.fixture
async def async_session():
    """Crea una base de datos SQLite en memoria limpia para cada prueba."""
    # Usamos base de datos en memoria para que no deje basura en disco al terminar
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_create_article_success(async_session: AsyncSession):
    """Verifica que una noticia nueva se inserta correctamente y devuelve creado=True."""
    repo = ArticleRepository(async_session)

    article_in = ArticleCreate(
        title="BBVA anuncia recompra de acciones por 1000 millones de euros",
        content="La entidad bancaria ejecutará un nuevo programa de recompra tras los buenos resultados.",
        url="https://es.investing.com/news/bbva-recompra-2026",
        source="investing",
        published_at=datetime.now(timezone.utc),
        author="Analista Mercado",
        tickers=["BBVA.MC"]
    )

    article, created = await repo.create_if_not_exists(article_in)

    assert created is True
    assert article.id is not None
    assert article.title == article_in.title
    assert article.source == "investing"
    assert article.tickers == ["BBVA.MC"]
    assert len(article.content_hash) == 64


@pytest.mark.asyncio
async def test_create_article_duplicate_hash(async_session: AsyncSession):
    """Comprueba que intentar guardar la misma noticia dos veces NO duplica registros."""
    repo = ArticleRepository(async_session)

    article_in = ArticleCreate(
        title="Tesla presenta sus previsiones de entrega de vehículos",
        content="La compañía de Elon Musk actualiza sus estimaciones de producción para el trimestre.",
        url="https://finance.yahoo.com/news/tesla-deliveries-update.html",
        source="yahoo_finance",
        published_at=datetime.now(timezone.utc),
        tickers=["TSLA"]
    )

    # 1. Primera inserción: debe crearla
    art1, created1 = await repo.create_if_not_exists(article_in)
    assert created1 is True

    # 2. Segunda inserción con exactamente el mismo contenido: debe rechazarla
    art2, created2 = await repo.create_if_not_exists(article_in)
    assert created2 is False
    assert art1.id == art2.id

    # El conteo total en la tabla debe seguir siendo 1
    total = await repo.count_articles()
    assert total == 1


@pytest.mark.asyncio
async def test_create_article_duplicate_url_different_body(async_session: AsyncSession):
    """Si cambia ligeramente el texto pero la URL es la misma, debe detectar que ya existe."""
    repo = ArticleRepository(async_session)

    art_original = ArticleCreate(
        title="El BCE sube los tipos de interés 25 puntos básicos",
        content="Decisión oficial del Banco Central Europeo tomada en su reunión de Fráncfort.",
        url="https://es.investing.com/news/bce-tipos-interes-2026",
        source="investing",
        published_at=datetime.now(timezone.utc)
    )
    await repo.create_if_not_exists(art_original)

    # Misma URL pero texto ligeramente editado por el portal
    art_modificado = ArticleCreate(
        title="El BCE sube tipos 25 puntos",
        content="Decisión oficial del Banco Central Europeo tomada en Fráncfort hoy por la tarde.",
        url="https://es.investing.com/news/bce-tipos-interes-2026",
        source="investing",
        published_at=datetime.now(timezone.utc)
    )

    article_recuperado, created = await repo.create_if_not_exists(art_modificado)
    assert created is False
    assert article_recuperado.url == "https://es.investing.com/news/bce-tipos-interes-2026"

    total = await repo.count_articles()
    assert total == 1


@pytest.mark.asyncio
async def test_list_articles_and_filtering(async_session: AsyncSession):
    """Verifica la paginación y el filtrado por fuente."""
    repo = ArticleRepository(async_session)

    # Metemos 3 noticias de prueba (2 de yahoo y 1 de investing)
    for i in range(3):
        art = ArticleCreate(
            title=f"Noticia financiera de prueba número {i}",
            content=f"Cuerpo detallado del artículo de prueba número {i} con más de veinte caracteres.",
            url=f"https://finance.yahoo.com/news/article-{i}",
            source="yahoo_finance" if i < 2 else "investing",
            published_at=datetime.now(timezone.utc)
        )
        await repo.create_if_not_exists(art)

    # Conteo general
    total = await repo.count_articles()
    assert total == 3

    # Filtrado por portal de origen
    yahoo_articles = await repo.list_articles(source="yahoo_finance")
    assert len(yahoo_articles) == 2

    investing_articles = await repo.list_articles(source="investing")
    assert len(investing_articles) == 1

    # Paginación (pedimos solo 2)
    paginated = await repo.list_articles(limit=2)
    assert len(paginated) == 2

