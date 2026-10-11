# Founder Guide

Base de conocimiento para founders construida desde transcripts de YouTube (YC y
similares) y libros. Ingiere fuentes, las segmenta con citas al segundo exacto y
responde preguntas en lenguaje natural ancladas a esas fuentes. Expone una API
FastAPI y una UI interna mínima.

**Estado actual:** funciona en local (tests verdes, SPECs 001–006 + tracks de
vault/búsqueda en `specs/`). Pendiente deploy y el piloto de 20 videos YC
(bloqueado por IP ban de YouTube, ver [Pendientes](#pendientes-conocidos)).

## Requisitos

- Python 3.11+
- `yt-dlp` solo para el modo live (catálogo y fallback de captions); se instala
  con el extra `live`.
- Para evitar el IP ban de YouTube en live: cuenta en
  [TranscriptAPI](https://transcriptapi.com) (free tier ~100 créditos,
  1 crédito/transcript).

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[live]'
```

Sin el extra (`pip install -e .`) todo funciona offline con fixtures; solo el
modo live requiere `yt-dlp`.

Variables de entorno (copiar `.env.example` a `.env`; el CLI lo carga solo):

| Variable | Uso |
|---|---|
| `TRANSCRIPT_API_KEY` | Provider de captions en live; evita el IP ban de YouTube. Alias: `GUIDE_TRANSCRIPT_API_KEY`. |
| `GUIDE_TOKEN` | Bearer token del servidor (alternativa a `--token`). |

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Uso

Demo end-to-end offline (ingesta un transcript fixture y responde una pregunta):

```bash
.venv/bin/guide demo
```

Levantar el servidor:

```bash
.venv/bin/guide serve --db /tmp/guide.sqlite --token dev --port 8080
```

- UI interna en `GET /` (pregunta + respuesta con citas).
- Auth bearer: `--token` o `GUIDE_TOKEN`. Si ambos están vacíos, queda abierto
  (modo local).
- Sin `--db` el corpus vive solo en memoria; con `--db` persiste en SQLite.

Endpoints: `GET /` (UI), `GET /v1/search`, `POST /v1/answers`,
`POST /v1/admin/ingestions`, `GET /v1/admin/verify`, `GET /healthz`.

Comandos del CLI (`guide <comando>`):

| Comando | Qué hace |
|---|---|
| `demo` | Demo offline: ingesta fixture y responde una pregunta de ejemplo. |
| `catalog-channel` | Lista videos de un canal y los registra como fuentes. |
| `ingest-video` | Ingiere el transcript de un video (`guide ingest-video VIDEO_ID`). |
| `ingest-pending` | Cataloga un canal e ingiere las fuentes pendientes. |
| `add-note` | Agrega una nota del equipo (`--scope shared` u otro configurado vía `GUIDE_SCOPES`, `--stage`, `--content`). |
| `serve` | Levanta la API + UI (`--host`, `--port`, `--token`, `--db`). |
| `verify-corpus` | Verifica integridad del corpus (segmentos, citas, timestamps). |

Flags comunes: `--limit`, `--languages es,en`, `--db`, `--fixture`,
`--catalog-fixture`, `--transcript-fixture`, `--live`.

## Modo live (YouTube real)

Sin `--live` todo corre con fixtures offline. Con `--live` se usan proveedores
reales: catálogo vía `yt-dlp` y captions con chain
`youtube-transcript-api` → `yt-dlp`. Si `TRANSCRIPT_API_KEY` está seteada, las
captions salen solo por TranscriptAPI, lo que evita el IP ban de YouTube al
scrapear desde la IP local.

```bash
export TRANSCRIPT_API_KEY=...
.venv/bin/guide catalog-channel 'https://www.youtube.com/@ycombinator' --live --limit 5
.venv/bin/guide ingest-pending 'https://www.youtube.com/@ycombinator' --live --limit 50 --languages es,en --db ~/.cache/founder-guide/pilot.sqlite
.venv/bin/guide verify-corpus --db ~/.cache/founder-guide/pilot.sqlite
```

Nota: `yt-dlp` debe estar en el `PATH` para el catálogo live (con
`.venv/bin` en `PATH` alcanza si instalaste el extra `live`).

## Estructura del repo

| Ruta | Contenido |
|---|---|
| `src/founder_guide/` | Paquete principal. `__init__.py` (dominio + CLI), `http_api.py` (FastAPI), `catalog.py`, `transcript.py`, `store.py` (SQLite), `synthesis.py`, `vault.py` / `book.py` / `index.py` / `query.py` / `models.py` (vault markdown e ingesta de libros), fixtures demo. |
| `specs/` | Specs numeradas por track (070 vault/ingesta … 110 team-share). |
| `docs/` | Arquitectura y plan del sistema team knowledge. |
| `adr/` | Decisiones de arquitectura (004, 005). |
| `tests/` | Suite `unittest` + fixtures. |
| `HANDOFF.md` | Estado operativo detallado, comandos de verificación y bloqueos. |

## Pendientes conocidos

- Deploy público y auth real (Cloudflare Access).
- Piloto de 20 videos YC/Platanus: catálogo ya probado, ingesta bloqueada por
  IP ban de YouTube — requiere `TRANSCRIPT_API_KEY` en `.env`.
- PostgreSQL FTS (hoy SQLite), Gemini, MCP.
- Idempotency-Key replay cache (el header se acepta, sin replay aún).

Detalle y contexto operativo: [`HANDOFF.md`](HANDOFF.md). Visión de largo plazo
(base de conocimiento de equipo, vault Obsidian, NotebookLM):
[`docs/TEAM_KNOWLEDGE_ARCHITECTURE.md`](docs/TEAM_KNOWLEDGE_ARCHITECTURE.md).
