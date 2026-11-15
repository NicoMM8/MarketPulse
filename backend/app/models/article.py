"""
Modelo relacional de artículos de noticias financieras para SQLAlchemy 2.0.
Tabla 'articles' con restricciones de unicidad e índices para evitar duplicados.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Article(Base):
    """
    Entidad relacional que representa una noticia financiera almacenada en el sistema.
    """
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(String(1000), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    # SQLite guarda JSON como texto por debajo, en postgres va como tipo json/jsonb
    tickers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    # Hash SHA-256 para busquedas rapidas de duplicados antes de insertar
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, source='{self.source}', title='{self.title[:30]}...', hash='{self.content_hash[:8]}')>"

