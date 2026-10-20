# learning-kit

[English README](README.en.md)

Sistema personal de aprendizaje operado por agentes, empaquetado en un solo
repo para clonar, instalar e iterar. Los agentes no son el truco: son la
tuberia. Cinco pisos conectados con piezas chicas y auditables en vez de una
app monolitica.

![Cinco pisos: fuentes -> acquisition -> NotebookLM -> production -> practice -> surface; vault y memory debajo](docs/assets/pipeline-flow.svg)

```
acquisition/   founder-guide: catalogo -> inbox -> Calibre -> NotebookLM
production/    capital-cultural: libretas -> briefs diarios LaTeX/PDF
               + narracion de audiolibros (voice-cast)
practice/      hypatia: modulos adaptativos estaticos (quiz, flashcards FSRS)
memory/        vault-sync: notas Markdown -> namespaces de una memoria MCP
               embeddings: indice semantico del vault (ChromaDB + bge-m3)
surface/       hub web estatico servido dentro de tu tailnet (nada publico)
```

`learning.yaml` es el registro del sistema completo (que piezas existen, donde
vive su estado, como se accede). `docs/architecture.md` cuenta el por que y
`docs/playbook-estudio.md` es el camino corto: libro -> audiolibro ->
flashcards con solo `nlm` + estas apps.

## Quickstart

```sh
./install.sh check   # que falta instalar
./install.sh         # instala por pisos (idempotente)
```

Requisitos por pieza en `REQUIREMENTS.md`. Las dos rutas mas cortas:

- **Audiolibros/briefs de tus libros**: `nlm login`, sube el libro a una
  libreta (`acquisition/scripts/acquire.py study`), audio overview en
  NotebookLM -> carpeta `audiobooks` -> `surface/`.
- **Flashcards**: `nlm flashcards create` / `nlm quiz create` dentro de la
  libreta, o `practice/Flashcards/index.html` con decks FSRS en
  `practice/Flashcards/decks/*.js` para repaso espaciado real.

## Que NO trae

- El piso de coaching (ai-coach): tiene estado personal, no se comparte. El
  `bundle.sh` de surface lo detecta si existe al lado y lo integra solo.
- El backbone `ai-memory` (MCP de memoria): pieza propia, fuera del repo.
  `memory/vault_sync.py` es opcional y `memory/embeddings/` funciona sin el.
- Datos: catalogs, vaults, decks propios y configs reales estan fuera o como
  `*.example`. Trae tus libros y tus notas.
- Un daemon central: cada piso es un proceso chico que se entiende solo.

## Reglas que lo hacen funcionar

1. **El vault es solo una carpeta.** Cualquier proceso puede escribir
   Markdown; no hace falta API de Obsidian.
2. **Privado por omision.** Lo personal vive fuera del repo (`vault/`,
   `state/`, configs en `~/.config`) y el .gitignore lo respalda.
3. **Nada publico.** `surface` se sirve solo dentro de la tailnet.

Cada piso conserva su propia licencia (Apache 2.0).
