# REQUIREMENTS

Que necesita cada piso y como instalarlo. Todo corre local; lo unico externo
es NotebookLM (Google), Calibre si lo montas en otro host, y providers de
captions opcionales.

## Tabla rapida

| Piso | Runtime | Deps externas | Opcional |
| --- | --- | --- | --- |
| `acquisition/` | Python >= 3.11 + uv/pip | fastapi, uvicorn, httpx, youtube-transcript-api | `live`: yt-dlp; `books`: PyMuPDF, ebooklib; TranscriptAPI key |
| `production/` | bash + Python 3 + `nlm` | `nlm` CLI + cuenta Google NotebookLM | pdflatex (PDFs), Calibre CWA via `CALIBRE_HOST` |
| `practice/` | nada (HTML/JS estatico) | navegador | node para los scripts de validacion |
| `memory/` | Python 3 stdlib | un servidor `ai-memory` MCP | Obsidian (el vault es solo una carpeta) |
| `surface/` | bash, python3 | tailscale (para publicar en tailnet) | node + player pr-explainer (explainers) |

---

## Base (una sola vez)

```sh
# uv — package/runner de python que tambien instala CLIs
curl -LsSf https://astral.sh/uv/install.sh | sh

# nlm — CLI de NotebookLM (libretas, fuentes, audio overviews)
uv tool install notebooklm-mcp-cli
nlm login          # auth interactiva con tu Google; cookies caducan cada pocas semanas
nlm doctor         # verifica
```

`install.sh` verifica todo esto solo (`./install.sh check`).

## acquisition/ — founder-guide

```sh
cd acquisition
uv venv && uv pip install -e .          # core
uv pip install -e '.[live]'             # + yt-dlp si vas a ingerir YouTube en vivo
uv pip install -e '.[books]'            # + epub/pdf de libros
```

- `scripts/acquire.py` — catalogo markdown -> inbox -> Calibre -> NotebookLM.
  Catalogo en `docs/book-candidates.md`, archivos en `vault/sources/files/`
  (se crea solo, gitignored).
- `scripts/mcp_server.py` — bridge MCP read-only sobre la API del proyecto.
- Calibre: define `CALIBRE_HOST` (host ssh con Calibre-Web-Automated en
  docker, `~/cwa/ingest/` como drop dir) para `push-calibre`. Sin la var, el
  resto funciona igual.
- `TRANSCRIPT_API_KEY` — provider de captions en live (evita el IP ban de
  YouTube). `.env.example` -> `.env`.
- Tests: `.venv/bin/python -m unittest discover -s tests -v`.

## production/ — capital-cultural

Convierte libretas NotebookLM en briefs diarios `.tex`/PDF y audiolibros
narrados. Sigue `production/AGENTS.md` (fuente de verdad + definicion de
terminado).

```sh
nlm login                                # requisito duro
./production/scripts/brief.sh <notebook-id> <categoria> <tema> <pregunta>
./production/scripts/voice-cast.sh <notebook-id> <slug> <categoria>
```

- El vault es `./vault` por default o `$CAPITAL_CULTURAL_VAULT`. Nace vacio:
  los scripts crean `_catalogo.md`, `logs/`, `summaries/` al primer uso.
- `pdflatex` (MacTeX/texlive) para compilar el PDF; sin el, quedan el `.tex`
  y el resumen igual.
- `docs/notebooklm-ingestion.md` documenta todos los comandos `nlm` usados,
  con fallback manual por si caduca la sesion.

## practice/ — hypatia

Cero instalacion: apps HTML/JS estaticas.

```sh
open practice/index.html                 # o
python3 -m http.server -d practice 8000
```

- `Flashcards/` — motor FSRS-6 (`fsrs.js`) + decks en `decks/*.js`. Deck nuevo =
  archivo `mi-deck.js` con `window.FLASHCARD_DECKS["mi-deck"] = {...}` (ver
  formato en `decks/fde.js`).
- `CubPrep`, `MLOps`, `SAA-C03` — modulos quiz por materia, bancos en
  `questions_by_materia/*.js`.
- Validacion (opcional, requiere node):
  `node scripts/validate-bank.mjs && node scripts/test-fsrs.mjs`.
- Spec del scheduler: `specs/fsrs-scheduling.md`.

## memory/ — vault-sync

```sh
mkdir -p ~/.config/vault-sync
cp memory/config.example.json ~/.config/vault-sync/config.json  # edita rutas
python3 memory/vault_sync.py
```

- Mapea lanes de directorios Markdown -> namespaces de un servidor
  `ai-memory` (MCP). Lo no declarado en `lanes` queda privado por omision.
- Config vive en `~/.config/vault-sync/config.json`, estado en
  `~/.cache/vault-sync/state.json`.
- Tests: `python3 -m unittest memory/tests/test_vault_sync.py` (stdlib).

## surface/ — hub web en tu tailnet

```sh
cd surface
./scripts/bundle.sh      # construye site/ (hub + apps de ../practice)
./scripts/serve.sh       # launchd + http.server en la IP tailscale, puerto 8787
./scripts/serve.sh off   # apaga
```

- Requiere tailscale corriendo (`tailscale ip -4`). Solo escucha en la IP de
  la tailnet: nada publico por diseno. En Linux sin launchd, sirve
  `python3 -m http.server 8787 --bind <tailscale-ip> -d site` via systemd.
- `explainers.txt` (copia de `explainers.example.txt`) lista modelos
  pr-explainer a publicar; requiere `PLAYER_DIR` apuntando al player.
- `AI_COACH_DIR` opcional: si tienes un repo coach con `web/` (vite build),
  el bundle lo integra; si no existe lo omite.

## Datos que NO van a git

`vault/` (contenido personal), `.env`, `site/`, `~/.config` reales,
`explainers.txt` propio, decks personales si no quieres compartirlos. El
`.gitignore` ya los cubre.
