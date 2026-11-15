# Revisión del Sprint 1

* **Periodo:** Semanas 1 y 2 (Noviembre 2026)
* **Objetivo del Sprint (Sprint Goal):** Establecer la infraestructura base del proyecto, el modelado homogéneo de noticias financieras y la capa de persistencia relacional con deduplicación por hash SHA-256.
* **Estado:** Completado con éxito

---

## 1. Trabajo Realizado e Issues Cerradas

Durante este primer sprint se han abordado las tareas fundacionales del backend y la configuración del entorno:

1. **Issue #1 — Estructura base y configuración del proyecto:**
   - Configuración de arquitectura modular en `backend/` y `docs/`.
   - `.gitignore` robusto que evita subir binarios, entornos virtuales o PDFs de referencia.
   - `README.md` técnico con portada profesional, insignias de estado y guía de instalación.
   - Integración de la plantilla oficial de LaTeX de la EPS de la UBU en `docs/memoria/`.

2. **Issue #2 — Modelado de datos con Pydantic v2:**
   - Definición de esquemas de datos (`ArticleBase`, `ArticleCreate`, `ArticleResponse`) en `backend/app/schemas/article.py`.
   - Normalización automática de símbolos bursátiles (mayúsculas, sin espacios ni duplicados).
   - Cálculo automático de la huella digital SHA-256 combinando URL y texto del artículo.

3. **Issue #3 — Pruebas unitarias de esquemas:**
   - Suite de pruebas con `pytest` en `backend/tests/test_schemas.py` cubriendo casos válidos, campos obligatorios omitidos, URLs erróneas y longitud mínima de contenido.

4. **Issue #4 — Conexión y configuración de base de datos:**
   - Configuración centralizada de variables de entorno mediante `pydantic-settings` (`backend/app/core/config.py`).
   - Motor asíncrono con SQLAlchemy 2.0 y soporte para SQLite mediante `aiosqlite` (`backend/app/core/database.py`).

5. **Issue #5 — Modelo relacional y repositorio con deduplicación:**
   - Creación de la tabla `articles` en `backend/app/models/article.py` con índices en `url`, `content_hash` y `published_at`.
   - Implementación del patrón Repositorio (`backend/app/models/repository.py`) con el método `create_if_not_exists` para garantizar inserciones idempotentes.

6. **Issue #6 — Pruebas automáticas de persistencia:**
   - Batería de pruebas en `backend/tests/test_repository.py` utilizando una base de datos SQLite en memoria (`:memory:`).
   - Comprobación de que reintentos de inserción de la misma noticia no generan registros duplicados.

---

## 2. Métricas de Calidad y Pruebas

- **Total de pruebas automáticas:** 9 pruebas (5 unitarias de esquemas + 4 de integración de base de datos).
- **Resultado:** 100% pasadas en verde (`9 passed in 4.48s`).
- **Commits realizados:** 6 commits enlazados a sus correspondientes issues en GitHub (`#1`, `#2`, `#3`, `#4`, `#5`, `#6`).

---

## 3. Dificultades Encontradas y Soluciones

* **Deduplicación eficaz:** Las fuentes financieras a menudo republican una noticia cambiando ligeramente una frase o el titular, manteniendo la misma URL, o viceversa. Se optó por una doble comprobación: primero por hash de contenido (indexado y rápido) y secundariamente por URL canónica normalizada.
* **Manejo de tickers en SQLite:** SQLite no dispone de tipo de dato `ARRAY` nativo como PostgreSQL. Se utilizó la columna de tipo `JSON` de SQLAlchemy, compatible de forma transparente con ambos motores.

---

## 4. Planificación para el Sprint 2

En el siguiente sprint se abordará el núcleo de la extracción de datos:
- Implementación del extractor para noticias de **Yahoo Finance** (vía feeds/web estructurada).
- Implementación del extractor dinámico con **Playwright** para **Investing.com** (gestión de carga JavaScript y selectores).
- Pruebas de integración del scraper conectándolo con el repositorio para guardar noticias reales.
- Generación de la **Release v0.1.0** (primer entregable de los tres obligatorios).
