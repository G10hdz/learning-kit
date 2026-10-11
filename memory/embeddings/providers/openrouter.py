"""Embedding provider using text-embedding-3-large through OpenRouter."""

import logging

from openai import OpenAI

from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseEmbeddingProvider):
    """Provider that calls ``text-embedding-3-large`` via the OpenRouter API.

    OpenRouter exposes an OpenAI-compatible ``/v1/embeddings`` endpoint, so we
    use the official ``openai`` SDK with a custom ``base_url``. The model
    produces **3072-dimensional** vectors.
    """

    key = "openrouter"
    DEFAULT_MODEL = "text-embedding-3-large"
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DIMENSION = 3072
    DEFAULT_BATCH_SIZE = 64

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 60,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is required for the OpenRouter provider."
            )
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size
        self._client = OpenAI(
            base_url=self.base_url, api_key=api_key, timeout=timeout
        )

    @property
    def name(self) -> str:
        return f"openrouter/{self.model}"

    @property
    def dimension(self) -> int:
        return self.DIMENSION

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in batches via the OpenAI-compatible endpoint."""
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            resp = self._client.embeddings.create(model=self.model, input=batch)
            out.extend([d.embedding for d in resp.data])
        return out

    def validate(self) -> bool:
        """Return True if the API key works and the endpoint responds."""
        try:
            self._client.embeddings.create(model=self.model, input="validation")
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("OpenRouter not reachable: %s", e)
            return False
