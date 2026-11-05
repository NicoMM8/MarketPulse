# MarketPulse
**Plataforma de Inteligencia Financiera y Análisis de Sentimiento basada en Extracción de Datos y Modelos de Lenguaje (LLMs)**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Playwright](https://img.shields.io/badge/Playwright-Web%20Scraping-45ba4b.svg)](https://playwright.dev/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Descripción del proyecto

**MarketPulse** es un Trabajo de Fin de Grado (TFG) para el **Grado en Ingeniería Informática (Modalidad Online)** de la **Universidad de Burgos (UBU)**.

El sistema implementa una arquitectura modular de tres capas diseñada para:
1. **Ingestión robusta:** Extraer noticias financieras en tiempo real y diferido desde portales clave (*Yahoo Finance*, *Investing.com*) combinando feeds estructurados y web scraping dinámico mediante **Playwright**.
2. **Núcleo analítico con LLMs:** Procesar el contenido textual de cada noticia mediante Modelos de Lenguaje (LLMs) aplicando esquemas estructurados para clasificar el sentimiento (*Positivo*, *Negativo*, *Neutral*), grado de confianza porcentual y entidades financieras afectadas.
3. **Dashboard interactivo:** Presentar cuadros de mando, evolución temporal del sentimiento de mercado y análisis por activo financiero, incluyendo soporte de internacionalización (i18n).

---

## Arquitectura del sistema

```
marketpulse/
├── backend/                 # API REST (FastAPI), Scraping y Núcleo Analítico
│   ├── app/
│   │   ├── api/             # Endpoints y controladores REST
│   │   ├── core/            # Configuración, settings y base de datos
│   │   ├── models/          # Modelos relacionales (SQLAlchemy 2.0)
│   │   ├── schemas/         # Validación de esquemas y DTOs (Pydantic v2)
│   │   └── services/
│   │       ├── scraper/     # Extractores asíncronos (Yahoo Finance, Investing)
│   │       └── nlp/         # Pipeline LLM y análisis de sentimiento
│   ├── tests/               # Pruebas unitarias e integración con Pytest
│   └── pyproject.toml       # Dependencias y configuración de herramientas
├── frontend/                # Dashboard interactivo (React + Vite + Tailwind)
├── docs/                    # Documentación formal, sprints y manuales
└── docker-compose.yml       # Orquestación de contenedores
```

---

## Metodología y planificación de releases

En cumplimiento de las directrices de la EPS de la Universidad de Burgos para la modalidad online, el proyecto se gestiona mediante metodología Scrum dividida en 6 Sprints y 3 Releases funcionales e incrementales:

- **Release v0.1.0 (Sprints 1 y 2):** Ingestión de datos, extracción estructurada con Playwright, deduplicación y persistencia relacional.
- **Release v0.2.0 (Sprints 3 y 4):** Integración del núcleo LLM, clasificación estructurada de sentimiento, API REST y benchmarks de evaluación.
- **Release v1.0.0 (Sprints 5 y 6):** Dashboard web interactivo, internacionalización (ES/EN), contenedorización completa y despliegue.

---

## Requisitos e instalación

### Requisitos previos
- Python >= 3.11
- Git
- Docker y Docker Compose (opcional para ejecución en contenedores)

### Configuración local del entorno de desarrollo (Backend)
```bash
# 1. Clonar el repositorio
git clone https://github.com/NicoMM8/MarketPulse.git
cd MarketPulse/backend

# 2. Crear y activar entorno virtual
python -m venv .venv
# En Windows:
.venv\Scripts\activate
# En Linux/macOS:
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Instalar los navegadores de Playwright
playwright install chromium

# 5. Ejecutar la suite de pruebas
pytest -v
```

---

## Seguimiento y auditoría del proyecto
- **Usuario UBU:** Se otorga acceso de lectura/auditoría al usuario del tribunal `ubutfgm` en GitHub.
- **Seguimiento Ágil:** La gestión de tareas se audita en la pestaña *Projects / Issues* del repositorio mediante *Milestones* por Sprint.

---

## Licencia
Distribuido bajo la Licencia MIT. Consulte `LICENSE` para más información.
