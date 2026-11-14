"""
Configuración global de la aplicación utilizando pydantic-settings.
Permite definir variables de entorno y valores por defecto para desarrollo y producción.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parámetros de configuración del sistema MarketPulse."""
    PROJECT_NAME: str = "MarketPulse"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Base de datos: por defecto SQLite asíncrono en la raíz del backend
    DATABASE_URL: str = "sqlite+aiosqlite:///./marketpulse.db"
    SQL_ECHO: bool = False

    # Configuración de lectura de archivo .env opcional
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
