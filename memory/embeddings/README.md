# Obsidian Semantic Indexing

Indice semantico de vaults Obsidian: guarda las notas en un **ChromaDB**
persistente y las busca por significado (no solo por palabra clave).

## Providers

Dos backends intercambiables; cada uno vive en su propia coleccion de
ChromaDB para que dimensiones distintas no choquen.

| Provider key | Modelo | Tipo | Dimensiones | Requiere |
|---|---|---|---|---|
| `ollama` *(default)* | `bge-m3` | Local, gratis | 1024 | Ollama en `localhost:11434` |
| `openrouter` | `text-embedding-3-large` | Nube | 3072 | `OPENROUTER_API_KEY` |

## Install

```bash
cd memory/embeddings
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # edita VAULT_PATHS con tus vaults
ollama pull bge-m3        # provider local
```

## Uso

```bash
# Indexado completo
.venv/bin/python index_vaults.py --full
# Incremental (solo archivos nuevos/modificados, por SHA256)
.venv/bin/python index_vaults.py --update
# Busqueda semantica
.venv/bin/python index_vaults.py --search "ideas sobre productividad"
.venv/bin/python index_vaults.py --search               # REPL interactivo
.venv/bin/python index_vaults.py --vault MiVault --search "query"
# Provider de nube
.venv/bin/python index_vaults.py --provider openrouter --full
```

| Flag | Que hace |
|---|---|
| `--full` | Reconstruye la coleccion del provider desde cero. |
| `--update` | Incremental: re-indexa cambios, borra lo eliminado. |
| `--search [QUERY]` | Busca; sin query abre modo interactivo. |
| `--provider {ollama,openrouter}` | Provider (default de `EMBEDDING_PROVIDER`). |
| `--vault NAME` | Acota a un vault (nombre de carpeta). |
| `--n-results N` | Numero de resultados (default 10). |

## Incremental

Cada archivo se hashea con SHA256; `--update` compara contra el cache y solo
embebe lo que cambio. Re-correr sin cambios hace **cero** llamadas de
embedding.

## Config (.env)

| Var | Default | Uso |
|---|---|---|
| `EMBEDDING_PROVIDER` | `ollama` | `ollama` / `openrouter` |
| `OPENROUTER_API_KEY` | — | Requerida para openrouter |
| `OLLAMA_MODEL` | `bge-m3` | Modelo local |
| `VAULT_PATHS` | `~/Obsidian/MyVault` | Vaults separados por coma |
| `CHROMA_PERSIST_DIR` | `~/.hermes/embeddings/obsidian-chroma` | Store vectorial |
| `CHUNK_MAX_CHARS` | `16000` | Cap de chunk (safe para token limits) |

## Providers propios

1. `providers/<nombre>.py` con una clase que extienda
   `BaseEmbeddingProvider` (`key`, `name`, `dimension`, `embed()`,
   `validate()`).
2. Registrarlo en `providers/__init__.py` -> `get_provider()`.
3. Agregarlo a las opciones de `--provider` en `index_vaults.py`.
