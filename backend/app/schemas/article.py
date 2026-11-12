"""
Esquemas de validación de datos para noticias financieras utilizando Pydantic v2.
Define la estructura de los artículos ingeridos por los scrapers y devueltos por la API REST.
"""

from datetime import datetime
import hashlib
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ArticleBase(BaseModel):
    """Atributos comunes de una noticia financiera."""
    title: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Titular de la noticia financiera."
    )
    content: str = Field(
        ...,
        min_length=20,
        description="Cuerpo textual o resumen principal de la noticia."
    )
    url: HttpUrl = Field(
        ...,
        description="URL canónica de origen de la noticia."
    )
    source: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Identificador del portal de procedencia (ej. 'yahoo_finance', 'investing')."
    )
    published_at: datetime = Field(
        ...,
        description="Fecha y hora de publicación original en formato UTC."
    )
    author: Optional[str] = Field(
        default=None,
        max_length=150,
        description="Nombre del autor o agencia de noticias si está disponible."
    )
    tickers: list[str] = Field(
        default_factory=list,
        description="Lista de activos/símbolos bursátiles identificados (ej. ['AAPL', 'MSFT'])."
    )

    @field_validator("tickers", mode="before")
    @classmethod
    def normalize_tickers(cls, v: list[str] | None) -> list[str]:
        """Normalizamos los tickers a mayúsculas, elimina espacios y descarta duplicados."""
        if not v:
            return []
        cleaned = []
        for ticker in v:
            if isinstance(ticker, str):
                item = ticker.strip().upper()
                if item and item not in cleaned:
                    cleaned.append(item)
        return cleaned

    @field_validator("title", "content", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Elimina espacios redundantes en títulos y cuerpos de texto."""
        if isinstance(v, str):
            return v.strip()
        return v


class ArticleCreate(ArticleBase):
    """Esquema utilizado por los módulos de scraping al extraer una nueva noticia."""
    content_hash: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Hash SHA-256 para control de duplicados (se autogenera si se omite)."
    )

    def calculate_hash(self) -> str:
        """Calcula el hash SHA-256 combinando URL y contenido para detectar duplicados."""
        raw = f"{str(self.url).strip()}_{self.content.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def model_post_init(self, __context) -> None:
        """Autocalcula el hash si no fue provisto explícitamente."""
        if not self.content_hash:
            self.content_hash = self.calculate_hash()


class ArticleResponse(ArticleBase):
    """Esquema de respuesta de noticias devueltas por el sistema y la API REST."""
    id: int = Field(..., description="Identificador único en base de datos.")
    content_hash: str = Field(..., description="Hash único del artículo para auditoría.")
    created_at: datetime = Field(..., description="Fecha de ingesta en el sistema.")

    model_config = ConfigDict(from_attributes=True)

