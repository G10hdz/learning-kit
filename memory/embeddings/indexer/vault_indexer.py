"""Vault indexer — orchestrates file discovery, chunking, embedding, and storage."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from .chunker import TextChunker, Chunk, chunk_id, compute_file_hash
from providers.base import BaseEmbeddingProvider
from store.chroma_store import ChromaStore

logger = logging.getLogger(__name__)

# Directories to always skip when scanning vaults
SKIP_DIRS = {
    ".obsidian",
    ".git",
    ".stfolder",
    ".stversions",
    "__pycache__",
    "node_modules",
    ".trash",
    ".smart-env",
    "graphify-out",
}


class VaultIndexer:
    """Orchestrates per-vault file discovery, chunking, embedding, and storage."""

    def __init__(
        self,
        vault_paths: dict[str, str],
        provider: BaseEmbeddingProvider,
        chroma_store: ChromaStore,
        chunker: Optional[TextChunker] = None,
        hash_cache_path: Optional[str] = None,
    ):
        self.vault_paths = vault_paths  # {name: absolute_path}
        self.provider = provider
        self.chroma_store = chroma_store
        self.chunker = chunker or TextChunker()
        self.hash_cache_path = hash_cache_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_full(self) -> dict:
        """Full rebuild: discover all files, chunk, embed, store.

        Returns stats dict.
        """
        logger.info("Full index — rebuilding all vaults...")
        self.chroma_store.reset_collection()

        total_files = 0
        total_chunks = 0
        total_errors = 0
        vaults_stats: dict[str, dict] = {}

        for vault_name, vault_path in self.vault_paths.items():
            files = self._discover_files(vault_path)
            logger.info(
                "Indexing vault '%s' (%s)... found %d files",
                vault_name, vault_path, len(files),
            )
            v_files, v_chunks, v_errors = self._index_files(
                vault_name, vault_path, files
            )
            vaults_stats[vault_name] = {
                "files": v_files,
                "chunks": v_chunks,
                "errors": v_errors,
            }
            total_files += v_files
            total_chunks += v_chunks
            total_errors += v_errors

        total_chroma = self.chroma_store.count()
        self._save_hash_cache_from_index(vaults_stats)

        stats = {
            "files_indexed": total_files,
            "chunks_created": total_chunks,
            "total_chunks_in_db": total_chroma,
            "errors": total_errors,
            "vaults": vaults_stats,
        }
        logger.info(
            "Full index complete: %d files, %d chunks (%d errors), %d total in DB",
            total_files, total_chunks, total_errors, total_chroma,
        )
        return stats

    def index_update(self) -> dict:
        """Incremental update: compare hashes, only re-index changed files.

        Steps per vault:
        1. Load cached hashes.
        2. Discover current .md files.
        3. Compute current hashes, compare with cache.
        4. Re-index changed/new files.
        5. Delete chunks for removed files.
        6. Save updated hash cache.

        Returns stats dict.
        """
        logger.info("Incremental update — checking for changes...")

        total_changed = 0
        total_chunks = 0
        total_errors = 0
        total_removed = 0
        vaults_stats: dict[str, dict] = {}

        cache = self._load_hash_cache()

        for vault_name, vault_path in self.vault_paths.items():
            if not os.path.isdir(vault_path):
                logger.warning("Vault path not found, skipping: %s", vault_path)
                continue

            discovered = self._discover_files(vault_path)
            discovered_paths = {str(p.relative_to(vault_path)) for p in discovered}
            cached_paths = set(cache.get(vault_name, {}).keys())
            cached_hashes = cache.get(vault_name, {})

            # Files that changed or are new
            changed: list[Path] = []
            for fp in discovered:
                rel = str(fp.relative_to(vault_path))
                current_hash = compute_file_hash(str(fp))
                cached_hash = cached_hashes.get(rel)
                if current_hash != cached_hash:
                    changed.append(fp)

            # Files that were removed
            removed_paths = cached_paths - discovered_paths
            for rel in removed_paths:
                deleted = self.chroma_store.delete_chunks_by_filter(
                    {"vault": vault_name, "relative_path": rel}
                )
                total_removed += deleted
                logger.info("  Removed %d chunks for deleted file: %s", deleted, rel)

            if not changed:
                logger.info(
                    "Vault '%s': no changes (%d files)", vault_name, len(discovered)
                )
                vaults_stats[vault_name] = {
                    "files_changed": 0,
                    "chunks": 0,
                    "errors": 0,
                    "removed": total_removed,
                }
                continue

            logger.info(
                "Vault '%s': %d changed/new files (of %d total)",
                vault_name, len(changed), len(discovered),
            )
            v_files, v_chunks, v_errors = self._index_files(
                vault_name, vault_path, changed
            )
            vaults_stats[vault_name] = {
                "files_changed": v_files,
                "chunks": v_chunks,
                "errors": v_errors,
                "removed": total_removed,
            }
            total_changed += v_files
            total_chunks += v_chunks
            total_errors += v_errors

        # Save updated cache
        self._save_hash_cache_from_index(vaults_stats)

        total_chroma = self.chroma_store.count()
        stats = {
            "files_changed": total_changed,
            "chunks_created": total_chunks,
            "chunks_removed": total_removed,
            "total_chunks_in_db": total_chroma,
            "errors": total_errors,
            "vaults": vaults_stats,
        }
        logger.info(
            "Update complete: %d changed files, %d chunks, %d removed (%d errors)",
            total_changed, total_chunks, total_removed, total_errors,
        )
        return stats

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _discover_files(self, vault_path: str) -> list[Path]:
        """Walk a vault directory and return all .md file paths.

        Skips hidden directories, .obsidian, etc.
        """
        files: list[Path] = []
        vault_root = Path(vault_path)
        if not vault_root.exists():
            logger.warning("Vault path does not exist: %s", vault_path)
            return files

        for root, dirs, names in os.walk(vault_root):
            # Skip excluded directories in-place (os.walk respects this)
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

            for name in names:
                if name.endswith(".md"):
                    files.append(Path(root) / name)

        return sorted(files)

    def _index_files(
        self, vault_name: str, vault_path: str, files: list[Path]
    ) -> tuple[int, int, int]:
        """Chunk, embed, and store a list of files.

        Returns (files_indexed, chunks_created, errors).
        """
        n_files = 0
        n_chunks = 0
        n_errors = 0

        for fp in tqdm(files, desc=f"  {vault_name}", unit="file"):
            try:
                relative = str(fp.relative_to(Path(vault_path)))
                chunks = self.chunker.chunk_file(
                    str(fp), vault_name, relative
                )
                if not chunks:
                    continue

                # Delete old chunks for this file (in case content changed)
                self.chroma_store.delete_chunks_by_filter(
                    {"vault": vault_name, "relative_path": relative}
                )

                # Embed
                texts = [c.text for c in chunks]
                embeddings = self.provider.embed(texts)

                # Upsert
                ids = [chunk_id(c) for c in chunks]
                metadatas = [
                    {
                        "vault": c.vault,
                        "relative_path": c.relative_path,
                        "file_title": c.file_title,
                        "heading": c.heading or "",
                        "heading_level": c.heading_level,
                        "chunk_index": c.chunk_index,
                        "modified_at": c.modified_at,
                        "word_count": c.word_count,
                        "sha256": c.sha256,
                    }
                    for c in chunks
                ]

                self.chroma_store.upsert_chunks(
                    ids=ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas,
                )

                n_files += 1
                n_chunks += len(chunks)

            except (RuntimeError, OSError, PermissionError) as e:
                logger.error("Error indexing %s: %s", fp, e)
                n_errors += 1
                continue

        return n_files, n_chunks, n_errors

    # ------------------------------------------------------------------
    # Hash cache management
    # ------------------------------------------------------------------

    def _load_hash_cache(self) -> dict:
        """Load hash cache from JSON file."""
        if not self.hash_cache_path:
            return {}
        path = Path(os.path.expanduser(self.hash_cache_path))
        if not path.exists():
            return {}
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load hash cache: %s", e)
            return {}

    def _save_hash_cache_from_index(self, vaults_stats: dict):
        """Compute fresh hash cache from currently indexed files and save."""
        if not self.hash_cache_path:
            return

        cache: dict[str, dict[str, str]] = {}
        for vault_name in self.vault_paths:
            vault_path = self.vault_paths[vault_name]
            if not os.path.isdir(vault_path):
                continue
            files = self._discover_files(vault_path)
            vault_cache: dict[str, str] = {}
            for fp in files:
                rel = str(fp.relative_to(Path(vault_path)))
                vault_cache[rel] = compute_file_hash(str(fp))
            cache[vault_name] = vault_cache

        path = Path(os.path.expanduser(self.hash_cache_path))
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w") as f:
                json.dump(cache, f, indent=2)
            logger.info("Hash cache saved to %s (%d entries)", path, sum(len(v) for v in cache.values()))
        except OSError as e:
            logger.error("Failed to save hash cache: %s", e)
