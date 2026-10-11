"""Embedding provider using bge-m3 through Ollama (local, default)."""

import json
import logging
import urllib.error
import urllib.request

from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseEmbeddingProvider):
    """Provider that calls bge-m3 via Ollama's native ``/api/embed`` endpoint.

    Uses only the standard library (``urllib``) so no extra dependency is
    required. Ollama's ``/api/embed`` supports batch embedding natively.
    bge-m3 produces 1024-dimensional vectors.
    """

    key = "ollama"

    def __init__(
        self,
        endpoint: str = "http://localhost:11434",
        model: str = "bge-m3",
        timeout: int = 60,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def name(self) -> str:
        return f"ollama/{self.model}"

    @property
    def dimension(self) -> int:
        return 1024

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via Ollama ``/api/embed`` (batched in a single request)."""
        if not texts:
            return []

        url = f"{self.endpoint}/api/embed"
        payload = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            raise RuntimeError(f"Ollama API error at {url}: {e}") from e

        embeddings = result.get("embeddings")
        if embeddings is None:
            raise RuntimeError(f"Ollama response missing 'embeddings' key: {result}")
        return embeddings

    def validate(self) -> bool:
        """Check if Ollama is running and the model is available."""
        url = f"{self.endpoint}/api/tags"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            models = [m["name"] for m in data.get("models", [])]
            available = any(
                m == self.model or m.startswith(f"{self.model}:") for m in models
            )
            if not available:
                logger.warning(
                    "Model '%s' not found in Ollama. Available: %s",
                    self.model,
                    ", ".join(models) if models else "(none)",
                )
                return False
            return True
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            logger.warning("Ollama not reachable at %s: %s", self.endpoint, e)
            return False
