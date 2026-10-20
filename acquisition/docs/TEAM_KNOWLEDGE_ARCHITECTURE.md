# Team Knowledge: arquitectura y plan

Fecha: 2026-08-07  
Estado: brief cerrado; diseño aceptado en
[`TEAM_KNOWLEDGE_SYSTEM_DESIGN.md`](TEAM_KNOWLEDGE_SYSTEM_DESIGN.md) y ejecución en
[`TEAM_KNOWLEDGE_DELIVERY_PLAN.md`](TEAM_KNOWLEDGE_DELIVERY_PLAN.md)  
Repo motor actual: `founder-guide`  
Audiencia: agentes de arquitectura e implementación; humanos del equipo

## 1. Visión

Una **base de conocimiento de equipo** con forma de wiki (vault Obsidian):

- Legible por **personas** (notas, links, MOCs).
- Consultable por **agentes** (CLI + skill, citas obligatorias).
- Exportable a **NotebookLM** (podcast / Audio Overview, material de aprendizaje).
- Con **ingesta de libros** (PDF/EPUB → markdown chunked + índice).
- Con **fuentes video** (YC y similares) ya prototipadas en founder-guide.

No es un SaaS multi-tenant. Es tooling interno (y opcionalmente motor OSS sin corpus con copyright).

### Job to be done

> Cuando alguien de negocio, diseño, producto o ingeniería tiene una duda, pregunta en lenguaje natural y obtiene respuesta **anclada a fuentes** (libro, nota, talk), no opinión suelta del modelo.

### Tres consumidores, una verdad

| Consumidor | Interfaz | Lee |
|------------|----------|-----|
| Humano | Obsidian / git MD | vault |
| Agente / dev | CLI + skill | vault + índice |
| Aprendizaje / contenido | NotebookLM | export generado desde vault |

Source of truth: **archivos markdown en el vault**. CLI, skill e índice son proyecciones. NotebookLM no es el cerebro: es destino de export.

## 2. Contexto: qué ya existe (founder-guide)

Repo: piso `acquisition/` del learning-kit

### Hecho y verde

- Dominio offline: catálogo, transcript, ingest, search, answer, notes/scope/stage.
- SPECs 001-006 de `ARCHITECTURE_SPEC.md` con tests de aceptación.
- SQLite write-through (`--db`).
- FastAPI mínimo + UI pregunta/citas.
- CLI: `demo`, `catalog-channel`, `ingest-video`, `ingest-pending`, `add-note`, `serve`, `verify-corpus`.
- Live captions: `TranscriptApiProvider` si hay `TRANSCRIPT_API_KEY` en env o `.env`.
- Fallback scrape: youtube-transcript-api + yt-dlp (hoy IP-baneado en la red de prueba).
- `ingest_pending` reporta `no_caption` e `invalid_transcript` sin tumbar el batch.
- `.env` local (gitignored) + `load_dotenv()` en CLI.

### Invariantes a preservar

1. Respuestas **extractivas** con **citas** (no alucinar corpus).
2. `insufficient_evidence` cuando no hay hits.
3. Procedencia de transcript (`manual` / `automatic`).
4. Segmentos acotados (hoy 60-120s en video).
5. Tests sin red en la suite default.
6. Secretos fuera de git (`.env`).

### No es meta de este doc reescribir

- Auth de producción (Cloudflare Access, etc.).
- PostgreSQL FTS.
- Deploy cloud.

Detalle operativo del motor actual: `HANDOFF.md`, `ARCHITECTURE_SPEC.md`.

## 3. Productos mentales (no mezclar)

| Capa | Nombre informal | Qué resuelve |
|------|-----------------|--------------|
| A | **Vault / wiki** | Personas leen y editan conocimiento por sección |
| B | **Motor guide** | Ingest + retrieve + answer + citas (video, luego book/md) |
| C | **Rules para agentes de código** | Estilo [agent-rules-books](https://github.com/ciembor/agent-rules-books): `full/mini/nano` como instrucciones de coding |
| D | **NotebookLM** | Podcast y estudio a partir de export |

A y B son el producto “conocimiento del equipo”.  
C puede vivir dentro de `04-codigo/` del vault (o submodule), pero su job es **guiar agentes que codean**, no responder dudas de ventas.  
D es pipeline de salida, no storage.

Referencia de patrón de destilación (no copiar libros): ciembor/agent-rules-books (MIT).

## 4. Secciones del vault

```
vault/
  00-general/           # cultura, glosario, cómo usar esto, MOC raíz
  01-startup-negocio/   # validación, ventas, teams, fundraising, ops
  02-diseno/            # producto, UX, marca, research
  03-ai/                # LLMs, RAG, evals, límites, uso interno de AI
  04-codigo/            # lineamientos + destilados tipo agent-rules-books
  _meta/                # índices, convenciones, licencias
  _export/notebooklm/   # generado; no editar a mano
  _raw/                 # opcional: binarios locales gitignored (PDF comprados)
```

Cada **obra o tema** es una carpeta:

```
01-startup-negocio/mom-test/
  _meta.yaml       # id, título, autor, license, source_hash, section
  README.md        # humano: qué es, cuándo aplica (1 pantalla)
  full.md          # canónico legible (humano + export + base de destilación)
  mini.md          # agente: reglas/cheatsheet accionable
  nano.md          # agente: presupuesto de contexto chico
  chunks/          # unidades de cita para retrieve (generadas por ingest)
    001.md
    002.md
```

### Roles de archivo

| Archivo | Humano | Agente coding/skill | Retrieve/RAG | NotebookLM |
|---------|--------|---------------------|--------------|------------|
| README.md | onboarding | link | bajo | opcional |
| full.md | lectura | raro | sí (o via chunks) | **principal** |
| mini.md | cheat sheet | **default** | opcional | opcional |
| nano.md | n/a | contexto justo | no | no |
| chunks/* | no | no | **cita atómica** | no |

Regla: **full es la verdad editorial**. mini/nano se derivan (proceso semi-manual o asistido). chunks se generan por ingest y no se editan a mano salvo corrección de OCR.

## 5. Ingesta de libros (módulo propio)

### Comando objetivo

```bash
guide ingest-book path/al/libro.pdf \
  --section 01-startup-negocio \
  --title "The Mom Test" \
  --author "Rob Fitzpatrick" \
  --license private \
  --book-id mom-test \
  --db ~/.cache/founder-guide/guide.sqlite
```

Soportar al menos: **PDF**, **EPUB**, **MD** ya limpio.

### Pipeline

1. **Extract** texto (PDF: PyMuPDF o similar; EPUB: ebooklib; MD: passthrough).
2. **Normalize** espacios, saltos de página → marcadores, basura de headers/footers.
3. **Structure** detectar capítulos/headings si existen; si no, ventanas por tokens.
4. **Chunk** ~800-1200 tokens, overlap pequeño; preferir límites de sección.
5. **Write vault** `_meta.yaml`, `full.md` (o full ensamblado), `chunks/NNN.md` con frontmatter.
6. **Index** en store del guide: `source_type=book`, citation estable.
7. **No** commitear PDF/EPUB comerciales al remoto público. `_raw/` + gitignore o vault privado.

### Frontmatter de chunk (cita)

```yaml
---
source_type: book
book_id: mom-test
section: 01-startup-negocio
title: "The Mom Test"
chapter: "1"
pages: "12-14"
license: private
---
Texto del chunk...
```

### Licencias

| license | Git público | Vault equipo | NotebookLM workspace |
|---------|-------------|--------------|----------------------|
| private / purchased | no | sí | sí (interno) |
| team-notes | según política | sí | sí |
| public-domain / CC permitido | sí con atribución | sí | sí |
| rules-distillation (inspirado, sin texto del libro) | sí (MIT propio) | sí | sí |

Azol debe proponer política explícita en `_meta/LICENSING.md`.

## 6. Video / YC (ya en motor)

- Catálogo canal + ingest captions (TranscriptAPI preferido con key).
- Segmentos con timestamp = citas.
- Piloto: ~20 videos YC/Platanus cuando haya `TRANSCRIPT_API_KEY`.
- Unificar después con books bajo el mismo `search` / `answer` (`source_type`: `youtube` | `book` | `note` | `md`).

## 7. Consulta: CLI, skill, UI

### CLI (extender guide)

```bash
guide q "cómo validar una oferta con clientes" --section 01-startup-negocio
guide answer "..."   # alias o mismo camino
```

Salida: texto extractivo + lista de citas (path, book_id/video_id, pages o t=).

### Skill (agentes IDE)

- Nombre tentativo: `vault` / `team-knowledge`.
- Trigger: dudas de negocio, diseño, AI de producto, lineamientos.
- Acción: invocar CLI o librería; devolver respuesta + paths `[[wikilinks]]` si aplica.
- Límite: cargar como máximo 1-2 `nano`/`mini` de `04-codigo` en tareas de código; no volcar el vault entero al system prompt.

### UI

- Mantener UI mínima del guide para demo interna.
- Obsidian es la UI de edición/wiki. No construir otra wiki web en el MVP.

## 8. Obsidian

- El directorio `vault/` (o repo hermano) se abre como vault.
- Wikilinks y MOCs en `00-general/` y por sección.
- Plugins útiles **opcionales** (no bloquean arquitectura):
  - Local REST API (coddingtonbear) si se quiere MCP write.
  - Ningún plugin requerido para CLI que solo lee filesystem.

### MCP Obsidian (fase 2)

- [obsidian-local-rest-api](https://github.com/coddingtonbear/obsidian-local-rest-api) + MCP bridges (cyanheads, MarkusPfundstein, etc.).
- Día 1: **filesystem + CLI**. MCP write solo si el equipo edita vía agente de forma habitual.

## 9. NotebookLM

### Rol

Generar **podcasts (Audio Overview)**, guías de estudio y onboarding a partir del conocimiento ya curado.

### Integración

| Fase | Cómo |
|------|------|
| MVP | `guide export-notebooklm --section 01-startup-negocio` → `_export/notebooklm/...` → upload manual |
| Luego | [notebooklm-mcp-cli](https://pypi.org/project/notebooklm-mcp-cli/) u equivalentes (RPC no oficial; frágil / ToS a evaluar) |

Recomendación: **un notebook por sección** (startup vs código no se contaminan).

Export incluye: `full.md` + READMEs de MOC. Excluye: `_raw/`, secrets, notes `license: private` si el notebook no es del workspace corporativo.

## 10. Retrieve y embeddings

| Fase | Retrieve |
|------|----------|
| MVP | Lexical / FTS sobre chunks y segmentos (como hoy) |
| Cuando duela | Hybrid: lexical + embeddings (modelo local tipo nomic/bge vía Ollama, o API ya pagada) |

No bloquear arquitectura de vault ni ingest-book por embeddings.  
Respuesta sigue siendo extractiva + citas; el embedding solo mejora ranking/recall.

## 11. Ecosistema relacionado (investigación)

### Parecidos

- agent-rules-books: destilados para coding agents.
- obsidian-rag-starter / glassMind: vault → RAG.
- OpenKnowledge: wiki MD team.
- Patrones “LLM wiki”: sources inmutables vs notas derivadas.

### Qué construir vs reusar

| Necesidad | Reusar | Construir en este sistema |
|-----------|--------|---------------------------|
| Wiki humana | Obsidian | convención de carpetas + MOCs |
| Ingesta libros | PyMuPDF / epub libs | `ingest-book` + chunk + frontmatter + index |
| Query + citas | founder-guide | `source_type` book/md + paths |
| Rules código | agent-rules-books / rules-books interno | sección `04-codigo` |
| Podcast | NotebookLM | export (+ CLI NL opcional después) |
| Captions YT | TranscriptAPI | ya en guide |

## 12. Decisiones abiertas (Azol debe cerrar o proponer)

1. **¿Un repo o dos?**  
   - Opción A: todo en `founder-guide` (`vault/` + motor).  
   - Opción B: `team-vault` (contenido) + `founder-guide` (motor como dep/CLI).  
   - Preferencia actual del hilo: contenido sensible/copyright fuera de git público; motor puede ser OSS.

2. **¿Idioma del vault?** Un idioma principal por repo (hoy español en handoff/spec). Términos técnicos en inglés inline.

3. **¿NotebookLM workspace** personal vs Google Workspace del equipo?

4. **¿Auth del serve?** Para vault local + CLI, `GUIDE_TOKEN` no es necesario. Solo si se expone HTTP.

5. **Tamaño de chunk y overlap** definitivos (proponer números y test).

6. **¿mini/nano de libros de negocio** se generan con LLM asistido + review humano, o solo manual al inicio?

## 13. No-goals (MVP)

- SaaS multi-equipo / billing.
- Subir PDFs con copyright a GitHub público.
- Sustituir lectura de libros por “solo el destilado” (los destilados no son el libro).
- Dependencia dura de API no oficial de NotebookLM en el camino crítico.
- Reescribir el motor de video desde cero.
- Embeddings día 1.
- Wiki web paralela a Obsidian.

## 14. Fases de implementación

### Fase 0: Documento y repos (esta entrega)

- [x] Este doc.
- [ ] Azol: ADR corto (Nygard) con decisión repo mono vs split + layout final.
- [ ] Track paralelo: lista de libros (ver §15).

### Fase 1: Esqueleto vault

- Crear árbol de secciones + 1 nota seed por sección.
- `00-general/README.md` (cómo contribuir, licencias, cómo preguntar).
- Abrir en Obsidian y validar wikilinks básicos.
- `.gitignore`: `_raw/`, PDFs, `.env`.

### Fase 2: ingest-book

- CLI `ingest-book` + tests con fixture PDF/MD chico (sin red).
- chunks + index SQLite.
- `guide q` o search unificado devuelve cita de libro.

### Fase 3: Unificar video + book en answer

- Mismo endpoint/CLI para ambos `source_type`.
- Piloto YC 20 con TranscriptAPI (key en `.env`).
- verify-corpus ampliado (issues si book sin chunks, etc.).

### Fase 4: Skill + export NotebookLM

- Skill del vault.
- `export-notebooklm` por sección.
- Prueba manual de Audio Overview en un notebook.

### Fase 5: Higiene y escala

- Embeddings hybrid si lexical falla en preguntas reales del equipo.
- MCP Obsidian opcional.
- Automatización NotebookLM solo si el export manual duele.
- Destilados mini/nano para 04-codigo (ciembor) y 1-2 libros de negocio.

## 15. Track paralelo: búsqueda de libros

Encargado: humano u otro agente (no bloquea a Azol).

### Entregable

Archivo propuesto: `docs/BOOK_CANDIDATES.md` (o sheet) con columnas:

| section | title | author | why (1 línea) | priority (P0/P1/P2) | license_notes | format_have (pdf/epub/paper/none) | ingest_ok |
|---------|-------|--------|---------------|---------------------|---------------|-----------------------------------|-----------|

### Cupo inicial sugerido

- **01-startup-negocio:** 5-8 (validación, lean, ventas/outbound, pricing, teams, fundraising).
- **02-diseno:** 3-5 (producto, UX research, visual/systems si aplica).
- **03-ai:** 3-5 (mental models AI, builders, evals/RAG prácticos; preferir textos actualizables + notas propias).
- **04-codigo:** no hace falta “ingerir” Clean Code entero si se usa destilado tipo agent-rules-books; listar 2-3 de cabecera + link al rule set.

### Criterios de selección

1. El equipo lo va a citar de verdad (no prestigioso-pero-muerto).
2. Formato obtenible legalmente (compra equipo / ya lo tienen).
3. Aplicable a más de un rol, o muy fuerte en un rol crítico.
4. Preferir pocos P0 ingeridos enteros antes que 40 títulos en wishlist.

### Ejemplos de semillas (solo pistas; el track confirma)

- Startup/negocio: The Mom Test; Traction; Inspired; The Cold Start Problem; libros/notas de sales que ya usen.
- Diseño: Inspired (solapa producto); Hooked o equivalentes que el equipo avale; design systems primer del equipo (notas propias > libro genérico).
- AI: apuntes internos de uso de modelos + 1-2 textos buenos de prompting/RAG; evitar “AI bestseller” vacío.
- Código: agent-rules-books / rules-books interno; DDIA o APoSD vía mini rules, no PDF pirata.

## 16. Brief para Azol (arquitectura)

**Misión:** bajar este doc a arquitectura implementable: ADRs, layout de repo(s), interfaces CLI, modelo de datos extendido, y plan de PRs chicos (<400 líneas c/u).

**Entregables esperados de Azol:**

1. ADR-001: mono-repo vs vault separado.  
2. ADR-002: modelo `Source` / documentos (youtube | book | md | note).  
3. Esquema de carpetas final + convenciones de `_meta.yaml`.  
4. Diseño de `ingest-book` (deps, errores, idempotencia por hash).  
5. Diseño de `q`/`answer` unificado y formato de cita.  
6. Diseño de `export-notebooklm`.  
7. Lista de PRs ordenados (Fase 1→4) con criterios de aceptación testeables.  
8. Riesgos: copyright, ToS NotebookLM no oficial, tamaño de vault en git.

**Constraints:**

- Reusar founder-guide; no greenfield.
- Tests sin red en default.
- Ponytail: mínimo código que cumpla el job; YAGNI embeddings/MCP/NL-auto.
- Un idioma de contenido; docs técnicos sin emoji.
- Commits/PRs voz humana; sin huella de co-autoría IA.

**Fuera de scope de Azol:** comprar libros, generar podcasts, redactar full.md de cada libro, implementar todo de una.

## 17. Brief para track de libros

**Misión:** proponer y priorizar corpus inicial por sección.

**Entregable:** `docs/BOOK_CANDIDATES.md` según §15.

**Constraints:** solo fuentes legales; marcar qué ya tiene el equipo en estante/Drive; P0 máximo ~8 títulos totales para primer trimestre.

## 18. Criterios de éxito (primer hito usable)

1. Vault abre en Obsidian con 4 secciones y navegación básica.  
2. Un libro de prueba (o MD fixture) ingerido → `guide q` devuelve cita con path/páginas.  
3. Una pregunta de negocio del equipo tiene respuesta con `insufficient_evidence=false` y cita real.  
4. Export de una sección sube a NotebookLM y genera un Audio Overview usable para onboarding.  
5. Suite de tests del motor sigue verde offline.

## 19. Referencias

- `ARCHITECTURE_SPEC.md`: motor guide original (video, SPECs).  
- `HANDOFF.md`: estado de implementación actual.  
- https://github.com/ciembor/agent-rules-books: patrón rules full/mini/nano.  
- https://github.com/coddingtonbear/obsidian-local-rest-api: API local Obsidian.  
- https://transcriptapi.com/docs/api/: captions YT managed.  
- https://pypi.org/project/notebooklm-mcp-cli/: automatización NL (evaluar después).

---

## Historial

| Fecha | Cambio |
|-------|--------|
| 2026-08-07 | Borrador inicial post discusión vault + books + NL + guide |
