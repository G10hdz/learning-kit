"""Configuration loaded from environment variables and a project ``.env`` file.

The ``.env`` file is loaded from THIS project directory (next to this file) so
that configuration is robust regardless of the current working directory.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Always load the project-local .env, even when invoked from another cwd.
load_dotenv(Path(__file__).resolve().parent / ".env")


class Config:
    """Central configuration sourced from the environment."""

    # ------------------------------------------------------------------ #
    # Vaults
    # ------------------------------------------------------------------ #
    @classmethod
    def load_vaults(cls) -> dict[str, str]:
        """Return ``{short_name: absolute_path}`` for the Obsidian vaults.

        Reads from the ``VAULT_PATHS`` env var (comma-separated) if set,
        otherwise falls back to the three default vaults.
        """
        env_paths = os.getenv("VAULT_PATHS")
        if env_paths:
            paths = [p.strip() for p in env_paths.split(",") if p.strip()]
            return {Path(p).name: p for p in paths}

        home = Path.home()
        # Fallback generico: un solo vault. Declara los tuyos en VAULT_PATHS
        # (separados por coma): VAULT_PATHS="/ruta/vault1,/ruta/vault2"
        return {"MyVault": str(home / "Obsidian/MyVault")}

    # ------------------------------------------------------------------ #
    # ChromaDB (persistent vector store)
    # ------------------------------------------------------------------ #
    CHROMA_PERSIST_DIR = os.getenv(
        "CHROMA_PERSIST_DIR",
        str(Path.home() / ".hermes/embeddings/obsidian-chroma"),
    )
    #: Collections are namespaced per provider as ``<PREFIX>_<provider_key>``.
    CHROMA_COLLECTION_PREFIX = os.getenv("CHROMA_COLLECTION_PREFIX", "obsidian_notes")

    @classmethod
    def collection_name(cls, provider_key: str) -> str:
        """Build the collection name for a given provider key."""
        return f"{cls.CHROMA_COLLECTION_PREFIX}_{provider_key}"

    # ------------------------------------------------------------------ #
    # Ollama (local provider)
    # ------------------------------------------------------------------ #
    OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "bge-m3")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))

    # ------------------------------------------------------------------ #
    # OpenRouter (cloud provider)
    # ------------------------------------------------------------------ #
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "text-embedding-3-large")
    OPENROUTER_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "60"))

    # ------------------------------------------------------------------ #
    # Provider selection: "auto" | "ollama" | "openrouter"
    # ------------------------------------------------------------------ #
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama")

    # ------------------------------------------------------------------ #
    # Chunking
    # ------------------------------------------------------------------ #
    CHUNK_BY = os.getenv("CHUNK_BY", "heading")  # "heading" | "paragraph"
    CHUNK_HEADING_LEVEL = int(os.getenv("CHUNK_HEADING_LEVEL", "2"))
    CHUNK_PARAGRAPH_MAX_WORDS = int(os.getenv("CHUNK_PARAGRAPH_MAX_WORDS", "300"))
    #: Hard cap on chunk length in characters. Keeps every embedding safely
    #: below the model's token limit (text-embedding-3-large & bge-m3: 8192
    #: tokens; 16000 chars ~= 4000 tokens).
    CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "16000"))

    # ------------------------------------------------------------------ #
    # Incremental-index hash cache
    # ------------------------------------------------------------------ #
    HASH_CACHE_PATH = os.getenv(
        "HASH_CACHE_PATH",
        str(Path.home() / ".hermes/embeddings/hash_cache.json"),
    )
