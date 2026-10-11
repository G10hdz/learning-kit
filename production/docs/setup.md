# Montaje del proyecto

## Agente local con CLI o MCP

1. Abre esta carpeta como raíz del proyecto.
2. Indica al agente que lea `AGENTS.md`.
3. Confirma que `./vault` apunta al vault correcto.
4. Verifica `nlm login --check` y sigue `docs/notebooklm-ingestion.md`.
5. Selecciona la siguiente unidad en `vault/_roadmap-niveles.md` usando `vault/logs/estudio.md`.
6. Genera el `.tex` desde `templates/daily-brief.tex` mediante `prompts/ingesta-diaria.md`.
7. Compila con `pdflatex` dos veces cuando esté disponible y compara visualmente con `references/sample-daily-brief.pdf`.

ZCode, Claude, Codex, Kimi y Grok comparten este flujo. Las integraciones particulares viven en la configuración del agente, no dentro de los documentos canónicos.

## Fallback manual

Si `nlm` o el MCP fallan:

1. Crea o abre la libreta en la interfaz web.
2. Carga únicamente las fuentes registradas.
3. Copia la respuesta normalizada a `vault/summaries/`.
4. Continúa desde el prompt diario.

## Herramientas opcionales

- Papis: añadir cuando el catálogo supere aproximadamente 50 fuentes o haga falta BibTeX automático.
- Calibre: usar para administrar y convertir ebooks.
- TeX Live: necesario para compilar localmente; sin él se conserva el `.tex`.

La versión inicial no necesita daemon, base de datos ni scheduler propio. El agente que ejecute la sesión puede encargarse de la tarea programada.
