"""
Patrón Repositorio para la entidad Article.
Encapsula las operaciones de acceso a datos, garantizando inserciones
idempotentes y evitando la duplicación de noticias mediante content_hash y url.
"""

from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.schemas.article import ArticleCreate


class ArticleRepository:
    """Gestor de operaciones de persistencia para noticias financieras."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, article_id: int) -> Optional[Article]:
        """Obtiene un artículo por su clave primaria."""
        stmt = select(Article).where(Article.id == article_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_hash(self, content_hash: str) -> Optional[Article]:
        """Busca un artículo por su hash SHA-256."""
        stmt = select(Article).where(Article.content_hash == content_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> Optional[Article]:
        """Busca un artículo por su URL canónica."""
        stmt = select(Article).where(Article.url == url)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


    async def create_if_not_exists(self, article_in: ArticleCreate) -> tuple[Article, bool]:
        """
        Inserta un nuevo artículo sólo si no existe previamente por hash o por URL.
        Retorna una tupla (artículo, creado: bool).
        """
        # Si no viene con hash calculado, lo sacamos al vuelo
        hash_to_check = article_in.content_hash or article_in.calculate_hash()

        # 1. Comprobar primero por hash (mas rapido al estar indexado)
        existing = await self.get_by_hash(hash_to_check)
        if existing:
            return existing, False

        # 2. Comprobamos por URL por si cambio una coma en el texto pero es la misma noticia
        existing_url = await self.get_by_url(str(article_in.url))
        if existing_url:
            return existing_url, False

        # 3. Si no existe, creamos la nueva entidad
        new_article = Article(
            title=article_in.title,
            content=article_in.content,
            url=str(article_in.url),
            source=article_in.source,
            published_at=article_in.published_at,
            author=article_in.author,
            tickers=article_in.tickers,
            content_hash=hash_to_check
        )

        self.session.add(new_article)
        await self.session.commit()
        await self.session.refresh(new_article)

        return new_article, True

    async def list_articles(
        self,
        skip: int = 0,
        limit: int = 50,
        source: Optional[str] = None
    ) -> list[Article]:
        """Retorna una lista paginada de artículos ordenados por fecha de publicación descendente."""
        stmt = select(Article).order_by(Article.published_at.desc())

        if source:
            stmt = stmt.where(Article.source == source)

        stmt = stmt.offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # TODO: meter filtros por rango de fechas cuando tengamos el scraper funcionando

    async def count_articles(self) -> int:
        """Devuelve el total de artículos registrados en la base de datos."""
        stmt = select(func.count(Article.id))
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

