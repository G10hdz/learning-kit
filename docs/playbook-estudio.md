# Playbook de estudio: audiolibros y flashcards

El camino corto de "tengo un libro" a "lo escucho y lo retengo" usando solo
`nlm` + un vault de notas + las apps de `practice/`. Todo lo demas en el kit
son versiones más pulidas de estas mismas piezas.

![El ciclo de estudio: libro -> libreta -> artefactos -> briefs -> repaso -> surface, escribiendo al vault en cada vuelta](assets/playbook-loop.svg)

## 0. Una sola vez

```sh
uv tool install notebooklm-mcp-cli   # la CLI `nlm`
nlm login                            # auth Google (cookies caducan ~semanas)
nlm doctor                           # verifica
```

## 1. Libreta por tema

Convencion que hace que todo encaje: **una libreta por tema**, no por libro.
`"AI - fundamentos"`, `"Negocios - ventas"`. Los libros son fuentes dentro de
la libreta, y los artefactos (audio, quiz, briefs) salen del tema completo.

```sh
nlm notebook create "AI - fundamentos"
nlm source add <notebook-id> --file ~/libros/ai-engineering.pdf --wait
nlm source add <notebook-id> --url "https://..." --wait
```

Tambien puedes descubrir fuentes sin traerlas tu:

```sh
nlm research "attention mechanism transformers"    # busca y propone fuentes
```

## 2. Audiolibro

```sh
nlm audio create <notebook-id>          # audio overview de la libreta
nlm download <notebook-id> --audio -o ~/audiobooks/<tema>.mp3
```

El audio overview resume el tema completo con dos voces. Para algo más
fiel a "narracion de audiolibro", `production/scripts/voice-cast.sh`
consulta a la libreta que narrador le queda al libro y registra el cast
en el vault.

Sirve la carpeta `audiobooks/` desde `surface/` (o cualquier http.server en
tu tailnet) y escuchas hands-free desde el telefono.

## 3. Flashcards y retencion

Dos rutas, una dentro y una fuera de NotebookLM:

**Dentro (cero codigo):**

```sh
nlm flashcards create <notebook-id>     # flashcards nativas de NotebookLM
nlm quiz create <notebook-id>           # quiz con respuestas
nlm mindmap create <notebook-id>        # mapa mental del tema
nlm report create <notebook-id>         # study guide estructurado
```

**Fuera (espaciado real):** `practice/Flashcards/` corre FSRS-6 (el mismo
algoritmo de Anki). Un agente genera un deck `.js` desde la libreta
(`nlm query` -> preguntas/respuestas -> `window.FLASHCARD_DECKS[...]`) y el
scheduler decide cuando repasar cada carta. Ver `practice/specs/fsrs-scheduling.md`.

## 4. Que aterrice en el vault

El vault es solo una carpeta de Markdown; no hace falta API de Obsidian:

```
~/Obsidian/MiVault/
├── 00-Inbox/              # cae todo, procesas despues
├── 20-Study/
│   ├── briefs/            # un brief por sesion: YYYY-MM-DD-<tema>
│   ├── temas_investigacion.md   # backlog de que sigue
│   └── _roadmap-niveles.md
└── 30-Projects/
```

- `production/scripts/brief.sh <notebook-id> <cat> <tema> <pregunta>` escribe
  el `.answer` de la libreta como resumen normalizado en el vault.
- `memory/vault_sync.py` copia lanes del vault a una memoria consultable por
  agentes (`obsidian/study`, `obsidian/inbox`...). Lo no declarado queda
  privado por omision.
- `memory/embeddings/` indexa el vault por significado: `--search "esa idea
  de los vectores"` la encuentra aunque no recuerdes la frase.

## 5. El loop completo

```
libro -> LibGen/inbox -> libreta -> audio + quiz + brief
                                  -> vault (markdown)
                                  -> decks FSRS -> surface en tu telefono
```

Cada paso es un comando o un archivo. Si una pieza falla, el resto sigue:
sin `nlm` hay fallback manual (baja el audio/overview desde la web de
NotebookLM a `audiobooks/`); sin embeddings, busqueda por grep; sin surface,
abres `practice/` en el navegador.
