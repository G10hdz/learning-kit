# Team Knowledge: plan de entrega y delegación

Fecha: 2026-08-07

Arquitectura: [TEAM_KNOWLEDGE_SYSTEM_DESIGN.md](TEAM_KNOWLEDGE_SYSTEM_DESIGN.md)

## Orden de PRs

| PR | Dueño de archivos | Entrega | Gate | Delegación |
|---|---|---|---|---|
| 0 | `adr/*`, `docs/*` | decisiones y contratos | revisión humana | flagship |
| 1 | repo `team-vault` | secciones, MOCs, `_meta`, ignores | Obsidian abre; no binarios | free cloud |
| 2 | `store.py`, modelos v2, test de migración | schema genérico y copia v1 | DB vieja carga; suite verde | Pop 51B, review flagship |
| 3 | `book.py`, `vault.py`, fixture MD, test | ingest MD y rebuild | doble ingest no duplica | free cloud o Pop 7B |
| 4 | `query.py`, CLI, `http_api.py`, tests | search/answer/citas unificadas | mismas citas CLI/HTTP | Pop 51B, review flagship |
| 5a | adaptador PDF y fixture | extracción PDF opcional | páginas correctas, sin red | free/local |
| 5b | adaptador EPUB y fixture | extracción EPUB opcional | orden de capítulos correcto | free/local |
| 6 | exportador y test | bundle NotebookLM manual | privados excluidos por default | local; review humana |
| 7 | skill de consulta | wrapper del CLI | máximo 1–2 mini/nano | free cloud, review flagship |

Los PR 5a y 5b empiezan solo cuando exista un archivo legal que el equipo quiera
ingerir. MCP, embeddings y automatización de NotebookLM quedan fuera.

## Dependencias

```text
PR0 -> PR1 -> PR3 -> PR6
  \-> PR2 -> PR3 -> PR4 -> PR7
                    \-> PR5a
                    \-> PR5b
```

PR1 ocurre en `team-vault`. Los demás, en `founder-guide`. Nadie edita el mismo
archivo a la vez; commits y rebases se serializan por repo.

## Routing de modelos

- Flagship: contratos, migración final, licencia, scope, auth y review de citas.
- `opencode/deepseek-v4-flash-free`: árbol del vault, fixtures, CLI mecánica y
  tests con contrato congelado.
- `ollama-pop/qwen2.5-coder:7b`: implementación local pequeña o corpus P2.
- `ollama-pop/qwen3-coder-next:latest`: migración y compatibilidad multiarchivo.
- Codex paid: solo si free/local falla un gate dos veces con diagnóstico útil.

Antes de usar Pop: iniciar túnel y correr `smoke`. El corpus privado no se envía
a free cloud; los agentes reciben fixtures sintéticos.

## Contrato mínimo para cada delegación

Cada prompt incluye:

1. ruta exacta del repo y archivos exclusivos;
2. ADR y contrato que debe respetar;
3. fixture sintético, nunca corpus privado;
4. cambios fuera de scope;
5. comando de verificación;
6. instrucción de parar sin commit si necesita cambiar otro archivo.

Verificación base en `founder-guide`:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Criterio de escalación

Escalar al modelo siguiente solo si el agente barato falla dos veces el mismo
gate y entrega causa concreta. Auth, secretos, licencias, scopes o migraciones
destructivas pasan a revisión flagship desde el primer intento.

## Auditorías delegadas en esta entrega

- mapa de implementación y gaps contra el brief;
- revisión de contradicciones y ADRs;
- matriz de routing por costo, archivo y gate.

El coordinador integró los resultados; ningún agente delegado editó el repo.
