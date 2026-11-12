"""
Pruebas unitarias para los esquemas Pydantic de noticias financieras (Issue #2 y #3).
Verifica validación de tipos, formatos, normalización de tickers y cálculo de hash.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.article import ArticleBase, ArticleCreate, ArticleResponse


def test_article_create_valid():
    """Comprueba que una noticia válida se crea correctamente con sus metadatos y hash."""
    article_data = {
        "title": "Apple supera expectativas de ingresos en el último trimestre",
        "content": "La compañía tecnológica de Cupertino presentó resultados financieros con récord histórico.",
        "url": "https://finance.yahoo.com/news/apple-earnings-q4-2026.html",
        "source": "yahoo_finance",
        "published_at": datetime(2026, 11, 12, 10, 30, tzinfo=timezone.utc),
        "author": "Redacción Financiera",
        "tickers": ["aapl", "AAPL", " msft "]
    }

    article = ArticleCreate(**article_data)

    assert article.title == "Apple supera expectativas de ingresos en el último trimestre"
    assert article.source == "yahoo_finance"
    # Normalización de tickers: mayúsculas, sin espacios y sin duplicados
    assert article.tickers == ["AAPL", "MSFT"]
    # Comprobar que calcula automáticamente el hash SHA-256
    assert article.content_hash is not None
    assert len(article.content_hash) == 64


def test_article_validation_error_missing_fields():
    """Verifica que Pydantic rechaza noticias a las que les falten campos obligatorios."""
    with pytest.raises(ValidationError) as exc_info:
        ArticleCreate(
            title="Titular incompleto",
            # Falta content, url, source, published_at
        )

    errors = exc_info.value.errors()
    missing_fields = {error["loc"][0] for error in errors}
    assert "content" in missing_fields
    assert "url" in missing_fields
    assert "source" in missing_fields
    assert "published_at" in missing_fields


def test_article_validation_invalid_url():
    """Comprueba que una URL con formato inválido provoca error de validación."""
    with pytest.raises(ValidationError):
        ArticleCreate(
            title="Noticia sobre tipos de interés del Banco Central",
            content="Los tipos de interés se mantendrán estables durante las próximas reuniones del BCE.",
            url="esto-no-es-una-url-valida",
            source="investing",
            published_at=datetime.now(timezone.utc)
        )


def test_article_validation_short_content():
    """Comprueba que no se aceptan contenidos excesivamente cortos (mínimo 20 caracteres)."""
    with pytest.raises(ValidationError):
        ArticleCreate(
            title="Noticia con texto demasiado breve",
            content="Muy corto",
            url="https://es.investing.com/news/article-123",
            source="investing",
            published_at=datetime.now(timezone.utc)
        )


def test_article_response_mapping():
    """Comprueba la instanciación de ArticleResponse simulando la lectura desde base de datos."""
    now = datetime.now(timezone.utc)
    response_data = {
        "id": 1,
        "title": "Santander incrementa su dividendo tras mejorar el margen de intereses",
        "content": "La entidad financiera española anuncia un incremento del pago al accionista para el próximo mes.",
        "url": "https://es.investing.com/news/santander-dividendo-2026",
        "source": "investing",
        "published_at": now,
        "author": "Agencia EFE",
        "tickers": ["SAN.MC"],
        "content_hash": "a" * 64,
        "created_at": now
    }

    response = ArticleResponse(**response_data)
    assert response.id == 1
    assert response.tickers == ["SAN.MC"]
    assert response.content_hash == "a" * 64

