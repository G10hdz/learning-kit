"""Embedding provider factory and exports."""

import logging

from .base import BaseEmbeddingProvider
from .ollama_provider import OllamaProvider
from .openrouter import OpenRouterProvider

logger = logging.getLogger(__name__)


def get_provider(
    name: str = "auto",
    ollama_endpoint: str = "http://localhost:11434",
    ollama_model: str = "bge-m3",
    ollama_timeout: int = 60,
    openrouter_api_key: str = "",
    openrouter_base_url: str = "https://openrouter.ai/api/v1",
    openrouter_model: str = "text-embedding-3-large",
    openrouter_timeout: int = 60,
) -> BaseEmbeddingProvider:
    """Get an embedding provider by name.

    Args:
        name: ``"ollama"``, ``"openrouter"``, or ``"auto"``
            (try Ollama, fall back to OpenRouter).
        ollama_*: Ollama connection settings.
        openrouter_*: OpenRouter connection settings.

    Returns:
        An initialized and validated ``BaseEmbeddingProvider``.

    Raises:
        RuntimeError: If the requested provider is unavailable.
    """
    if name == "ollama":
        provider = OllamaProvider(
            endpoint=ollama_endpoint, model=ollama_model, timeout=ollama_timeout
        )
        if provider.validate():
            return provider
        raise RuntimeError(
            "Ollama provider selected but unavailable. "
            "Is Ollama running and is `ollama pull bge-m3` done?"
        )

    if name == "openrouter":
        provider = OpenRouterProvider(
            api_key=openrouter_api_key,
            model=openrouter_model,
            base_url=openrouter_base_url,
            timeout=openrouter_timeout,
        )
        if provider.validate():
            return provider
        raise RuntimeError(
            "OpenRouter provider selected but unavailable. "
            "Check OPENROUTER_API_KEY and network connectivity."
        )

    # "auto" — try Ollama first, then OpenRouter.
    ollama = OllamaProvider(
        endpoint=ollama_endpoint, model=ollama_model, timeout=ollama_timeout
    )
    if ollama.validate():
        logger.info("Auto: using Ollama provider.")
        return ollama

    if openrouter_api_key:
        logger.info("Ollama unavailable, trying OpenRouter...")
        orp = OpenRouterProvider(
            api_key=openrouter_api_key,
            model=openrouter_model,
            base_url=openrouter_base_url,
            timeout=openrouter_timeout,
        )
        if orp.validate():
            logger.info("Auto: using OpenRouter provider.")
            return orp

    raise RuntimeError(
        "No embedding provider available.\n"
        "  Option 1 (local): start Ollama and pull bge-m3:\n"
        "    $ ollama pull bge-m3 && ollama serve\n"
        "  Option 2 (cloud): set OPENROUTER_API_KEY in .env and run with --provider openrouter\n"
        "  Option 3: set EMBEDDING_PROVIDER=openrouter to force OpenRouter."
    )
