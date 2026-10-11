# Instrucciones para agentes

## Fuente de verdad

Lee, en este orden:

1. `README.md`
2. `docs/architecture.md`
3. `vault/_roadmap-niveles.md`
4. `vault/logs/estudio.md`
5. El resumen indicado dentro de `vault/summaries/`

## Reglas

- Mantén los artefactos neutrales respecto al proveedor de IA.
- No inventes contenido que NotebookLM no haya extraído. Marca cualquier hueco como `PENDIENTE`.
- No presentes familiaridad superficial como experiencia. En los simuladores usa fórmulas honestas como “estoy estudiando…” o preguntas abiertas.
- Conserva las fuentes y su procedencia en `vault/sources/_catalogo.md`.
- No sobrescribas sesiones anteriores. Usa nombres `YYYY-MM-DD-<tema>`.
- Añade una sola entrada breve al log por ejecución.
- Usa `templates/daily-brief.tex` como contrato visual; no recrees su preámbulo.
- Usa `nlm` mediante los comandos documentados en `docs/notebooklm-ingestion.md`; conserva el fallback manual.
- Resuelve el contenido desde `CAPITAL_CULTURAL_VAULT` o, por defecto, `./vault`.
- Nunca confirmes en Git credenciales (`.env`, cookies, perfiles).

## Definición de terminado

Una sesión está completa cuando existen dentro del vault el resumen de entrada, el `.tex`, el PDF si hay compilador disponible y la entrada correspondiente en el log. El PDF debe conservar la jerarquía visual de `references/sample-daily-brief.pdf`.
