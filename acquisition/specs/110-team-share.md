# SPEC 110: preparar founder-guide para compartir al team

Fecha: 2026-08-11
Estado: en ejecución

## Objetivo

Que cualquier miembro del team pueda levantar el proyecto y usar la UI interna
con una experiencia presentable. Deploy público, auth real (Cloudflare Access)
y migración PostgreSQL quedan fuera de este spec.

## Trabajo en paralelo

### Track A: UI presentable (`src/founder_guide/http_api.py` + tests)

- Citas con **título de la fuente** y **timestamp formateado** (`mm:ss`) en vez
  de URL cruda. Requiere threadear `title` desde `query.py` (ya hace join con
  `sources`) hasta `Citation` y el payload de `/v1/answers` y `/v1/search`.
- Estado de carga visible (spinner / "Buscando…") mientras corre el fetch.
- Campo `stage` en el formulario (la API ya lo soporta en `AnswerRequest`).
- Scopes del `<select>` servidos por el backend (endpoint o inyección en el
  HTML), no hardcodeados.
- Branding mínimo: favicon inline (emoji SVG), jerarquía visual de respuesta
  vs. citas, responsive básico. Sin frameworks, sin build step; mismo patrón
  de HTML inline en `_UI_HTML`.
- Tests: actualizar/extend `tests/test_acceptance.py` para el nuevo payload
  de citas (title presente, startSeconds intacto).

### Track B: README de onboarding (`README.md`)

- Qué es, requisitos (Python 3.11+, yt-dlp opcional para live).
- Setup: venv + `pip install -e .[live]`.
- Comandos: tests, `guide serve`, `guide demo`, ingest live con
  `TRANSCRIPT_API_KEY`.
- Auth bearer (`--token` / `GUIDE_TOKEN`) y estructura del repo.
- Basado en `HANDOFF.md` y `pyproject.toml`; en español, tono del proyecto.

## Secuencial (después de los tracks)

1. Revisar ambos diffs, correr `.venv/bin/python -m unittest discover -s tests -v`.
2. Actualizar `HANDOFF.md` (quitar "UI mínima" de pendientes, fechar cambio).
3. Commit: pendiente de confirmación explícita del usuario.

## Fuera de scope

- Deploy, Cloudflare Access, PostgreSQL FTS, Gemini, MCP.
- Piloto de 20 videos YC (bloqueado: requiere `TRANSCRIPT_API_KEY` en `.env`).
- Idempotency-Key replay cache.
