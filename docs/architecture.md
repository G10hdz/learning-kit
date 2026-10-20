---
title: Learning Stack: sistema personal de aprendizaje operado por agentes
fecha: 2026-09-20
estado: borrador compartible
---

# Learning Stack

Un sistema personal de aprendizaje donde los agentes no son el truco: son la tubería. La idea central es separar **cinco pisos** (adquisición, producción, práctica, memoria y superficie) y conectarlos con piezas chicas y auditables en vez de una app monolítica.

## La gran foto

```
FUENTES ── libros, papers, URLs, transcripts, libretas NotebookLM
   │
ADQUISICIÓN
   ├─ acquire.py        catálogo en markdown, links de búsqueda, inbox
   └─ Calibre (CWA)     convierte, completa metadata, manda al Kindle
   │
PRODUCCIÓN
   ├─ generador de briefs   fuentes → briefs diarios LaTeX/PDF, rotación por categorías
   ├─ vault de estudio      viaja como git bundle (un archivo con historia completa)
   └─ NotebookLM            una libreta por tema; audio overviews
   │
PRÁCTICA
   ├─ coach de entrevistas/oratoria   estado vivo en state/, rúbricas, drills
   └─ módulos adaptativos             apps HTML estáticas, sin build
   │
MEMORIA
   ├─ mega vault Obsidian   superficie humana única, backup git privado
   ├─ vault_sync            lanes → namespaces de una memoria MCP
   ├─ índice semántico      ChromaDB local, búsqueda por significado
   └─ grafo personal        MCP read-only, consulta estructural
   │
AGENTES ── gateway con MCPs (memoria, grafo) + CLIs (nlm, acquire, sync)
```

## Las reglas que lo hacen funcionar

1. **El vault es solo una carpeta.** Cualquier proceso puede escribir Markdown; no hace falta API de Obsidian. Lo que debe ser consultable por agentes entra por un sync de lanes; lo demás queda privado por omisión.
2. **Sync por lanes, no por todo.** `vault_sync` mapea directorios a namespaces (`20-Study` → `obsidian/study`, `coaching/` → `obsidian/coaching`). Los snapshots de archivo (`Imports/`) se excluyen: son historia, no memoria viva.
3. **El estado de práctica se exporta como notas.** Los sistemas externos (coach, módulos) no se copian al vault: se registran como *external lanes* y sus `.md` se indexan directo desde su repo.
4. **Los pasos grises son humanos deliberados.** La descarga desde fuentes shadow-library es manual por diseño: el pipeline genera el link de búsqueda, la persona decide, el archivo cae a un inbox. Lo que funciona, se compra físico.
5. **Un registry declara los sistemas.** `learning.yaml` lista cada sistema con su piso, host, repo, acceso (CLI/MCP/API/archivo) y data tier, el equivalente de un `agents.yaml` para el aprendizaje.
6. **Data tiers respetados.** Conversaciones privadas y datos de trabajo anonimizado tienen tier alto: entran a memoria solo donde corresponde y nunca a índices globales.

## Piezas del stack

| Pieza | Piso | Rol |
|---|---|---|
| acquire.py + catálogo md | adquisición | sugerir → link de búsqueda → inbox → Calibre → NotebookLM |
| generador de briefs | producción | briefs diarios LaTeX/PDF con rotación anti-repetición |
| vault de estudio + bundles | producción | git bundle como transporte: un archivo, historia completa, por cualquier canal |
| NotebookLM (vía `nlm`) | producción | síntesis, audio overviews, una libreta por tema |
| coach (skills + state) | práctica | entrevistas, oratoria, drills; el progreso vive en Markdown |
| módulos estáticos | práctica | apps HTML de aprendizaje adaptativo |
| mega vault | superficie | superficie humana; git privado como backup y puente |
| ai-memory + vault_sync | memoria | namespaces por lane; agentes consultan por MCP |
| índice semántico | memoria | búsqueda por significado sobre el vault |
| grafo personal | memoria | entidades y relaciones, MCP read-only |
| Calibre en otro host | superficie | librería + conversión + Kindle |

## Qué es compartible y qué no

**Compartible:** el patrón (este documento), el generador de briefs, `vault_sync`, `acquire.py`, `learning.yaml`, los módulos estáticos, las skills de coaching vendor (MIT/CC-BY).

**Privado por diseño:** el contenido del vault, el estado de coaching, transcripts, el paso de descarga manual, y cualquier dato tier 3.

## Por qué no una app

Cada piso ya tenía una herramienta que funcionaba. Unificar no era reescribir: era declarar las fronteras (registry), abrir un solo canal de memoria (lanes → MCP) y dejar que cada pieza siga en su runtime. Los agentes leen el mapa y operan las piezas; yo solo estudio.
