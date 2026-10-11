"""ChromaDB persistent vector store wrapper."""

import logging
import os
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class ChromaStore:
    """Wrapper around ChromaDB's PersistentClient for Obsidian vault indexing."""

    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "obsidian_vaults",
        embedding_dimension: int = 1024,
    ):
        self.persist_directory = os.path.expanduser(persist_directory)
        self.collection_name = collection_name
        self.embedding_dimension = embedding_dimension

        # Ensure directory exists
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        """Get existing collection or create a new one."""
        try:
            return self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine", "dimension": self.embedding_dimension},
            )
        except Exception as e:
            logger.warning("Error getting/creating collection: %s", e)
            # Try creating fresh
            try:
                self._client.delete_collection(self.collection_name)
            except Exception:
                pass
            return self._client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine", "dimension": self.embedding_dimension},
            )

    def upsert_chunks(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> int:
        """Upsert chunks into the collection.

        Args:
            ids: Unique IDs for each chunk.
            embeddings: Embedding vectors.
            documents: Chunk text content.
            metadatas: Metadata dicts per chunk.

        Returns:
            Number of chunks upserted.
        """
        if not ids:
            return 0

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return len(ids)

    def delete_chunks_by_filter(self, where: dict) -> int:
        """Delete chunks matching a metadata filter.

        Args:
            where: ChromaDB filter dict, e.g. {"vault": "brain", "relative_path": "..."}

        Returns:
            Number of chunks deleted.
        """
        try:
            result = self._collection.delete(where=where)
            if result is None:
                return 0
            return len(result) if isinstance(result, list) else 1
        except Exception as e:
            # ChromaDB raises if nothing matches — that's fine
            logger.debug("Delete by filter (may be empty): %s", e)
            return 0

    def get_file_hashes(self, vault_name: str) -> dict[str, str]:
        """Get all (relative_path → sha256) mappings for a vault.

        Returns:
            Dict of {relative_path: sha256_hash} for all indexed files.
        """
        try:
            results = self._collection.get(
                where={"vault": vault_name},
                include=["metadatas"],
            )
        except Exception as e:
            logger.debug("Error getting file hashes: %s", e)
            return {}

        hashes: dict[str, str] = {}
        if results and results["metadatas"]:
            for meta in results["metadatas"]:
                path = meta.get("relative_path", "")
                sha = meta.get("sha256", "")
                if path and sha:
                    hashes[path] = sha
        return hashes

    def get_all_file_paths(self, vault_name: str) -> set[str]:
        """Get all indexed relative paths for a vault.

        Returns:
            Set of relative_path strings.
        """
        try:
            results = self._collection.get(
                where={"vault": vault_name},
                include=["metadatas"],
            )
        except Exception:
            return set()

        paths: set[str] = set()
        if results and results["metadatas"]:
            for meta in results["metadatas"]:
                path = meta.get("relative_path", "")
                if path:
                    paths.add(path)
        return paths

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """Search the collection by embedding vector.

        Args:
            query_embedding: The embedding vector to search with.
            n_results: Number of results to return.
            where: Optional metadata filter.

        Returns:
            List of result dicts with keys: id, document, metadata, distance
        """
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        formatted = []
        if results and results["ids"]:
            for i in range(len(results["ids"][0])):
                formatted.append(
                    {
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i]
                        if results.get("documents")
                        else "",
                        "metadata": results["metadatas"][0][i]
                        if results.get("metadatas")
                        else {},
                        "distance": results["distances"][0][i]
                        if results.get("distances")
                        else 0.0,
                    }
                )
        return formatted

    def count(self) -> int:
        """Return total number of chunks in the collection."""
        try:
            return self._collection.count()
        except Exception:
            return 0

    def reset_collection(self):
        """Delete and recreate the collection (for --full rebuild)."""
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = self._client.create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": "cosine",
                "dimension": self.embedding_dimension,
            },
        )
