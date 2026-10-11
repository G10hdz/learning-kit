"""Abstract base class for embedding providers.

Spec contract: every concrete provider declares its vector ``dimension`` and a
collection-safe ``key``. The ``key`` is used to namespace ChromaDB collections
(``obsidian_notes_<key>``) so that providers with different dimensions never
collide on the same collection.
"""

from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """Interface for embedding providers."""

    #: Collection-safe identifier, e.g. ``"ollama"`` or ``"openrouter"``.
    key: str = "base"

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for logging/display."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimension produced by this provider's model."""
        ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts.

        Args:
            texts: Text strings to embed.

        Returns:
            One embedding vector per input text, order preserved.
        """
        ...

    @abstractmethod
    def validate(self) -> bool:
        """Return True if the provider is reachable and ready."""
        ...
