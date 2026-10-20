# learning-kit

[README en español](README.md)

A personal learning system operated by agents, packaged in a single repo to
clone, install and iterate on. The agents are not the trick: they are the
plumbing. Five connected floors built from small, auditable pieces instead of
one monolithic app.

![Five floors: sources -> acquisition -> NotebookLM -> production -> practice -> surface; vault and memory underneath](docs/assets/pipeline-flow.svg)

```
acquisition/   founder-guide: catalog -> inbox -> Calibre -> NotebookLM
production/    capital-cultural: notebooks -> daily LaTeX/PDF briefs
               + audiobook narration (voice-cast)
practice/      hypatia: static adaptive modules (quiz, FSRS flashcards)
memory/        vault-sync: Markdown notes -> namespaces of an MCP memory
               embeddings: semantic index of the vault (ChromaDB + bge-m3)
surface/       static web hub served inside your tailnet (nothing public)
```

`learning.yaml` is the registry of the whole system (which pieces exist,
where their state lives, how to reach them). `docs/architecture.md` tells the
why and `docs/playbook-estudio.md` is the short path: book -> audiobook ->
flashcards with only `nlm` + these apps.

## Quickstart

```sh
./install.sh check   # what is missing
./install.sh         # installs by floors (idempotent)
```

Per-piece requirements in `REQUIREMENTS.md`. The two shortest routes:

- **Audiobooks/briefs from your books**: `nlm login`, upload the book to a
  notebook (`acquisition/scripts/acquire.py study`), audio overview in
  NotebookLM -> `audiobooks` folder -> `surface/`.
- **Flashcards**: `nlm flashcards create` / `nlm quiz create` inside the
  notebook, or `practice/Flashcards/index.html` with FSRS decks in
  `practice/Flashcards/decks/*.js` for real spaced repetition.

## What it does NOT include

- The coaching floor (ai-coach): it holds personal state and is not shared.
  `surface/scripts/bundle.sh` detects it if it exists next door and wires it in.
- The `ai-memory` backbone (memory MCP): its own piece, outside this repo.
  `memory/vault_sync.py` is optional and `memory/embeddings/` works without it.
- Data: catalogs, vaults, your own decks and real configs stay out or come as
  `*.example`. Bring your books and your notes.
- A central daemon: each floor is a small process you can understand alone.

## Rules that make it work

1. **The vault is just a folder.** Any process can write Markdown; no
   Obsidian API needed.
2. **Private by default.** Personal stuff lives outside the repo (`vault/`,
   `state/`, configs in `~/.config`) and .gitignore backs it up.
3. **Nothing public.** `surface` is served only inside the tailnet.

Each floor keeps its own license (Apache 2.0).
