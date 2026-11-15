"""Módulo de modelos de persistencia relacional."""

from app.models.article import Article
from app.models.repository import ArticleRepository

__all__ = ["Article", "ArticleRepository"]
